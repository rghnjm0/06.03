"""Общие вспомогательные функции приложения «Уют»."""
import os
import re
from datetime import datetime, timedelta
from flask import url_for
from db import get_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOMS_DIR = os.path.join(BASE_DIR, "static", "images", "rooms")
ACTIVE_BOOKING_STATUSES = ("Подтверждено", "Заселен")


def init_uploads():
    os.makedirs(ROOMS_DIR, exist_ok=True)


def get_room_image(room_number):
    room_number_str = str(room_number)
    extensions = (".jpg", ".jpeg", ".png", ".webp")
    for ext in extensions:
        filename = f"{room_number_str}{ext}"
        if os.path.isfile(os.path.join(ROOMS_DIR, filename)):
            return url_for("static", filename=f"images/rooms/{filename}")
    default_image = os.path.join(ROOMS_DIR, "default.jpg")
    if os.path.isfile(default_image):
        return url_for("static", filename="images/rooms/default.jpg")
    return ""


def booking_conflicts(conn, room_id, check_in, check_out, exclude_booking_id=None):
    """Совместимый адаптер к сервисному правилу доступности номера."""
    from services.booking import room_is_available
    return not room_is_available(conn, room_id, check_in, check_out, exclude_booking_id)


def next_id(conn, table, prefix, field):
    """Генерирует следующий ID без зависимости от COUNT(), поэтому удаление записей не ломает IDs."""
    # Identifiers cannot be SQL parameters; allow only known schema identifiers.
    allowed = {
        ("Бронирования", "ID_Бронирования"),
        ("Счета", "ID_Счета"),
        ("Клиенты", "ID_Клиента"),
        ("Номера", "ID_Номера"),
    }
    if (table, field) not in allowed or not re.fullmatch(r"[A-ZА-ЯЁ_]+", prefix):
        raise ValueError("Недопустимые параметры генерации ID")
    rows = conn.execute(
        f"SELECT {field} FROM {table} WHERE {field} LIKE ?",
        (f"{prefix}%",),
    ).fetchall()
    max_number = 0
    for row in rows:
        value = str(row[field] or "")
        suffix = value[len(prefix):]
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return f"{prefix}{max_number + 1:03d}"


def booking_total(conn, room_id, check_in, check_out):
    room = conn.execute("SELECT Цена_за_сутки FROM Номера WHERE ID_Номера = ?", (room_id,)).fetchone()
    if not room:
        return 0.0, 0
    start = datetime.strptime(str(check_in), "%Y-%m-%d").date()
    end = datetime.strptime(str(check_out), "%Y-%m-%d").date()
    nights = (end - start).days
    return max(nights, 0) * float(room["Цена_за_сутки"]), max(nights, 0)


def sync_room_statuses():
    """Пересчитывает фактический статус каждого номера из бронирований.

    Правило:
    - сегодня проживание -> «Занят»;
    - есть будущая активная бронь -> «Будет занят»;
    - иначе -> «Свободен».
    Прошедшие подтверждённые/заселённые брони переводятся в «Завершено».
    """
    conn = get_db()
    try:
        today = datetime.now().date().strftime("%Y-%m-%d")
        conn.execute("""
            UPDATE Бронирования
            SET Статус = 'Завершено'
            WHERE Статус IN ('Подтверждено', 'Заселен')
              AND Дата_выезда <= ?
        """, (today,))

        room_columns = {row['name'] for row in conn.execute("PRAGMA table_info(Номера)").fetchall()}
        if 'Статус_обслуживания' in room_columns:
            conn.execute("UPDATE Номера SET Статус = 'Свободен' WHERE COALESCE(Статус_обслуживания,'') = ''")
        else:
            conn.execute("UPDATE Номера SET Статус = 'Свободен'")
        conn.execute("""
            UPDATE Номера
            SET Статус = 'Занят'
            WHERE COALESCE(Статус_обслуживания,'') = ''
              AND ID_Номера IN (
                SELECT DISTINCT ID_Номера
                FROM Бронирования
                WHERE Статус IN ('Подтверждено', 'Заселен')
                  AND Дата_заезда <= ?
                  AND Дата_выезда > ?
            )
        """, (today, today))
        conn.execute("""
            UPDATE Номера
            SET Статус = 'Будет занят'
            WHERE Статус = 'Свободен'
              AND COALESCE(Статус_обслуживания,'') = ''
              AND ID_Номера IN (
                SELECT DISTINCT ID_Номера
                FROM Бронирования
                WHERE Статус IN ('Подтверждено', 'Заселен')
                  AND Дата_заезда > ?
              )
        """, (today,))
        conn.commit()
        return True
    finally:
        conn.close()


def register_context_processors(app):
    @app.context_processor
    def utility_processor():
        return {
            "now": datetime.now(),
            "today": datetime.now().date(),
            "timedelta": timedelta,
            "get_room_image": get_room_image,
        }


def safe_csv_value(value):
    """Prevents spreadsheet formula injection in exported CSV files."""
    text = '' if value is None else str(value)
    if text[:1] in ('=', '+', '-', '@'):
        return "'" + text
    return text
