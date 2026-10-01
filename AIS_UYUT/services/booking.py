"""Бизнес-правила бронирования и промокодов без зависимости от Flask."""
from datetime import datetime, date


class BookingError(ValueError):
    """Ожидаемая ошибка валидации бронирования."""


def room_is_available(conn, room_id, check_in, check_out, exclude_booking_id=None):
    """True, если номер свободен на весь интервал проживания."""
    query = """
        SELECT ID_Бронирования FROM Бронирования
        WHERE ID_Номера = ? AND Статус IN ('Подтверждено', 'Заселен')
          AND NOT (Дата_выезда <= ? OR Дата_заезда >= ?)
    """
    params = [room_id, check_in, check_out]
    if exclude_booking_id:
        query += " AND ID_Бронирования <> ?"
        params.append(exclude_booking_id)
    return conn.execute(query, params).fetchone() is None


def parse_stay_dates(check_in: str, check_out: str, today=None):
    """Парсит и проверяет даты заезда/выезда. Возвращает (date, date)."""
    today = today or datetime.now().date()
    try:
        start = datetime.strptime(check_in, "%Y-%m-%d").date()
        end = datetime.strptime(check_out, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise BookingError("Укажите корректные даты.") from exc
    if start < today:
        raise BookingError("Дата заезда не может быть в прошлом.")
    if end <= start:
        raise BookingError("Дата выезда должна быть позже даты заезда.")
    if (end - start).days > 90:
        raise BookingError("Период проживания не может превышать 90 дней.")
    return start, end


def validate_guests(guests: int, capacity: int):
    if guests < 1 or guests > capacity:
        raise BookingError(f"Вместимость номера — до {capacity} гостей.")
    return guests


def nights_between(check_in: str, check_out: str) -> int:
    start = datetime.strptime(check_in, "%Y-%m-%d").date()
    end = datetime.strptime(check_out, "%Y-%m-%d").date()
    return max(0, (end - start).days)


def calc_stay_total(price_per_night: float, check_in: str, check_out: str, service_rows) -> float:
    """Сумма проживания + выбранные услуги."""
    nights = nights_between(check_in, check_out)
    total = float(price_per_night) * nights
    for row in service_rows:
        total += float(row["Цена"] if hasattr(row, "keys") else row[1])
    return round(total, 2)


def resolve_promo(conn, code: str, client_id: str, base_total: float):
    """Возвращает (discount_amount, promo_code) или (0, '')."""
    if not code:
        return 0.0, ""
    code = code.strip().upper()
    row = conn.execute(
        "SELECT Код, Скидка, Лимит, Использовано, Действует_до, Активен FROM Промокоды WHERE upper(Код)=?",
        (code,),
    ).fetchone()
    if not row or not row["Активен"]:
        raise BookingError("Промокод недействителен.")
    if row["Действует_до"]:
        until = datetime.strptime(row["Действует_до"], "%Y-%m-%d").date()
        if datetime.now().date() > until:
            raise BookingError("Срок действия промокода истёк.")
    if row["Лимит"] is not None and row["Использовано"] is not None and row["Использовано"] >= row["Лимит"]:
        raise BookingError("Лимит промокода исчерпан.")
    used = conn.execute(
        "SELECT 1 FROM Использованные_промокоды WHERE Код=? AND ID_Клиента=?",
        (row["Код"], client_id),
    ).fetchone()
    if used:
        raise BookingError("Вы уже использовали этот промокод.")
    discount = round(base_total * float(row["Скидка"]) / 100.0, 2)
    return discount, row["Код"]


def create_confirmed_booking(
    conn,
    *,
    client_id: str,
    room_id: str,
    check_in: str,
    check_out: str,
    guests: int,
    total: float,
    selected_service_rows,
    promo_code: str = "",
    discount: float = 0.0,
    next_id_fn,
):
    """Создаёт бронь, услуги, счёт и запись об использовании промокода. Без commit."""
    if not room_is_available(conn, room_id, check_in, check_out):
        raise BookingError("Номер уже занят на выбранные даты. Выберите другой период.")
    booking_id = next_id_fn(conn, "Бронирования", "BR", "ID_Бронирования")
    invoice_id = next_id_fn(conn, "Счета", "INV", "ID_Счета")
    prepayment = round(total * 0.30, 2)
    conn.execute(
        """INSERT INTO Бронирования
            (ID_Бронирования, ID_Клиента, ID_Номера, Дата_бронирования, Дата_заезда, Дата_выезда,
             Количество_гостей, Статус, Предоплата)
            VALUES (?, ?, ?, date('now'), ?, ?, ?, 'Подтверждено', ?)""",
        (booking_id, client_id, room_id, check_in, check_out, guests, prepayment),
    )
    for row in selected_service_rows:
        sid = row["ID_Услуги"]
        price = row["Цена"]
        conn.execute(
            "INSERT INTO Бронирование_Услуги(ID_Бронирования,ID_Услуги,Количество,Цена) VALUES(?,?,1,?)",
            (booking_id, sid, price),
        )
    conn.execute(
        "INSERT INTO Счета(ID_Счета,ID_Бронирования,Дата_выставления,Сумма_проживание,Оплачено) VALUES(?,?,date('now'),?,0)",
        (invoice_id, booking_id, total),
    )
    if promo_code and discount > 0:
        conn.execute(
            "INSERT INTO Использованные_промокоды(Код,ID_Клиента,ID_Бронирования) VALUES(?,?,?)",
            (promo_code, client_id, booking_id),
        )
    return booking_id, invoice_id
