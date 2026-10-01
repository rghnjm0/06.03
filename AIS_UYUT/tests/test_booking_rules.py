from datetime import date
import pytest
from services.booking import (
    BookingError, calc_stay_total, nights_between, parse_stay_dates, validate_guests,
)


def test_parse_stay_dates_accepts_valid_range():
    start, end = parse_stay_dates("2026-10-10", "2026-10-12", today=date(2026, 10, 1))
    assert (end - start).days == 2


@pytest.mark.parametrize(("check_in", "check_out"), [("bad", "2026-10-12"), ("2026-10-12", "2026-10-12"), ("2026-09-30", "2026-10-12")])
def test_parse_stay_dates_rejects_invalid_ranges(check_in, check_out):
    with pytest.raises(BookingError):
        parse_stay_dates(check_in, check_out, today=date(2026, 10, 1))


def test_validate_guests_enforces_capacity():
    assert validate_guests(2, 3) == 2
    with pytest.raises(BookingError):
        validate_guests(4, 3)


def test_nights_and_total_include_services():
    assert nights_between("2026-10-10", "2026-10-13") == 3
    assert calc_stay_total(1000, "2026-10-10", "2026-10-12", [{"Цена": 250}]) == 2250
