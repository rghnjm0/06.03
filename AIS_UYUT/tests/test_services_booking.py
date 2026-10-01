"""Unit tests for services.booking domain logic."""
import pytest
from datetime import date, timedelta
from services.booking import (
    parse_stay_dates, validate_guests, nights_between, BookingError, room_is_available,
)


def test_parse_stay_dates_ok():
    today = date.today()
    start, end = parse_stay_dates(
        today.isoformat(),
        (today + timedelta(days=3)).isoformat(),
        today=today,
    )
    assert (end - start).days == 3


def test_parse_stay_dates_rejects_past():
    today = date.today()
    with pytest.raises(BookingError):
        parse_stay_dates(
            (today - timedelta(days=2)).isoformat(),
            (today + timedelta(days=1)).isoformat(),
            today=today,
        )


def test_parse_stay_dates_rejects_long_stay():
    today = date.today()
    with pytest.raises(BookingError):
        parse_stay_dates(
            today.isoformat(),
            (today + timedelta(days=120)).isoformat(),
            today=today,
        )


def test_validate_guests():
    assert validate_guests(2, 4) == 2
    with pytest.raises(BookingError):
        validate_guests(5, 2)


def test_nights_between():
    assert nights_between("2026-01-01", "2026-01-04") == 3
