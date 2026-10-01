from flask import render_template, request, redirect, url_for, flash, session, current_app
from datetime import datetime
from db import get_db
from utils import sync_room_statuses



def register_public_routes(app):
    @app.route('/')


    def index():


        try:


            sync_room_statuses()


            conn = get_db()


            cursor = conn.cursor()


            cursor.execute("SELECT DISTINCT Категория FROM Номера ORDER BY Категория")


            categories = [row['Категория'] for row in cursor.fetchall()]


            cursor.execute("""


                SELECT * FROM Номера 


                ORDER BY 


                    CASE Статус 


                        WHEN 'Свободен' THEN 1


                        WHEN 'Будет занят' THEN 2


                        WHEN 'Занят' THEN 3


                    END,


                    Номер_Комнаты


            """)


            rooms = cursor.fetchall()


            conn.close()


            return render_template('index.html', rooms=rooms, categories=categories)


        except Exception as e:


            current_app.logger.exception('Ошибка загрузки главной страницы'); flash('Не удалось загрузить данные. Попробуйте ещё раз.', 'danger')


            return render_template('index.html', rooms=[], categories=[])








    # Поиск номеров
    @app.route('/search')
    def search_rooms():
        try:
            check_in = request.args.get('check_in', '').strip()
            check_out = request.args.get('check_out', '').strip()
            guests = request.args.get('guests', 1, type=int)
            category = request.args.get('category', '').strip()

            if guests < 1:
                guests = 1
            if check_in and check_out:
                try:
                    start = datetime.strptime(check_in, '%Y-%m-%d').date()
                    end = datetime.strptime(check_out, '%Y-%m-%d').date()
                    if end <= start:
                        raise ValueError
                except ValueError:
                    flash('Дата выезда должна быть позже даты заезда.', 'danger')
                    return redirect(url_for('index'))

            conn = get_db()
            cursor = conn.cursor()
            params = [guests]
            query = """
                SELECT n.*
                FROM Номера n
                WHERE n.Вместимость >= ?
            """
            if category:
                query += ' AND n.Категория = ?'
                params.append(category)

            if check_in and check_out:
                query += """
                    AND NOT EXISTS (
                        SELECT 1 FROM Бронирования b
                        WHERE b.ID_Номера = n.ID_Номера
                          AND b.Статус IN ('Подтверждено', 'Заселен')
                          AND NOT (b.Дата_выезда <= ? OR b.Дата_заезда >= ?)
                    )
                """
                params.extend([check_in, check_out])
            else:
                query += " AND n.Статус = 'Свободен'"

            query += ' ORDER BY n.Цена_за_сутки, n.Номер_Комнаты'
            cursor.execute(query, params)
            rooms = cursor.fetchall()

            cursor.execute('SELECT DISTINCT Категория FROM Номера ORDER BY Категория')
            categories = [row['Категория'] for row in cursor.fetchall()]
            conn.close()

            return render_template('rooms.html', rooms=rooms, categories=categories,
                                   check_in=check_in, check_out=check_out,
                                   guests=guests, selected_category=category)
        except Exception as e:
            current_app.logger.exception('Ошибка поиска номеров'); flash('Не удалось выполнить поиск. Попробуйте ещё раз.', 'danger')
            return redirect(url_for('index'))


    # Детальная страница номера


    @app.route('/room/<string:room_id>')


    def room_detail(room_id):


        try:


            sync_room_statuses()


            conn = get_db()


            cursor = conn.cursor()


            cursor.execute("SELECT * FROM Номера WHERE ID_Номера = ?", (room_id,))


            room = cursor.fetchone()


            if not room:


                flash('Номер не найден', 'danger')


                conn.close()


                return redirect(url_for('index'))


            gallery = conn.execute("SELECT * FROM Галерея_номеров WHERE ID_Номера=? ORDER BY ID", (room_id,)).fetchall()
            reviews = conn.execute("SELECT r.*, 'Гость' AS Имя FROM Отзывы r WHERE r.ID_Номера=? AND r.Опубликовано=1 ORDER BY r.ID DESC", (room_id,)).fetchall()
            avg_rating = conn.execute("SELECT COALESCE(AVG(Оценка),0) avg, COUNT(*) count FROM Отзывы WHERE ID_Номера=? AND Опубликовано=1", (room_id,)).fetchone()
            favorite = bool(session.get('client_id') and conn.execute("SELECT 1 FROM Избранное WHERE ID_Клиента=? AND ID_Номера=?", (session['client_id'],room_id)).fetchone())
            conn.close()
            return render_template('room_detail.html', room=room, gallery=gallery, reviews=reviews, avg_rating=avg_rating, favorite=favorite)


        except Exception as e:


            current_app.logger.exception('Ошибка загрузки номера'); flash('Не удалось загрузить номер. Попробуйте ещё раз.', 'danger')


            return redirect(url_for('index'))








    # Регистрация клиента



    @app.route('/availability')
    def availability():
        check_in = request.args.get('check_in','').strip()
        check_out = request.args.get('check_out','').strip()
        guests = request.args.get('guests',1,type=int)
        rooms = []
        if check_in and check_out:
            try:
                start = datetime.strptime(check_in,'%Y-%m-%d').date(); end = datetime.strptime(check_out,'%Y-%m-%d').date()
                if end <= start: raise ValueError
                conn=get_db()
                rooms=conn.execute("""SELECT n.* FROM Номера n WHERE n.Вместимость>=? AND NOT EXISTS (SELECT 1 FROM Бронирования b WHERE b.ID_Номера=n.ID_Номера AND b.Статус IN ('Подтверждено','Заселен') AND NOT (b.Дата_выезда<=? OR b.Дата_заезда>=?)) ORDER BY n.Цена_за_сутки""",(max(1,guests),check_in,check_out)).fetchall(); conn.close()
            except ValueError:
                flash('Проверьте выбранные даты.','danger')
        return render_template('availability.html', rooms=rooms, check_in=check_in, check_out=check_out, guests=guests)

    @app.route('/contact')


    def contact():


        return render_template('contact.html')








    # ============= ПУБЛИЧНЫЕ МАРШРУТЫ =============





    # Главная админ-панели
