"""Бизнес-правила бронирования без зависимости от Flask."""

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
