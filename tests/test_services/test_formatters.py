from __future__ import annotations

import pytest

from app.utils.formatters import format_date, format_inr, parse_iso_date, rupees_to_paise


@pytest.mark.parametrize(
    "paise,expected",
    [
        (0, "₹0.00"),
        (50, "₹0.50"),
        (12345, "₹123.45"),
        (100000, "₹1,000.00"),
        (12345600, "₹1,23,456.00"),
        (1234567890, "₹1,23,45,678.90"),
        (-12345600, "-₹1,23,456.00"),
    ],
)
def test_format_inr(paise: int, expected: str) -> None:
    assert format_inr(paise) == expected


def test_format_inr_no_symbol() -> None:
    assert format_inr(12345600, with_symbol=False) == "1,23,456.00"


def test_format_date_default() -> None:
    assert format_date("2025-04-01") == "01-04-2025"


def test_format_date_custom() -> None:
    assert format_date("2025-04-01", "yyyy/mm/dd") == "2025/04/01"


def test_format_date_empty() -> None:
    assert format_date("") == ""
    assert format_date(None) == ""


def test_parse_iso_date_round_trip() -> None:
    assert parse_iso_date("2025-04-01") == "2025-04-01"


def test_parse_iso_date_invalid() -> None:
    with pytest.raises(ValueError):
        parse_iso_date("01-04-2025")


def test_rupees_to_paise() -> None:
    assert rupees_to_paise(123) == 12300
    assert rupees_to_paise("123.45") == 12345
    assert rupees_to_paise(0.1) == 10
