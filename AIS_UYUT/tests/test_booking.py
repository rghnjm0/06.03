from services.booking import room_is_available


def _booking(conn, booking_id, room_id, start, end, status="Подтверждено"):
    conn.execute(
        "INSERT INTO Бронирования VALUES (?,?,?,?,?)",
        (booking_id, room_id, start, end, status),
    )


def test_adjacent_stays_do_not_conflict(memory_db):
    _booking(memory_db, "BK001", "RM001", "2026-10-10", "2026-10-12")
    assert room_is_available(memory_db, "RM001", "2026-10-12", "2026-10-14")


def test_overlapping_stay_is_unavailable(memory_db):
    _booking(memory_db, "BK001", "RM001", "2026-10-10", "2026-10-12")
    assert not room_is_available(memory_db, "RM001", "2026-10-11", "2026-10-13")


def test_cancelled_booking_does_not_block(memory_db):
    _booking(memory_db, "BK001", "RM001", "2026-10-10", "2026-10-12", "Отменено")
    assert room_is_available(memory_db, "RM001", "2026-10-11", "2026-10-13")


def test_different_room_is_not_blocked(memory_db):
    _booking(memory_db, "BK001", "RM001", "2026-10-10", "2026-10-12")
    assert room_is_available(memory_db, "RM002", "2026-10-11", "2026-10-13")


def test_can_exclude_booking_being_edited(memory_db):
    _booking(memory_db, "BK001", "RM001", "2026-10-10", "2026-10-12")
    assert room_is_available(
        memory_db, "RM001", "2026-10-10", "2026-10-12", exclude_booking_id="BK001"
    )


def test_checked_out_booking_does_not_block(memory_db):
    _booking(memory_db, "BK001", "RM001", "2026-10-10", "2026-10-12", "Завершено")
    assert room_is_available(memory_db, "RM001", "2026-10-11", "2026-10-13")


def test_checked_in_booking_blocks(memory_db):
    _booking(memory_db, "BK001", "RM001", "2026-10-10", "2026-10-12", "Заселен")
    assert not room_is_available(memory_db, "RM001", "2026-10-11", "2026-10-13")
