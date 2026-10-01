"""Авторизация, регистрация, профиль гостя и создание бронирований."""
from flask import render_template, request, redirect, url_for, flash, session, current_app
from datetime import datetime, timedelta
import hashlib
from urllib.parse import urlparse
from db import get_db
from utils import sync_room_statuses, next_id, booking_total
from constants import PREPAYMENT_RATE
from security import login_required
from services.passwords import password_matches, hash_password
from services.auth import find_user_by_login
from services.booking import (
    BookingError, parse_stay_dates, validate_guests, calc_stay_total,
    resolve_promo, create_confirmed_booking, room_is_available,
)

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15


def ensure_login_attempts_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Попытки_входа (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Идентификатор TEXT NOT NULL,
            IP TEXT NOT NULL,
            Неудачные_попытки INTEGER NOT NULL DEFAULT 0,
            Заблокировано_до TEXT
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_login_attempts_identity_ip
        ON Попытки_входа(Идентификатор, IP)
    """)
    conn.commit()


def get_login_attempt_state(conn, identifier, ip):
    row = conn.execute(
        "SELECT Неудачные_попытки, Заблокировано_до FROM Попытки_входа WHERE Идентификатор=? AND IP=?",
        (identifier, ip)
    ).fetchone()
    if not row:
        return 0, None
    return int(row[0] or 0), row[1]


def record_failed_login(conn, identifier, ip):
    now = datetime.now()
    attempts, _ = get_login_attempt_state(conn, identifier, ip)
    attempts += 1
    locked_until = None
    if attempts >= LOGIN_MAX_ATTEMPTS:
        locked_until = (now + timedelta(minutes=LOGIN_LOCK_MINUTES)).isoformat(timespec="seconds")
        attempts = 0
    conn.execute("""
        INSERT INTO Попытки_входа(Идентификатор, IP, Неудачные_попытки, Заблокировано_до)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(Идентификатор, IP) DO UPDATE SET
            Неудачные_попытки=excluded.Неудачные_попытки,
            Заблокировано_до=excluded.Заблокировано_до
    """, (identifier, ip, attempts, locked_until))
    conn.commit()
    return attempts, locked_until


def clear_login_attempts(conn, identifier, ip):
    conn.execute("DELETE FROM Попытки_входа WHERE Идентификатор=? AND IP=?", (identifier, ip))
    conn.commit()


def login_is_locked(conn, identifier, ip):
    attempts, locked_until = get_login_attempt_state(conn, identifier, ip)
    if not locked_until:
        return False, attempts, 0
    try:
        until = datetime.fromisoformat(locked_until)
    except ValueError:
        clear_login_attempts(conn, identifier, ip)
        return False, 0, 0
    remaining = int((until - datetime.now()).total_seconds())
    if remaining <= 0:
        clear_login_attempts(conn, identifier, ip)
        return False, 0, 0
    return True, attempts, remaining


def register_account_routes(app):

    # ---------------- РЕГИСТРАЦИЯ ----------------
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            try:
                last_name = request.form['last_name']
                first_name = request.form['first_name']
                middle_name = request.form.get('middle_name', '')
                phone = request.form['phone']
                birth_date = request.form.get('birth_date', '')
                address = request.form.get('address', '')
                password = request.form['password']
                confirm_password = request.form['confirm_password']

                if not all([last_name, first_name, phone, password]):
                    flash('Заполните все обязательные поля', 'danger')
                    return render_template('register.html')

                if password != confirm_password:
                    flash('Пароли не совпадают', 'danger')
                    return render_template('register.html')

                if len(password) < 12:
                    flash('Пароль должен содержать минимум 12 символов', 'danger')
                    return render_template('register.html')

                conn = get_db()
                cursor = conn.cursor()

                conn.execute('BEGIN IMMEDIATE')
                cursor.execute("SELECT ID_Клиента FROM Клиенты WHERE Телефон = ?", (phone,))
                if cursor.fetchone():
                    # Не раскрываем существование учётной записи (user enumeration).
                    conn.rollback()
                    conn.close()
                    current_app.logger.info('Регистрация отклонена: телефон уже занят')
                    flash(
                        'Не удалось завершить регистрацию. Проверьте введённые данные '
                        'или войдите, если аккаунт уже есть.',
                        'danger',
                    )
                    return render_template('register.html')

                client_id = next_id(conn, 'Клиенты', 'CL', 'ID_Клиента')

                cursor.execute("""
                    INSERT INTO Клиенты (ID_Клиента, Фамилия, Имя, Отчество, Телефон, Дата_рождения, Адрес)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (client_id, last_name, first_name, middle_name, phone, birth_date or None, address or None))

                cursor.execute("""
                    INSERT INTO Пользователи (ID_Клиента, Логин, Пароль, Роль)
                    VALUES (?, ?, ?, ?)
                """, (client_id, phone, hash_password(password), 'client'))

                conn.commit()
                conn.close()
                from hotel_logic import log_action
                log_action('Регистрация гостя', client_id, 'Создана учётная запись')

                flash('Регистрация успешна! Теперь вы можете войти в систему.', 'success')
                return redirect(url_for('login'))

            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    current_app.logger.debug('rollback after registration error failed', exc_info=True)
                try:
                    conn.close()
                except Exception:
                    current_app.logger.debug('close after registration error failed', exc_info=True)
                current_app.logger.exception('Ошибка регистрации')
                flash('Не удалось завершить регистрацию. Проверьте введённые данные.', 'danger')
                return render_template('register.html')

        return render_template('register.html')

    # ---------------- ВХОД ----------------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Единая авторизация: один экран для гостя и администратора."""
        conn = get_db()
        ensure_login_attempts_table(conn)
        if request.method == 'POST':
            try:
                login_value = request.form.get('login', '').strip()
                password = request.form.get('password', '')
                # Bind lockout to real client IP + identifier so one attacker cannot
                # lock out all users. Prefer remote_addr; X-Forwarded-For is only
                # trusted when ProxyFix is configured with known proxies.
                client_ip = (request.remote_addr or 'unknown').strip()
                identifier = ''.join(ch for ch in login_value if ch.isdigit()) if any(ch.isdigit() for ch in login_value) else login_value.casefold()
                locked, _, lock_seconds = login_is_locked(conn, identifier, client_ip)
                if locked:
                    flash('Слишком много неудачных попыток. Попробуйте позже.', 'danger')
                    conn.close()
                    return render_template('login.html')

                # Для телефона допускаем ввод с пробелами, скобками и дефисами.
                normalized = ''.join(ch for ch in login_value if ch.isdigit() or ch == '+')
                user = find_user_by_login(conn, login_value, normalized)

                # Проверяем хэш. Старый пароль из учебной БД при успешном входе автоматически хэшируется.
                if user and password_matches(user['Пароль'], password):
                    clear_login_attempts(conn, identifier, client_ip)
                    from hotel_logic import log_action
                    log_action('Успешный вход', user['ID_Клиента'], f"Роль: {user['Роль']}")
                    session.clear()
                    session.permanent = True
                    session['user_id'] = user['ID_Клиента']
                    session['user_role'] = user['Роль']
                    # Привязка сессии к актуальному хэшу пароля: смена пароля
                    # инвалидирует все остальные сессии этого пользователя.
                    stored_pw = user['Пароль'] or ''
                    session['pwd_sig'] = stored_pw[:64] if stored_pw else ''

                    if user['Роль'] == 'admin':
                        name = ((user['Имя'] or '') + ' ' + (user['Фамилия'] or '')).strip() or 'Администратор'
                        session['user_name'] = name
                        session['admin_id'] = user['ID_Клиента']
                        session['admin_name'] = 'Администратор'
                        flash('Добро пожаловать в панель администратора!', 'success')
                        return redirect(url_for('admin_dashboard'))

                    name = f"{user['Фамилия'] or ''} {user['Имя'] or ''}".strip() or 'Гость'
                    session['user_name'] = name
                    session['client_id'] = user['ID_Клиента']
                    session['client_name'] = name
                    flash(f'Добро пожаловать, {user["Имя"] or "гость"}!', 'success')
                    next_page = request.args.get('next', '')
                    # Prevent open redirects: accept only local absolute paths.
                    if next_page and next_page.startswith('/') and not next_page.startswith('//') and '\\\\' not in next_page and '\\' not in next_page:
                        parsed = urlparse(next_page)
                        safe_next = parsed.path + (('?' + parsed.query) if parsed.query else '') + (('#' + parsed.fragment) if parsed.fragment else '')
                    else:
                        safe_next = url_for('index')
                    return redirect(safe_next)

                attempts, locked_until = record_failed_login(conn, identifier, client_ip)
                current_app.logger.warning('Неудачная попытка входа; identifier_hash=%s; attempts=%s', hashlib.sha256(identifier.encode('utf-8')).hexdigest()[:16], attempts)
                try:
                    from hotel_logic import log_action
                    log_action('Неудачная попытка входа', 'Авторизация', f'Счётчик попыток: {attempts}')
                except Exception:
                    current_app.logger.exception('Не удалось записать аудит неудачного входа')
                if locked_until:
                    flash('Слишком много неудачных попыток. Попробуйте позже.', 'danger')
                else:
                    # Единое сообщение без счётчика попыток и без намёка
                    # на существование учётной записи.
                    flash('Неверные данные для входа.', 'danger')
            except Exception as e:
                flash('Не удалось выполнить вход', 'danger')

        conn.close()
        return render_template('login.html')

    # ---------------- ВЫХОД ----------------
    @app.route('/logout', methods=['POST'])
    def logout():
        try:
            from hotel_logic import log_action
            log_action('Выход из системы', session.get('user_id', 'unknown'), 'Пользователь завершил сессию')
        except Exception:
            current_app.logger.exception('Не удалось записать аудит выхода')
        session.clear()
        flash('Вы вышли из системы', 'info')
        return redirect(url_for('index'))

    # ---------------- ЛИЧНЫЙ КАБИНЕТ ----------------
    @app.route('/profile')
    @login_required
    def profile():
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Клиенты WHERE ID_Клиента = ?", (session['client_id'],))
            client = cursor.fetchone()

            if not client:
                flash('Клиент не найден', 'danger')
                return redirect(url_for('index'))

            # FIX #3: реальная сумма берётся из счёта (учитывает услуги и скидку
            # по промокоду), а не вычисляется как «ночи × цена за сутки».
            cursor.execute("""
                SELECT b.*, n.Номер_Комнаты, n.Категория, n.Цена_за_сутки,
                       CAST(JULIANDAY(b.Дата_выезда) - JULIANDAY(b.Дата_заезда) AS INTEGER) AS days_count,
                       s.Сумма_проживание AS invoice_total,
                       s.Оплачено         AS invoice_paid,
                       COALESCE((
                           SELECT SUM(bs.Количество * bs.Цена)
                           FROM Бронирование_Услуги bs
                           WHERE bs.ID_Бронирования = b.ID_Бронирования
                       ), 0) AS services_total
                FROM Бронирования b
                JOIN Номера n ON b.ID_Номера = n.ID_Номера
                LEFT JOIN Счета s ON s.ID_Бронирования = b.ID_Бронирования
                WHERE b.ID_Клиента = ?
                ORDER BY b.Дата_заезда DESC
            """, (session['client_id'],))

            bookings = cursor.fetchall()
            bookings_with_total = []
            for booking in bookings:
                booking_dict = dict(booking)
                days = booking_dict.get('days_count', 0) or 1
                # Приоритет: сумма счёта → fallback на «ночи × цена».
                if booking_dict.get('invoice_total') is not None:
                    booking_dict['total_price'] = float(booking_dict['invoice_total'])
                else:
                    booking_dict['total_price'] = days * float(booking_dict.get('Цена_за_сутки', 0))
                booking_dict['services_total'] = float(booking_dict.get('services_total') or 0)
                booking_dict['is_paid'] = bool(booking_dict.get('invoice_paid'))
                if booking_dict.get('Дата_заезда'):
                    booking_dict['Дата_заезда'] = str(booking_dict['Дата_заезда'])
                if booking_dict.get('Дата_выезда'):
                    booking_dict['Дата_выезда'] = str(booking_dict['Дата_выезда'])
                bookings_with_total.append(booking_dict)

            conn.close()
            return render_template('profile.html', client=client, bookings=bookings_with_total)

        except Exception as e:
            current_app.logger.exception('Ошибка загрузки профиля')
            flash('Не удалось загрузить профиль. Попробуйте ещё раз.', 'danger')
            return redirect(url_for('index'))

    # ---------------- СОЗДАНИЕ БРОНИРОВАНИЯ ----------------
    # Два шага: выбор параметров → подтверждение
    @app.route('/booking/<string:room_id>', methods=['GET', 'POST'])
    @login_required
    def create_booking(room_id):
        from hotel_logic import log_action
        conn = get_db()
        try:
            room = conn.execute("SELECT * FROM Номера WHERE ID_Номера = ?", (room_id,)).fetchone()
            services = conn.execute("SELECT * FROM Услуги WHERE Активна=1 ORDER BY Название").fetchall()
            if not room:
                flash('Номер не найден', 'danger')
                return redirect(url_for('index'))
            if room['Статус_обслуживания'] if 'Статус_обслуживания' in room.keys() else False:
                flash(f"Номер временно недоступен: {room['Статус_обслуживания']}.", 'danger')
                return redirect(url_for('room_detail', room_id=room_id))

            if request.method == 'POST':
                action = request.form.get('action', 'review')
                check_in = request.form.get('check_in', '').strip()
                check_out = request.form.get('check_out', '').strip()
                guests = request.form.get('guests', 1, type=int)
                selected_services = request.form.getlist('services')

                try:
                    parse_stay_dates(check_in, check_out)
                    validate_guests(guests, room['Вместимость'])
                except BookingError as be:
                    flash(str(be), 'danger')
                    return render_template('booking.html', room=room, services=services, check_in=check_in, check_out=check_out, guests=guests)
                if not room_is_available(conn, room_id, check_in, check_out):
                    flash('Номер уже занят на выбранные даты. Выберите другой период.', 'danger')
                    return render_template('booking.html', room=room, services=services, check_in=check_in, check_out=check_out, guests=guests)

                valid_service_ids = {s['ID_Услуги'] for s in services}
                selected_services = [x for x in selected_services if x in valid_service_ids]
                total_room, nights = booking_total(conn, room_id, check_in, check_out)
                selected_rows = []
                for sid in selected_services:
                    row = conn.execute('SELECT * FROM Услуги WHERE ID_Услуги=?', (sid,)).fetchone()
                    if row:
                        selected_rows.append(row)
                services_sum = sum(float(x['Цена']) for x in selected_rows)
                subtotal = total_room + services_sum
                promo_code = request.form.get('promo_code','').strip().upper()
                if promo_code:
                    session['promo'] = {'code': promo_code}
                promo = session.get('promo') or {}
                discount = 0.0
                if promo.get('code'):
                    p = conn.execute("SELECT * FROM Промокоды WHERE Код=? AND Активен=1 AND (Действует_до IS NULL OR Действует_до>=date('now'))", (promo['code'],)).fetchone()
                    used = conn.execute("SELECT 1 FROM Использованные_промокоды WHERE Код=? AND ID_Клиента=?", (promo['code'], session['client_id'])).fetchone()
                    if p and not used and (not p['Лимит'] or p['Использовано'] < p['Лимит']):
                        discount = round(subtotal * float(p['Скидка']) / 100, 2)
                    else:
                        session.pop('promo', None)
                total = round(subtotal - discount, 2)

                if action == 'review':
                    session['booking_draft'] = {
                        'room_id': room_id, 'check_in': check_in, 'check_out': check_out,
                        'guests': guests, 'services': selected_services,
                        'promo_code': (session.get('promo') or {}).get('code','')
                    }
                    return render_template('booking_review.html', room=room, services=selected_rows,
                                           check_in=check_in, check_out=check_out, guests=guests,
                                           nights=nights, room_total=total_room, services_total=services_sum,
                                           subtotal=subtotal, discount=discount,
                                           promo_code=(session.get('promo') or {}).get('code',''),
                                           total=total, prepayment=round(total * PREPAYMENT_RATE, 2))

                if action == 'confirm':
                    draft = session.get('booking_draft') or {}
                    if draft.get('room_id') != room_id or draft.get('check_in') != check_in or draft.get('check_out') != check_out:
                        raise ValueError('Срок действия черновика бронирования истёк. Начните бронирование заново.')

                    # FIX #2: промокод может быть изменён на шаге подтверждения —
                    # берём его из формы, а не только из черновика.
                    promo_code_final = (
                        request.form.get('promo_code')
                        or draft.get('promo_code')
                        or ''
                    ).strip().upper()

                    # Критическая проверка внутри транзакции: пока бронь
                    # подтверждается, другой запрос не сможет занять тот же номер.
                    conn.execute('BEGIN IMMEDIATE')
                    if not room_is_available(conn, room_id, check_in, check_out):
                        conn.rollback()
                        raise ValueError('Номер только что забронировал другой пользователь. Выберите другой период.')

                    # Все данные пересчитываются из БД, а не доверяются данным с клиента.
                    selected_services = [x for x in (draft.get('services') or []) if x in valid_service_ids]
                    selected_rows = []
                    for sid in selected_services:
                        row = conn.execute('SELECT * FROM Услуги WHERE ID_Услуги=? AND Активна=1', (sid,)).fetchone()
                        if row:
                            selected_rows.append(row)
                    total_room, nights = booking_total(conn, room_id, check_in, check_out)
                    services_sum = sum(float(x['Цена']) for x in selected_rows)
                    subtotal = total_room + services_sum
                    discount = 0.0
                    if promo_code_final:
                        p = conn.execute(
                            "SELECT * FROM Промокоды WHERE Код=? AND Активен=1 AND (Действует_до IS NULL OR Действует_до>=date('now'))",
                            (promo_code_final,),
                        ).fetchone()
                        used = conn.execute(
                            "SELECT 1 FROM Использованные_промокоды WHERE Код=? AND ID_Клиента=?",
                            (promo_code_final, session['client_id']),
                        ).fetchone()
                        if p and not used and (not p['Лимит'] or p['Использовано'] < p['Лимит']):
                            discount = round(subtotal * float(p['Скидка']) / 100, 2)
                            updated = conn.execute(
                                "UPDATE Промокоды SET Использовано=Использовано+1 WHERE Код=? AND Активен=1 AND (Лимит=0 OR Использовано < Лимит)",
                                (promo_code_final,),
                            )
                            if updated.rowcount != 1:
                                conn.rollback()
                                raise ValueError('Лимит промокода только что был исчерпан.')
                        elif p and used:
                            raise ValueError('Вы уже использовали этот промокод.')
                        else:
                            raise ValueError('Промокод недействителен или лимит исчерпан.')
                    total = round(subtotal - discount, 2)

                    booking_id, invoice_id = create_confirmed_booking(
                        conn,
                        client_id=session['client_id'],
                        room_id=room_id,
                        check_in=check_in,
                        check_out=check_out,
                        guests=guests,
                        total=total,
                        selected_service_rows=selected_rows,
                        promo_code=promo_code_final or '',
                        discount=discount,
                        next_id_fn=next_id,
                    )
                    conn.commit()
                    session.pop('booking_draft', None); session.pop('promo', None)
                    log_action('Создано бронирование', booking_id, f'Номер {room["Номер_Комнаты"]}, {check_in} — {check_out}')
                    sync_room_statuses()
                    flash(f'Бронирование {booking_id} создано.', 'success')
                    return redirect(url_for('booking_confirmation', booking_id=booking_id))

            check_in = request.args.get('check_in', datetime.now().strftime('%Y-%m-%d'))
            check_out = request.args.get('check_out', (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'))
            guests = request.args.get('guests', 1, type=int)
            return render_template('booking.html', room=room, services=services, check_in=check_in, check_out=check_out, guests=guests)
        except Exception as e:
            conn.rollback()
            current_app.logger.exception('Ошибка создания бронирования')
            flash('Не удалось создать бронирование. Попробуйте ещё раз.', 'danger')
            return redirect(url_for('room_detail', room_id=room_id))
        finally:
            conn.close()

    # ---------------- ПОДТВЕРЖДЕНИЕ БРОНИРОВАНИЯ ----------------
    @app.route('/booking/confirmation/<string:booking_id>')
    @login_required
    def booking_confirmation(booking_id):
        try:
            conn = get_db()
            booking = conn.execute("""
                SELECT b.*, n.Номер_Комнаты, n.Категория, n.Цена_за_сутки,
                       CAST(JULIANDAY(b.Дата_выезда) - JULIANDAY(b.Дата_заезда) AS INTEGER) AS days_count,
                       c.Фамилия, c.Имя, c.Отчество
                FROM Бронирования b
                JOIN Номера n ON b.ID_Номера=n.ID_Номера
                JOIN Клиенты c ON b.ID_Клиента=c.ID_Клиента
                WHERE b.ID_Бронирования=? AND b.ID_Клиента=?
            """, (booking_id, session['client_id'])).fetchone()
            if not booking:
                conn.close()
                flash('Бронирование не найдено', 'danger')
                return redirect(url_for('profile'))
            invoice = conn.execute("SELECT * FROM Счета WHERE ID_Бронирования=?", (booking_id,)).fetchone()
            services = conn.execute("""SELECT u.*, bs.Количество, bs.Цена AS Цена_при_бронировании
                FROM Бронирование_Услуги bs JOIN Услуги u ON u.ID_Услуги=bs.ID_Услуги
                WHERE bs.ID_Бронирования=?""", (booking_id,)).fetchall()
            conn.close()
            booking_dict = dict(booking)
            booking_dict['total_price'] = float(invoice['Сумма_проживание']) if invoice else float(booking_dict.get('days_count', 0)) * float(booking_dict.get('Цена_за_сутки', 0))
            booking_dict['payment_paid'] = bool(invoice and invoice['Оплачено'])
            booking_dict['payment_amount'] = float(booking_dict.get('Предоплата') or 0)
            return render_template('confirmation.html', booking=booking_dict, services=services, invoice=invoice)
        except Exception as e:
            current_app.logger.exception('Ошибка загрузки подтверждения')
            flash('Не удалось загрузить подтверждение. Попробуйте ещё раз.', 'danger')
            return redirect(url_for('profile'))

    # ---------------- ОТМЕНА БРОНИРОВАНИЯ ----------------
    @app.route('/booking/cancel/<string:booking_id>', methods=['POST'])
    @login_required
    def cancel_booking(booking_id):
        conn = get_db()
        try:
            booking = conn.execute(
                "SELECT Дата_заезда, ID_Номера FROM Бронирования WHERE ID_Бронирования=? AND ID_Клиента=?",
                (booking_id, session['client_id'])
            ).fetchone()
            if not booking:
                flash('Бронирование не найдено.', 'danger')
                return redirect(url_for('profile'))
            check_in = datetime.strptime(booking['Дата_заезда'], '%Y-%m-%d').date()
            if check_in <= datetime.now().date():
                flash('Нельзя отменить бронирование в день заезда или позже.', 'danger')
                return redirect(url_for('profile'))
            conn.execute("UPDATE Бронирования SET Статус='Отменено' WHERE ID_Бронирования=?", (booking_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            current_app.logger.exception('Ошибка отмены бронирования')
            flash('Не удалось отменить бронирование. Попробуйте ещё раз.', 'danger')
            return redirect(url_for('profile'))
        finally:
            conn.close()
        sync_room_statuses()
        from hotel_logic import log_action
        log_action('Отменено бронирование', booking_id, 'Гость отменил бронь')
        flash('Бронирование отменено.', 'success')
        return redirect(url_for('profile'))