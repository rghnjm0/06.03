"""Расширенная бизнес-логика АИС «Уют»."""
from datetime import datetime
from db import get_db


def ensure_extra_rooms(conn):
    """Добавляет дополнительные номера 402–406 в существующую учебную БД.
    Это миграция: при повторном запуске уже существующие номера не дублируются.
    """
    extra_rooms = [
        ('RM011', '402', 'Люкс', 4, 9000.00, 'Свободен', 4, '402.jpg'),
        ('RM012', '403', 'Люкс', 4, 9500.00, 'Свободен', 4, '403.jpg'),
        ('RM013', '404', 'Премиум', 2, 10500.00, 'Свободен', 4, '404.jpg'),
        ('RM014', '405', 'Премиум', 3, 11000.00, 'Свободен', 4, '405.jpg'),
        ('RM015', '406', 'Апартаменты', 5, 13500.00, 'Свободен', 4, '406.jpg'),
    ]
    for room in extra_rooms:
        conn.execute("""
            INSERT OR IGNORE INTO Номера
            (ID_Номера, Номер_Комнаты, Категория, Вместимость, Цена_за_сутки, Статус, Этаж, Изображение)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, room)

    # Если номер уже был создан ранее, но у него не было фотографии,
    # привязываем именно загруженную пользователем фотографию.
    for room_number, filename in [('402','402.jpg'),('403','403.jpg'),('404','404.jpg'),('405','405.jpg'),('406','406.jpg')]:
        conn.execute(
            "UPDATE Номера SET Изображение=? WHERE Номер_Комнаты=? AND (Изображение IS NULL OR Изображение='')",
            (filename, room_number)
        )

def ensure_extended_schema():
    conn = get_db()
    try:
        ensure_extra_rooms(conn)
        conn.commit()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Услуги (
                ID_Услуги TEXT PRIMARY KEY,
                Название TEXT NOT NULL UNIQUE,
                Описание TEXT,
                Цена REAL NOT NULL DEFAULT 0,
                Активна INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Бронирование_Услуги (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ID_Бронирования TEXT NOT NULL,
                ID_Услуги TEXT NOT NULL,
                Количество INTEGER NOT NULL DEFAULT 1,
                Цена REAL NOT NULL DEFAULT 0,
                UNIQUE(ID_Бронирования, ID_Услуги),
                FOREIGN KEY(ID_Бронирования) REFERENCES Бронирования(ID_Бронирования) ON DELETE CASCADE,
                FOREIGN KEY(ID_Услуги) REFERENCES Услуги(ID_Услуги)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Журнал_действий (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Время TEXT NOT NULL,
                Пользователь TEXT,
                Роль TEXT,
                Действие TEXT NOT NULL,
                Объект TEXT,
                Детали TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_booking_services_booking ON Бронирование_Услуги(ID_Бронирования)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON Журнал_действий(Время)")
        services = [
            ('SRV001', 'Завтрак', 'Шведский стол', 900),
            ('SRV002', 'Парковка', 'Место на охраняемой парковке', 500),
            ('SRV003', 'Трансфер', 'Трансфер из/в аэропорт', 1800),
            ('SRV004', 'Поздний выезд', 'Выезд до 18:00', 1500),
            ('SRV005', 'Дополнительное место', 'Раскладная кровать', 1200),
            ('SRV006', 'Романтический пакет', 'Украшение номера и комплимент', 2500),
            ('SRV007', 'Кофейный набор', 'Кофе и чай в номер', 450),
            ('SRV008', 'Ранний заезд', 'Заезд с 10:00 при наличии номера', 1200),
        ]
        for sid, name, desc, price in services:
            conn.execute("INSERT OR IGNORE INTO Услуги(ID_Услуги,Название,Описание,Цена) VALUES(?,?,?,?)", (sid,name,desc,price))
        conn.commit()
    finally:
        conn.close()


def _sanitize_audit_text(value, max_len=500):
    """Ограничивает длину и убирает управляющие символы из полей журнала."""
    if value is None:
        return ''
    text = str(value)
    # Убираем управляющие символы, кроме табуляции и перевода строки.
    text = ''.join(ch for ch in text if ch == '\t' or ch == '\n' or ord(ch) >= 32)
    text = ' '.join(text.split())  # схлопываем пробелы
    if len(text) > max_len:
        text = text[: max_len - 1] + '…'
    return text


def log_action(action, obj='', details=''):
    try:
        from flask import session
        user = session.get('user_name') or session.get('admin_name') or 'Система'
        role = session.get('user_role') or 'system'
    except Exception:
        user, role = 'Система', 'system'
    action = _sanitize_audit_text(action, 120)
    obj = _sanitize_audit_text(obj, 120)
    details = _sanitize_audit_text(details, 500)
    user = _sanitize_audit_text(user, 120)
    role = _sanitize_audit_text(role, 40)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO Журнал_действий(Время,Пользователь,Роль,Действие,Объект,Детали) VALUES(?,?,?,?,?,?)",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user, role, action, obj, details),
        )
        conn.commit()
    finally:
        conn.close()
