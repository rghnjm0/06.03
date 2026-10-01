"""Рабочая часть админ-панели АИС «Уют»."""
from datetime import datetime
import csv
import io
from flask import Response
from flask import render_template, request, redirect, url_for, flash, session
from db import get_db, db_session
from utils import sync_room_statuses, booking_conflicts, next_id, booking_total, safe_csv_value
from security import admin_required
from services.passwords import hash_password, validate_password

STATUSES = ('Подтверждено', 'Заселен', 'Завершено', 'Отменено')
ACTIVE = ('Подтверждено', 'Заселен')


def _date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()


def _db_error_message(e):
    """Единое сообщение об ошибке БД/валидации для админ-маршрутов."""
    return str(e) if isinstance(e, ValueError) else "Внутренняя ошибка. Попробуйте ещё раз."


def register_admin_routes(app):
    @app.route('/admin')
    def admin_root():
        return redirect(url_for('admin_dashboard')) if session.get('user_role') == 'admin' else redirect(url_for('login'))

    @app.route('/admin/login')
    def admin_login_redirect():
        return redirect(url_for('login'))

    @app.route('/admin/dashboard')
    @admin_required
    def admin_dashboard():
        sync_room_statuses()
        today = datetime.now().strftime('%Y-%m-%d')
        with db_session() as conn:
            total_rooms = conn.execute("SELECT COUNT(*) FROM Номера").fetchone()[0]
            free_rooms = conn.execute("SELECT COUNT(*) FROM Номера WHERE Статус='Свободен'").fetchone()[0]
            occupied_rooms = conn.execute("SELECT COUNT(*) FROM Номера WHERE Статус='Занят'").fetchone()[0]
            future_rooms = conn.execute("SELECT COUNT(*) FROM Номера WHERE Статус='Будет занят'").fetchone()[0]
            active_bookings = conn.execute("SELECT COUNT(*) FROM Бронирования WHERE Статус IN ('Подтверждено','Заселен')").fetchone()[0]
            arrivals_today = conn.execute("SELECT COUNT(*) FROM Бронирования WHERE Статус='Подтверждено' AND Дата_заезда=?", (today,)).fetchone()[0]
            departures_today = conn.execute("SELECT COUNT(*) FROM Бронирования WHERE Статус='Заселен' AND Дата_выезда=?", (today,)).fetchone()[0]
            revenue = conn.execute("SELECT COALESCE(SUM(Сумма_проживание),0) FROM Счета s JOIN Бронирования b ON b.ID_Бронирования=s.ID_Бронирования WHERE b.Статус!='Отменено'").fetchone()[0]
            paid = conn.execute("SELECT COALESCE(SUM(s.Сумма_проживание),0) FROM Счета s JOIN Бронирования b ON b.ID_Бронирования=s.ID_Бронирования WHERE s.Оплачено=1 AND b.Статус!='Отменено'").fetchone()[0]
            unpaid = max(0, revenue - paid)

            upcoming_checkins = conn.execute("""
                SELECT b.*, n.Номер_Комнаты, c.Фамилия, c.Имя, c.Телефон
                FROM Бронирования b
                JOIN Номера n ON n.ID_Номера=b.ID_Номера
                JOIN Клиенты c ON c.ID_Клиента=b.ID_Клиента
                WHERE b.Статус='Подтверждено' AND b.Дата_заезда >= ?
                ORDER BY b.Дата_заезда, n.Номер_Комнаты LIMIT 8
            """, (today,)).fetchall()
            recent_bookings = conn.execute("""
                SELECT b.*, n.Номер_Комнаты, c.Фамилия, c.Имя, c.Телефон
                FROM Бронирования b
                JOIN Номера n ON n.ID_Номера=b.ID_Номера
                JOIN Клиенты c ON c.ID_Клиента=b.ID_Клиента
                ORDER BY b.Код DESC LIMIT 10
            """).fetchall()
            room_status_stats = conn.execute("""
                SELECT Категория, COUNT(*) total,
                       SUM(CASE WHEN Статус='Свободен' THEN 1 ELSE 0 END) free,
                       SUM(CASE WHEN Статус='Занят' THEN 1 ELSE 0 END) occupied,
                       SUM(CASE WHEN Статус='Будет занят' THEN 1 ELSE 0 END) future
                FROM Номера GROUP BY Категория ORDER BY Категория
            """).fetchall()
            return render_template('admin/dashboard.html', **locals())

    @app.route('/admin/logout', methods=['POST'])
    @admin_required
    def admin_logout():
        session.clear()
        flash('Вы вышли из админ-панели.', 'info')
        return redirect(url_for('login'))

    # ---------------- НОМЕРА ----------------
    @app.route('/admin/rooms')
    @admin_required
    def admin_rooms():
        sync_room_statuses()
        with db_session() as conn:
            rooms = conn.execute("""
                SELECT n.*,
                       (SELECT c.Фамилия || ' ' || c.Имя FROM Бронирования b JOIN Клиенты c ON c.ID_Клиента=b.ID_Клиента
                        WHERE b.ID_Номера=n.ID_Номера AND b.Статус IN ('Подтверждено','Заселен')
                        ORDER BY b.Дата_заезда LIMIT 1) next_guest,
                       (SELECT b.Дата_заезда FROM Бронирования b
                        WHERE b.ID_Номера=n.ID_Номера AND b.Статус IN ('Подтверждено','Заселен')
                        ORDER BY b.Дата_заезда LIMIT 1) next_checkin
                FROM Номера n ORDER BY CAST(n.Номер_Комнаты AS INTEGER), n.Номер_Комнаты
            """).fetchall()
            return render_template('admin/rooms.html', rooms=rooms)

    @app.route('/admin/room/add', methods=['GET', 'POST'])
    @admin_required
    def admin_room_add():
        if request.method == 'POST':
            try:
                with db_session(commit=True) as conn:
                    room_number = request.form.get('room_number','').strip()
                    category = request.form.get('category','').strip()
                    capacity = int(request.form.get('capacity', 1))
                    price = float(request.form.get('price', 0))
                    floor = int(request.form.get('floor', 1))
                    if not room_number or capacity < 1 or price <= 0 or floor < 1:
                        raise ValueError('Проверьте данные номера.')
                    if conn.execute('SELECT 1 FROM Номера WHERE Номер_Комнаты=?', (room_number,)).fetchone():
                        raise ValueError('Номер с таким номером комнаты уже существует.')
                    room_id = next_id(conn, 'Номера', 'RM', 'ID_Номера')
                    conn.execute("""
                        INSERT INTO Номера (ID_Номера,Номер_Комнаты,Категория,Вместимость,Цена_за_сутки,Статус,Этаж)
                        VALUES (?,?,?,?,?,'Свободен',?)
                    """, (room_id, room_number, category, capacity, price, floor))
                    from hotel_logic import log_action
                    log_action('Создан номер', room_id, f'Номер {room_number}')
                    flash(f'Номер {room_number} добавлен.', 'success')
                    return redirect(url_for('admin_rooms'))
            except Exception as e:
                flash(_db_error_message(e), 'danger')
        return render_template('admin/room_form.html', room=None)

    @app.route('/admin/room/edit/<string:room_id>', methods=['GET', 'POST'])
    @admin_required
    def admin_room_edit(room_id):
        conn = get_db()
        try:
            room = conn.execute('SELECT * FROM Номера WHERE ID_Номера=?', (room_id,)).fetchone()
            if not room:
                flash('Номер не найден.', 'danger'); return redirect(url_for('admin_rooms'))
            if request.method == 'POST':
                room_number = request.form.get('room_number','').strip()
                category = request.form.get('category','').strip()
                capacity = int(request.form.get('capacity', 1))
                price = float(request.form.get('price', 0))
                floor = int(request.form.get('floor', 1))
                duplicate = conn.execute('SELECT 1 FROM Номера WHERE Номер_Комнаты=? AND ID_Номера<>?', (room_number, room_id)).fetchone()
                if duplicate: raise ValueError('Такой номер комнаты уже существует.')
                conn.execute("""UPDATE Номера SET Номер_Комнаты=?,Категория=?,Вместимость=?,Цена_за_сутки=?,Этаж=? WHERE ID_Номера=?""",
                             (room_number, category, capacity, price, floor, room_id))
                conn.commit(); from hotel_logic import log_action; log_action('Изменён номер', room_id, room_number); flash(f'Номер {room_number} обновлён.', 'success')
                return redirect(url_for('admin_rooms'))
            return render_template('admin/room_form.html', room=room)
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger'); return redirect(url_for('admin_rooms'))
        finally:
            conn.close()

    @app.route('/admin/room/delete/<string:room_id>', methods=['POST'])
    @admin_required
    def admin_room_delete(room_id):
        try:
            with db_session(commit=True) as conn:
                has_history = conn.execute('SELECT 1 FROM Бронирования WHERE ID_Номера=? LIMIT 1', (room_id,)).fetchone()
                if has_history:
                    flash('Номер нельзя удалить: у него есть история бронирований. Отредактируйте его или оставьте в фонде.', 'danger')
                else:
                    conn.execute('DELETE FROM Номера WHERE ID_Номера=?', (room_id,))
                    from hotel_logic import log_action
                    log_action('Удалён номер', room_id, 'Удалён из номерного фонда')
                    flash('Номер удалён.', 'success')
        except Exception as e:
            flash(_db_error_message(e), 'danger')
        return redirect(url_for('admin_rooms'))

    # ---------------- БРОНИРОВАНИЯ ----------------
    @app.route('/admin/bookings')
    @admin_required
    def admin_bookings():
        sync_room_statuses()
        status = request.args.get('status','').strip()
        search = request.args.get('search','').strip()
        date_from = request.args.get('date_from','').strip()
        date_to = request.args.get('date_to','').strip()
        with db_session() as conn:
            query = """
                SELECT b.*, n.Номер_Комнаты, n.Категория, n.Цена_за_сутки,
                       c.Фамилия, c.Имя, c.Телефон,
                       s.Оплачено, s.Сумма_проживание
                FROM Бронирования b
                JOIN Номера n ON n.ID_Номера=b.ID_Номера
                JOIN Клиенты c ON c.ID_Клиента=b.ID_Клиента
                LEFT JOIN Счета s ON s.ID_Бронирования=b.ID_Бронирования
                WHERE 1=1
            """
            params=[]
            if status: query += ' AND b.Статус=?'; params.append(status)
            if search:
                query += ' AND (b.ID_Бронирования LIKE ? OR n.Номер_Комнаты LIKE ? OR c.Фамилия LIKE ? OR c.Имя LIKE ? OR c.Телефон LIKE ?)'
                params += [f'%{search}%']*5
            if date_from: query += ' AND b.Дата_заезда >= ?'; params.append(date_from)
            if date_to: query += ' AND b.Дата_заезда <= ?'; params.append(date_to)
            query += ' ORDER BY b.Дата_заезда DESC, b.Код DESC'
            bookings = conn.execute(query, params).fetchall()
            return render_template('admin/bookings.html', bookings=bookings, selected_status=status, search=search, date_from=date_from, date_to=date_to)

    @app.route('/admin/booking/add', methods=['GET','POST'])
    @admin_required
    def admin_booking_add():
        conn = get_db()
        try:
            clients = conn.execute('SELECT * FROM Клиенты ORDER BY Фамилия, Имя').fetchall()
            rooms = conn.execute('SELECT * FROM Номера ORDER BY CAST(Номер_Комнаты AS INTEGER), Номер_Комнаты').fetchall()
            services = conn.execute('SELECT * FROM Услуги WHERE Активна=1 ORDER BY Название').fetchall()
            if request.method == 'POST':
                client_id = request.form.get('client_id','')
                room_id = request.form.get('room_id','')
                check_in = request.form.get('check_in','')
                check_out = request.form.get('check_out','')
                guests = request.form.get('guests',1,type=int)
                status = request.form.get('status','Подтверждено')
                selected_services = request.form.getlist('services')
                if status not in STATUSES: raise ValueError('Недопустимый статус.')
                start, end = _date(check_in), _date(check_out)
                if end <= start: raise ValueError('Дата выезда должна быть позже даты заезда.')
                today = datetime.now().date()
                if start < today and status in ACTIVE: raise ValueError('Активную бронь нельзя создавать задним числом.')
                if status == 'Заселен' and not (start <= today < end): raise ValueError('Статус «Заселен» можно установить только на текущий период проживания.')
                if status == 'Завершено' and end > today: raise ValueError('Завершённая бронь должна иметь дату выезда в прошлом.')
                client = conn.execute('SELECT 1 FROM Клиенты WHERE ID_Клиента=?',(client_id,)).fetchone()
                if not client: raise ValueError('Гость не найден.')
                room = conn.execute('SELECT * FROM Номера WHERE ID_Номера=?',(room_id,)).fetchone()
                if not room: raise ValueError('Номер не найден.')
                if guests < 1 or guests > room['Вместимость']: raise ValueError(f"Вместимость номера: {room['Вместимость']}.")
                conn.execute('BEGIN IMMEDIATE')
                if status in ACTIVE and booking_conflicts(conn, room_id, check_in, check_out):
                    conn.rollback()
                    raise ValueError('Номер уже занят на выбранный период.')
                total, nights = booking_total(conn, room_id, check_in, check_out)
                selected_rows = []
                for sid in selected_services:
                    sr = conn.execute('SELECT * FROM Услуги WHERE ID_Услуги=? AND Активна=1',(sid,)).fetchone()
                    if sr:
                        selected_rows.append(sr)
                        total += float(sr['Цена'])
                booking_id = next_id(conn,'Бронирования','BR','ID_Бронирования')
                invoice_id = next_id(conn,'Счета','INV','ID_Счета')
                prepayment = round(total*0.30,2)
                conn.execute("""INSERT INTO Бронирования(ID_Бронирования,ID_Клиента,ID_Номера,ID_Сотрудника,Дата_бронирования,Дата_заезда,Дата_выезда,Количество_гостей,Статус,Предоплата)
                    VALUES(?,?,?,?,date('now'),?,?,?,?,?)""",(booking_id,client_id,room_id,session.get('admin_id'),check_in,check_out,guests,status,prepayment))
                conn.execute("INSERT INTO Счета(ID_Счета,ID_Бронирования,Дата_выставления,Сумма_проживание,Оплачено) VALUES(?,?,date('now'),?,0)",(invoice_id,booking_id,total))
                for sr in selected_rows:
                    conn.execute('INSERT INTO Бронирование_Услуги(ID_Бронирования,ID_Услуги,Количество,Цена) VALUES(?,?,1,?)',(booking_id,sr['ID_Услуги'],sr['Цена']))
                conn.commit(); sync_room_statuses(); from hotel_logic import log_action; log_action('Создано бронирование', booking_id, 'Бронь создана администратором'); flash(f'Бронь {booking_id} создана.', 'success')
                return redirect(url_for('admin_bookings'))
            return render_template('admin/booking_form.html', clients=clients, rooms=rooms, services=services, booking=None)
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger')
            return render_template('admin/booking_form.html', clients=clients, rooms=rooms, services=services, booking=None)
        finally: conn.close()

    @app.route('/admin/booking/update/<string:booking_id>', methods=['POST'])
    @admin_required
    def admin_booking_update(booking_id):
        new_status = request.form.get('status','')
        conn = get_db()
        try:
            booking = conn.execute('SELECT * FROM Бронирования WHERE ID_Бронирования=?',(booking_id,)).fetchone()
            if not booking: raise ValueError('Бронирование не найдено.')
            if new_status not in STATUSES: raise ValueError('Недопустимый статус.')
            if new_status == 'Заселен':
                today = datetime.now().date()
                if not (_date(booking['Дата_заезда']) <= today < _date(booking['Дата_выезда'])):
                    raise ValueError('Заселить можно только в период проживания.')
            if new_status in ACTIVE and _date(booking['Дата_заезда']) < datetime.now().date():
                raise ValueError('Нельзя активировать бронь с датой заезда в прошлом.')
            if new_status in ACTIVE and booking_conflicts(conn, booking['ID_Номера'], booking['Дата_заезда'], booking['Дата_выезда'], booking_id):
                raise ValueError('Нельзя активировать бронь: даты пересекаются с другой активной бронью.')
            conn.execute('UPDATE Бронирования SET Статус=? WHERE ID_Бронирования=?',(new_status,booking_id))
            conn.commit(); sync_room_statuses(); from hotel_logic import log_action; log_action('Изменён статус бронирования', booking_id, new_status); flash(f'Статус {booking_id}: {new_status}.', 'success')
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger')
        finally: conn.close()
        return redirect(url_for('admin_bookings'))

    @app.route('/admin/invoice/pay/<string:booking_id>', methods=['POST'])
    @admin_required
    def admin_invoice_pay(booking_id):
        method = request.form.get('payment_method','Карта')
        conn = get_db()
        try:
            booking = conn.execute("SELECT Статус FROM Бронирования WHERE ID_Бронирования=?", (booking_id,)).fetchone()
            if not booking:
                raise ValueError('Бронирование не найдено.')
            if booking['Статус'] == 'Отменено':
                raise ValueError('Нельзя отметить оплату по отменённой брони.')
            conn.execute("UPDATE Счета SET Оплачено=1, Способ_оплаты=?, Дата_оплаты=date('now') WHERE ID_Бронирования=?",(method,booking_id))
            conn.commit(); from hotel_logic import log_action; log_action('Отмечена оплата', booking_id, method); flash('Оплата отмечена.', 'success')
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger')
        finally: conn.close()
        return redirect(url_for('admin_bookings'))

    # ---------------- ГОСТИ ----------------
    @app.route('/admin/clients')
    @admin_required
    def admin_clients():
        search=request.args.get('search','').strip()
        conn=get_db()
        try:
            if search:
                clients=conn.execute("SELECT * FROM Клиенты WHERE Фамилия LIKE ? OR Имя LIKE ? OR Телефон LIKE ? ORDER BY Фамилия,Имя",(f'%{search}%',)*3).fetchall()
            else:
                clients=conn.execute('SELECT * FROM Клиенты ORDER BY Фамилия,Имя').fetchall()
            return render_template('admin/clients.html',clients=clients,search=search)
        finally: conn.close()

    @app.route('/admin/client/add', methods=['GET','POST'])
    @admin_required
    def admin_client_add():
        conn=get_db()
        try:
            if request.method=='POST':
                last=request.form.get('last_name','').strip(); first=request.form.get('first_name','').strip(); middle=request.form.get('middle_name','').strip(); phone=request.form.get('phone','').strip(); password=request.form.get('password','')
                if not last or not first or not phone: raise ValueError('Фамилия, имя и телефон обязательны.')
                if conn.execute('SELECT 1 FROM Клиенты WHERE Телефон=?',(phone,)).fetchone(): raise ValueError('Гость с таким телефоном уже существует.')
                client_id=next_id(conn,'Клиенты','CL','ID_Клиента')
                conn.execute('INSERT INTO Клиенты(ID_Клиента,Фамилия,Имя,Отчество,Телефон,Дата_рождения,Адрес) VALUES(?,?,?,?,?,?,?)',(client_id,last,first,middle,phone,request.form.get('birth_date') or None,request.form.get('address') or None))
                validate_password(password)
                conn.execute('INSERT INTO Пользователи(ID_Клиента,Логин,Пароль,Роль) VALUES(?,?,?,?)',(client_id,phone,hash_password(password),'client'))
                conn.commit(); from hotel_logic import log_action; log_action('Создан гость', client_id, 'Добавлен администратором'); flash(f'Гость {client_id} добавлен.','success'); return redirect(url_for('admin_clients'))
            return render_template('admin/client_form.html',client=None)
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger'); return render_template('admin/client_form.html',client=None)
        finally: conn.close()

    @app.route('/admin/client/edit/<string:client_id>', methods=['GET','POST'])
    @admin_required
    def admin_client_edit(client_id):
        conn=get_db()
        try:
            client=conn.execute('SELECT * FROM Клиенты WHERE ID_Клиента=?',(client_id,)).fetchone()
            if not client: flash('Гость не найден.','danger'); return redirect(url_for('admin_clients'))
            if request.method=='POST':
                phone=request.form.get('phone','').strip()
                duplicate=conn.execute('SELECT 1 FROM Клиенты WHERE Телефон=? AND ID_Клиента<>?',(phone,client_id)).fetchone()
                if duplicate: raise ValueError('Этот телефон уже используется.')
                conn.execute("UPDATE Клиенты SET Фамилия=?,Имя=?,Отчество=?,Телефон=?,Дата_рождения=?,Адрес=? WHERE ID_Клиента=?",(request.form.get('last_name'),request.form.get('first_name'),request.form.get('middle_name'),phone,request.form.get('birth_date') or None,request.form.get('address') or None,client_id))
                conn.execute("UPDATE Пользователи SET Логин=? WHERE ID_Клиента=?",(phone,client_id))
                if request.form.get('password'):
                    validate_password(request.form.get('password'))
                    conn.execute("UPDATE Пользователи SET Пароль=? WHERE ID_Клиента=?",(hash_password(request.form.get('password')),client_id))
                conn.commit(); from hotel_logic import log_action; log_action('Изменены данные гостя', client_id, 'Изменение администратором'); flash('Данные гостя обновлены.','success'); return redirect(url_for('admin_client_detail',client_id=client_id))
            return render_template('admin/client_form.html',client=client)
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger'); return redirect(url_for('admin_clients'))
        finally: conn.close()

    @app.route('/admin/client/delete/<string:client_id>', methods=['POST'])
    @admin_required
    def admin_client_delete(client_id):
        conn=get_db()
        try:
            if conn.execute("SELECT 1 FROM Бронирования WHERE ID_Клиента=? LIMIT 1",(client_id,)).fetchone():
                raise ValueError('Гостя нельзя удалить: у него есть история бронирований.')
            conn.execute('DELETE FROM Уведомления WHERE ID_Клиента=?',(client_id,))
            conn.execute('DELETE FROM Использованные_промокоды WHERE ID_Клиента=?',(client_id,))
            conn.execute('DELETE FROM Пользователи WHERE ID_Клиента=?',(client_id,))
            conn.execute('DELETE FROM Клиенты WHERE ID_Клиента=?',(client_id,))
            conn.commit(); from hotel_logic import log_action; log_action('Удалён гость', client_id, 'Удалён администратором'); flash('Гость удалён.','success')
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger')
        finally: conn.close()
        return redirect(url_for('admin_clients'))

    @app.route('/admin/client/<string:client_id>')
    @admin_required
    def admin_client_detail(client_id):
        conn=get_db()
        try:
            client=conn.execute('SELECT * FROM Клиенты WHERE ID_Клиента=?',(client_id,)).fetchone()
            bookings=conn.execute("""SELECT b.*,n.Номер_Комнаты,n.Категория,s.Сумма_проживание,s.Оплачено FROM Бронирования b JOIN Номера n ON n.ID_Номера=b.ID_Номера LEFT JOIN Счета s ON s.ID_Бронирования=b.ID_Бронирования WHERE b.ID_Клиента=? ORDER BY b.Дата_заезда DESC""",(client_id,)).fetchall()
            if not client: flash('Гость не найден.','danger'); return redirect(url_for('admin_clients'))
            return render_template('admin/client_detail.html',client=client,bookings=bookings)
        finally: conn.close()

    # ---------------- ОТЧЁТЫ ----------------
    @app.route('/admin/reports')
    @admin_required
    def admin_reports():
        conn=get_db()
        try:
            room_stats=conn.execute("SELECT Категория,COUNT(*) count,AVG(Цена_за_сутки) avg_price,SUM(CASE WHEN Статус='Свободен' THEN 1 ELSE 0 END) free FROM Номера GROUP BY Категория ORDER BY Категория").fetchall()
            monthly_stats=conn.execute("SELECT strftime('%Y-%m',Дата_заезда) month,COUNT(*) count,COALESCE(SUM(s.Сумма_проживание),0) revenue FROM Бронирования b LEFT JOIN Счета s ON s.ID_Бронирования=b.ID_Бронирования WHERE b.Статус!='Отменено' GROUP BY month ORDER BY month DESC LIMIT 12").fetchall()
            financial=conn.execute("SELECT COUNT(*) total_bookings,COALESCE(SUM(s.Сумма_проживание),0) total_amount,COALESCE(SUM(CASE WHEN s.Оплачено=1 THEN s.Сумма_проживание ELSE 0 END),0) paid_amount FROM Бронирования b LEFT JOIN Счета s ON s.ID_Бронирования=b.ID_Бронирования WHERE b.Статус!='Отменено'").fetchone()
            return render_template('admin/reports.html',room_stats=room_stats,monthly_stats=monthly_stats,financial=financial)
        finally: conn.close()

    # ---------------- ОПЕРАЦИОННЫЙ КАЛЕНДАРЬ ----------------
    @app.route('/admin/calendar')
    @admin_required
    def admin_calendar():
        sync_room_statuses()
        from datetime import timedelta
        start_str = request.args.get('start') or datetime.now().strftime('%Y-%m-%d')
        try:
            start = _date(start_str)
        except ValueError:
            start = datetime.now().date()
        days = [start + timedelta(days=i) for i in range(14)]
        conn = get_db()
        try:
            rooms = conn.execute("SELECT * FROM Номера ORDER BY CAST(Номер_Комнаты AS INTEGER), Номер_Комнаты").fetchall()
            bookings = conn.execute("""SELECT b.ID_Бронирования,b.ID_Номера,b.Дата_заезда,b.Дата_выезда,b.Статус,c.Фамилия,c.Имя
                FROM Бронирования b JOIN Клиенты c ON c.ID_Клиента=b.ID_Клиента
                WHERE b.Статус IN ('Подтверждено','Заселен')
                  AND b.Дата_выезда > ? AND b.Дата_заезда < ?""",
                (days[0].strftime('%Y-%m-%d'), (days[-1] + timedelta(days=1)).strftime('%Y-%m-%d'))).fetchall()
            return render_template('admin/calendar.html', rooms=rooms, bookings=bookings, days=days, start=start)
        finally:
            conn.close()

    @app.route('/admin/checkin/<string:booking_id>', methods=['POST'])
    @admin_required
    def admin_checkin(booking_id):
        conn = get_db()
        try:
            booking = conn.execute("SELECT * FROM Бронирования WHERE ID_Бронирования=?", (booking_id,)).fetchone()
            if not booking: raise ValueError('Бронирование не найдено.')
            today = datetime.now().date()
            if not (_date(booking['Дата_заезда']) <= today < _date(booking['Дата_выезда'])):
                raise ValueError('Заселение доступно только в период проживания.')
            if booking_conflicts(conn, booking['ID_Номера'], booking['Дата_заезда'], booking['Дата_выезда'], booking_id):
                raise ValueError('Номер пересекается с другой активной бронью.')
            conn.execute("UPDATE Бронирования SET Статус='Заселен', ID_Сотрудника=? WHERE ID_Бронирования=?", (session.get('admin_id'), booking_id))
            conn.commit()
            from hotel_logic import log_action
            log_action('Заселение', booking_id, f'Номер {booking["ID_Номера"]}')
            sync_room_statuses(); flash(f'Гость по брони {booking_id} заселён.', 'success')
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger')
        finally: conn.close()
        return redirect(url_for('admin_bookings'))

    @app.route('/admin/checkout/<string:booking_id>', methods=['POST'])
    @admin_required
    def admin_checkout(booking_id):
        conn = get_db()
        try:
            booking = conn.execute("SELECT * FROM Бронирования WHERE ID_Бронирования=?", (booking_id,)).fetchone()
            if not booking: raise ValueError('Бронирование не найдено.')
            if booking['Статус'] != 'Заселен': raise ValueError('Выселить можно только уже заселённого гостя.')
            conn.execute("UPDATE Бронирования SET Статус='Завершено', ID_Сотрудника=? WHERE ID_Бронирования=?", (session.get('admin_id'), booking_id))
            conn.commit()
            from hotel_logic import log_action
            log_action('Выселение', booking_id, f'Номер {booking["ID_Номера"]}')
            sync_room_statuses(); flash(f'Гость по брони {booking_id} выселен.', 'success')
        except Exception as e:
            conn.rollback(); flash(_db_error_message(e), 'danger')
        finally: conn.close()
        return redirect(url_for('admin_bookings'))

    # ---------------- ФИНАНСЫ ----------------
    @app.route('/admin/finance')
    @admin_required
    def admin_finance():
        conn = get_db()
        try:
            totals = conn.execute("""SELECT COUNT(*) bookings,
                COALESCE(SUM(CASE WHEN b.Статус!='Отменено' THEN s.Сумма_проживание ELSE 0 END),0) revenue,
                COALESCE(SUM(CASE WHEN b.Статус!='Отменено' AND s.Оплачено=1 THEN s.Сумма_проживание ELSE 0 END),0) paid,
                COALESCE(SUM(CASE WHEN b.Статус!='Отменено' AND s.Оплачено=0 THEN s.Сумма_проживание ELSE 0 END),0) debt
                FROM Бронирования b LEFT JOIN Счета s ON s.ID_Бронирования=b.ID_Бронирования""").fetchone()
            by_payment = conn.execute("""SELECT COALESCE(Способ_оплаты,'Не указан') method, COUNT(*) count, COALESCE(SUM(Сумма_проживание),0) amount
                FROM Счета WHERE Оплачено=1 GROUP BY Способ_оплаты ORDER BY amount DESC""").fetchall()
            by_month = conn.execute("""SELECT strftime('%Y-%m', b.Дата_заезда) month, COUNT(*) count, COALESCE(SUM(s.Сумма_проживание),0) amount
                FROM Бронирования b LEFT JOIN Счета s ON s.ID_Бронирования=b.ID_Бронирования
                WHERE b.Статус!='Отменено' GROUP BY month ORDER BY month DESC LIMIT 12""").fetchall()
            return render_template('admin/finance.html', totals=totals, by_payment=by_payment, by_month=by_month)
        finally: conn.close()

    # ---------------- ЖУРНАЛ ДЕЙСТВИЙ ----------------
    @app.route('/admin/journal')
    @admin_required
    def admin_journal():
        search = request.args.get('search','').strip()
        conn = get_db()
        try:
            if search:
                rows = conn.execute("SELECT * FROM Журнал_действий WHERE Пользователь LIKE ? OR Действие LIKE ? OR Объект LIKE ? OR Детали LIKE ? ORDER BY ID DESC LIMIT 300", tuple([f'%{search}%']*4)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM Журнал_действий ORDER BY ID DESC LIMIT 300").fetchall()
            return render_template('admin/journal.html', rows=rows, search=search)
        finally: conn.close()

    @app.route('/admin/reports/export.csv')
    @admin_required
    def admin_reports_export():
        MAX_EXPORT_ROWS = 5000
        conn=get_db()
        try:
            rows=conn.execute("""SELECT b.ID_Бронирования,c.Фамилия||' '||c.Имя guest,n.Номер_Комнаты,b.Дата_заезда,b.Дата_выезда,b.Количество_гостей,b.Статус,COALESCE(s.Сумма_проживание,0) total,CASE WHEN s.Оплачено=1 THEN 'Да' ELSE 'Нет' END paid
                FROM Бронирования b JOIN Клиенты c ON c.ID_Клиента=b.ID_Клиента JOIN Номера n ON n.ID_Номера=b.ID_Номера LEFT JOIN Счета s ON s.ID_Бронирования=b.ID_Бронирования ORDER BY b.Дата_заезда DESC LIMIT ?""", (MAX_EXPORT_ROWS,)).fetchall()
            out=io.StringIO(); writer=csv.writer(out, delimiter=';'); writer.writerow(['Бронь','Гость','Номер','Заезд','Выезд','Гостей','Статус','Сумма','Оплачено'])
            for r in rows: writer.writerow([safe_csv_value(v) for v in r])
            return Response('﻿'+out.getvalue(), mimetype='text/csv; charset=utf-8', headers={'Content-Disposition':'attachment; filename=uyut_report.csv'})
        finally: conn.close()
