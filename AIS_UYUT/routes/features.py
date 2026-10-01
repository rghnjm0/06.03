"""Дополнительные возможности АИС «Уют»: профиль, избранное, отзывы,
промокоды, внутренние уведомления, галерея и расширенные операции администратора.
"""
from datetime import datetime
import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, current_app
from db import get_db
from security import login_required, admin_required
from services.passwords import password_matches, hash_password, validate_password
from hotel_logic import log_action
from utils import safe_csv_value
import csv, io

features_bp = Blueprint('features', __name__)


def ensure_features_schema():
    conn = get_db()
    try:
        # SQLite migration for room maintenance state.
        cols = [r['name'] for r in conn.execute("PRAGMA table_info(Номера)").fetchall()]
        if 'Статус_обслуживания' not in cols:
            conn.execute("ALTER TABLE Номера ADD COLUMN Статус_обслуживания TEXT DEFAULT ''")
        conn.execute("""CREATE TABLE IF NOT EXISTS Избранное (
            ID INTEGER PRIMARY KEY AUTOINCREMENT, ID_Клиента TEXT NOT NULL, ID_Номера TEXT NOT NULL,
            UNIQUE(ID_Клиента,ID_Номера), FOREIGN KEY(ID_Клиента) REFERENCES Клиенты(ID_Клиента) ON DELETE CASCADE,
            FOREIGN KEY(ID_Номера) REFERENCES Номера(ID_Номера) ON DELETE CASCADE)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS Отзывы (
            ID INTEGER PRIMARY KEY AUTOINCREMENT, ID_Клиента TEXT NOT NULL, ID_Номера TEXT NOT NULL,
            ID_Бронирования TEXT, Оценка INTEGER NOT NULL, Текст TEXT, Создано TEXT NOT NULL,
            Опубликовано INTEGER NOT NULL DEFAULT 1, UNIQUE(ID_Клиента,ID_Бронирования),
            FOREIGN KEY(ID_Клиента) REFERENCES Клиенты(ID_Клиента) ON DELETE CASCADE)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS Промокоды (
            ID INTEGER PRIMARY KEY AUTOINCREMENT, Код TEXT UNIQUE NOT NULL, Скидка REAL NOT NULL,
            Активен INTEGER NOT NULL DEFAULT 1, Лимит INTEGER DEFAULT 0, Использовано INTEGER NOT NULL DEFAULT 0,
            Действует_до TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS Использованные_промокоды (
            ID INTEGER PRIMARY KEY AUTOINCREMENT, Код TEXT NOT NULL, ID_Клиента TEXT NOT NULL,
            ID_Бронирования TEXT NOT NULL, UNIQUE(Код,ID_Клиента), FOREIGN KEY(Код) REFERENCES Промокоды(Код))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS Уведомления (
            ID INTEGER PRIMARY KEY AUTOINCREMENT, ID_Клиента TEXT NOT NULL, Заголовок TEXT NOT NULL,
            Текст TEXT NOT NULL, Прочитано INTEGER NOT NULL DEFAULT 0, Создано TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS Галерея_номеров (
            ID INTEGER PRIMARY KEY AUTOINCREMENT, ID_Номера TEXT NOT NULL, Файл TEXT NOT NULL,
            Подпись TEXT, FOREIGN KEY(ID_Номера) REFERENCES Номера(ID_Номера) ON DELETE CASCADE)""")
        for code, discount, limit in [('UYUT10',10,0),('WELCOME5',5,100),('FAMILY15',15,50)]:
            conn.execute("INSERT OR IGNORE INTO Промокоды(Код,Скидка,Лимит) VALUES(?,?,?)", (code,discount,limit))
        # Seed gallery from existing room images, without duplicating rows.
        rooms = conn.execute("SELECT ID_Номера,Изображение FROM Номера WHERE Изображение IS NOT NULL AND Изображение!=''").fetchall()
        for r in rooms:
            exists = conn.execute("SELECT 1 FROM Галерея_номеров WHERE ID_Номера=? AND Файл=?", (r['ID_Номера'],r['Изображение'])).fetchone()
            if not exists:
                conn.execute("INSERT INTO Галерея_номеров(ID_Номера,Файл,Подпись) VALUES(?,?,?)", (r['ID_Номера'],r['Изображение'],'Фото номера'))
        conn.commit()
    finally:
        conn.close()


@features_bp.get('/favorites')
@login_required
def favorites():
    conn=get_db()
    try:
        rooms=conn.execute("SELECT n.* FROM Избранное f JOIN Номера n ON n.ID_Номера=f.ID_Номера WHERE f.ID_Клиента=? ORDER BY f.ID DESC",(session['client_id'],)).fetchall()
        return render_template('favorites.html', rooms=rooms)
    finally: conn.close()

@features_bp.post('/favorite/<string:room_id>')
@login_required
def toggle_favorite(room_id):
    conn=get_db()
    try:
        row=conn.execute("SELECT 1 FROM Избранное WHERE ID_Клиента=? AND ID_Номера=?",(session['client_id'],room_id)).fetchone()
        if row:
            conn.execute("DELETE FROM Избранное WHERE ID_Клиента=? AND ID_Номера=?",(session['client_id'],room_id))
            flash('Номер удалён из избранного.','info')
            log_action('Избранное', room_id, 'Удалён из избранного')
        else:
            conn.execute("INSERT OR IGNORE INTO Избранное(ID_Клиента,ID_Номера) VALUES(?,?)",(session['client_id'],room_id))
            flash('Номер добавлен в избранное.','success')
            log_action('Избранное', room_id, 'Добавлен в избранное')
        conn.commit()
    finally: conn.close()
    return redirect(url_for('room_detail', room_id=room_id))

@features_bp.post('/review/<string:booking_id>')
@login_required
def add_review(booking_id):
    rating=request.form.get('rating',type=int); text=request.form.get('text','').strip()
    conn=get_db()
    try:
        b=conn.execute("SELECT * FROM Бронирования WHERE ID_Бронирования=? AND ID_Клиента=? AND Статус='Завершено'",(booking_id,session['client_id'])).fetchone()
        if not b: raise ValueError('Оставить отзыв можно после завершённого проживания.')
        if rating not in range(1,6): raise ValueError('Оценка должна быть от 1 до 5.')
        conn.execute("INSERT OR REPLACE INTO Отзывы(ID_Клиента,ID_Номера,ID_Бронирования,Оценка,Текст,Создано) VALUES(?,?,?,?,?,?)",
                     (session['client_id'],b['ID_Номера'],booking_id,rating,text,datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        log_action('Отзыв', booking_id, f'Оценка {rating}, номер {b["ID_Номера"]}')
        flash('Спасибо! Отзыв сохранён.','success')
    except Exception as e: conn.rollback(); flash(str(e) if isinstance(e, ValueError) else 'Внутренняя ошибка. Попробуйте ещё раз.','danger')
    finally: conn.close()
    return redirect(url_for('profile'))

@features_bp.route('/profile/edit', methods=['GET','POST'])
@login_required
def profile_edit():
    conn=get_db()
    try:
        client=conn.execute("SELECT * FROM Клиенты WHERE ID_Клиента=?",(session['client_id'],)).fetchone()
        if request.method=='POST':
            phone = request.form.get('phone','').strip()
            duplicate = conn.execute("SELECT 1 FROM Клиенты WHERE Телефон=? AND ID_Клиента<>?", (phone, session['client_id'])).fetchone()
            if duplicate:
                raise ValueError('Этот телефон уже используется.')
            conn.execute("UPDATE Клиенты SET Фамилия=?,Имя=?,Отчество=?,Телефон=?,Дата_рождения=?,Адрес=? WHERE ID_Клиента=?",
                         (request.form.get('last_name','').strip(),request.form.get('first_name','').strip(),request.form.get('middle_name','').strip(),phone,request.form.get('birth_date') or None,request.form.get('address','').strip(),session['client_id']))
            conn.execute("UPDATE Пользователи SET Логин=? WHERE ID_Клиента=?",(phone,session['client_id']))
            conn.commit(); log_action('Изменён профиль гостя', session['client_id'], 'Гость обновил персональные данные'); flash('Профиль обновлён.','success'); return redirect(url_for('profile'))
        return render_template('profile_edit.html',client=client)
    finally: conn.close()

@features_bp.route('/profile/password', methods=['GET','POST'])
@login_required
def change_password():
    if request.method=='POST':
        conn=get_db()
        try:
            row=conn.execute("SELECT Пароль FROM Пользователи WHERE ID_Клиента=?",(session['client_id'],)).fetchone()
            if not row or not password_matches(row['Пароль'], request.form.get('current_password','')): raise ValueError('Текущий пароль введён неверно.')
            p=request.form.get('password',''); p2=request.form.get('password2','')
            if p!=p2: raise ValueError('Новые пароли не совпадают.')
            validate_password(p)
            new_hash = hash_password(p)
            conn.execute("UPDATE Пользователи SET Пароль=? WHERE ID_Клиента=?",(new_hash,session['client_id']))
            conn.commit()
            # Текущая сессия остаётся валидной; остальные (со старым pwd_sig) отвалятся.
            session['pwd_sig'] = (new_hash or '')[:64]
            log_action('Смена пароля', session['client_id'], 'Гость изменил пароль')
            flash('Пароль изменён. Другие активные сессии завершены.','success')
            return redirect(url_for('profile'))
        except Exception as e: conn.rollback(); flash(str(e) if isinstance(e, ValueError) else 'Внутренняя ошибка. Попробуйте ещё раз.','danger')
        finally: conn.close()
    return render_template('password_change.html')

@features_bp.post('/promo/check')
@login_required
def check_promo():
    code=request.form.get('code','').strip().upper()
    conn=get_db()
    try:
        p=conn.execute("SELECT * FROM Промокоды WHERE Код=? AND Активен=1 AND (Действует_до IS NULL OR Действует_до>=date('now'))",(code,)).fetchone()
        if not p or (p['Лимит'] and p['Использовано']>=p['Лимит']): raise ValueError('Промокод недействителен или лимит исчерпан.')
        if conn.execute("SELECT 1 FROM Использованные_промокоды WHERE Код=? AND ID_Клиента=?",(code,session['client_id'])).fetchone(): raise ValueError('Вы уже использовали этот промокод.')
        # Сумма из браузера используется только для предварительного отображения.
        # Итоговая сумма всегда пересчитывается на сервере при подтверждении брони.
        session['promo']={'code':code,'discount_percent':float(p['Скидка'])}
        return {'ok':True,'code':code,'discount_percent':float(p['Скидка'])}
    except Exception as e: return {'ok':False,'error':str(e)},400
    finally: conn.close()

@features_bp.get('/notifications')
@login_required
def notifications():
    conn=get_db()
    try:
        rows=conn.execute("SELECT * FROM Уведомления WHERE ID_Клиента=? ORDER BY ID DESC",(session['client_id'],)).fetchall()
        conn.execute("UPDATE Уведомления SET Прочитано=1 WHERE ID_Клиента=?",(session['client_id'],)); conn.commit()
        return render_template('notifications.html',notifications=rows)
    finally: conn.close()

@features_bp.get('/room/<string:room_id>/reviews')
def room_reviews(room_id):
    conn=get_db()
    try:
        room=conn.execute("SELECT * FROM Номера WHERE ID_Номера=?",(room_id,)).fetchone()
        reviews=conn.execute("SELECT r.*,c.Имя,c.Фамилия FROM Отзывы r JOIN Клиенты c ON c.ID_Клиента=r.ID_Клиента WHERE r.ID_Номера=? AND r.Опубликовано=1 ORDER BY r.ID DESC",(room_id,)).fetchall()
        return render_template('room_reviews.html',room=room,reviews=reviews)
    finally: conn.close()

# Admin additions
@features_bp.post('/admin/room/status/<string:room_id>')
@admin_required
def room_service_status(room_id):
    status=request.form.get('status','')
    allowed={'':'Обычный режим','Уборка':'Уборка','Ремонт':'Ремонт'}
    if status not in allowed: flash('Недопустимый статус.','danger'); return redirect(url_for('admin_rooms'))
    conn=get_db()
    try:
        conn.execute("UPDATE Номера SET Статус_обслуживания=? WHERE ID_Номера=?",(status,room_id)); conn.commit(); log_action('Изменён статус номера',room_id,status or 'Обычный режим'); flash('Статус номера обновлён.','success')
    finally: conn.close()
    return redirect(url_for('admin_rooms'))

@features_bp.route('/admin/promocodes',methods=['GET','POST'])
@admin_required
def admin_promocodes():
    conn=get_db()
    try:
        if request.method=='POST':
            code=request.form.get('code','').strip().upper(); discount=float(request.form.get('discount',0)); limit=int(request.form.get('limit',0) or 0); until=request.form.get('until') or None
            if not code or not (0<discount<=100): raise ValueError('Проверьте код и размер скидки.')
            conn.execute("INSERT INTO Промокоды(Код,Скидка,Лимит,Действует_до) VALUES(?,?,?,?)",(code,discount,limit,until)); conn.commit(); log_action('Создан промокод', code, f'Скидка {discount}%'); flash('Промокод создан.','success')
            return redirect(url_for('features.admin_promocodes'))
        rows=conn.execute("SELECT * FROM Промокоды ORDER BY ID DESC").fetchall()
        return render_template('admin/promocodes.html',promocodes=rows)
    except Exception as e:
        conn.rollback()
        flash(str(e) if isinstance(e, ValueError) else 'Внутренняя ошибка. Попробуйте ещё раз.','danger')
        # ВАЖНО: endpoint промокодов принадлежит blueprint'у features
        return redirect(url_for('features.admin_promocodes'))
    finally:
        conn.close()

@features_bp.post('/admin/promocode/toggle/<int:promo_id>')
@admin_required
def toggle_promocode(promo_id):
    conn=get_db(); conn.execute("UPDATE Промокоды SET Активен=CASE WHEN Активен=1 THEN 0 ELSE 1 END WHERE ID=?",(promo_id,)); conn.commit(); log_action('Изменён статус промокода', promo_id, 'Переключение активности'); conn.close(); return redirect(url_for('features.admin_promocodes'))

@features_bp.post('/admin/room/gallery/<string:room_id>')
@admin_required
def add_gallery(room_id):
    f=request.files.get('image')
    if not f or not f.filename:
        flash('Выберите изображение.','danger'); return redirect(url_for('admin_rooms'))
    room_id = room_id.strip()
    conn=get_db()
    try:
        if not conn.execute('SELECT 1 FROM Номера WHERE ID_Номера=?',(room_id,)).fetchone():
            raise ValueError('Номер не найден.')
        original = f.filename.rsplit('.',1)
        if len(original) != 2 or original[1].lower() not in {'jpg','jpeg','png','webp'}:
            raise ValueError('Разрешены только JPG, JPEG, PNG и WEBP.')
        from PIL import Image
        f.stream.seek(0)
        try:
            img = Image.open(f.stream)
            img.verify()
            fmt = (img.format or '').upper()
        except Exception:
            raise ValueError('Файл не является корректным изображением.')
        ext = {'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(fmt)
        if not ext:
            raise ValueError('Поддерживаются только JPEG, PNG и WEBP.')
        name = f"room_{uuid.uuid4().hex}.{ext}"
        upload_dir = current_app.config.get('UPLOAD_FOLDER') or os.path.join(current_app.root_path, 'static', 'images', 'rooms')
        if not os.path.isabs(upload_dir):
            upload_dir = os.path.join(current_app.root_path, upload_dir)
        path = os.path.join(upload_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        f.stream.seek(0)
        with Image.open(f.stream) as img2:
            img2.load()
            if img2.width > 5000 or img2.height > 5000:
                raise ValueError('Изображение слишком большое по разрешению.')
            # Перекодируем изображение вместо сохранения произвольного исходного потока.
            if fmt == 'JPEG':
                img2 = img2.convert('RGB')
            elif img2.mode not in ('RGB', 'RGBA'):
                img2 = img2.convert('RGBA' if 'A' in img2.getbands() else 'RGB')
            img2.save(path, format=fmt, optimize=True)
        conn.execute("INSERT INTO Галерея_номеров(ID_Номера,Файл,Подпись) VALUES(?,?,?)",(room_id,name,request.form.get('caption','').strip()[:200])); conn.commit(); log_action('Галерея', room_id, f'Добавлено фото {name}'); flash('Фото добавлено.','success')
    except Exception as e:
        conn.rollback(); flash(str(e) if isinstance(e, ValueError) else 'Внутренняя ошибка. Попробуйте ещё раз.','danger')
    finally: conn.close()
    return redirect(url_for('admin_rooms'))

@features_bp.get('/admin/export/guests.csv')
@admin_required
def export_guests():
    MAX_EXPORT_ROWS = 5000
    conn=get_db()
    rows=conn.execute(
        "SELECT ID_Клиента,Фамилия,Имя,Отчество,Телефон,Дата_рождения,Адрес FROM Клиенты ORDER BY Фамилия,Имя LIMIT ?",
        (MAX_EXPORT_ROWS,),
    ).fetchall()
    conn.close()
    out=io.StringIO(); w=csv.writer(out,delimiter=';'); w.writerow(['ID','Фамилия','Имя','Отчество','Телефон','Дата рождения','Адрес']); [w.writerow([safe_csv_value(v) for v in r]) for r in rows]
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=uyut_guests.csv'})
