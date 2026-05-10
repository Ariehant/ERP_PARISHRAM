from __future__ import annotations

import pytest

from app.utils.inr_words import paise_to_words


@pytest.mark.parametrize(
    "paise,expected",
    [
        (0, "Zero Rupees Only"),
        (100, "Rupees One Only"),
        (12300, "Rupees One Hundred Twenty Three Only"),
        (1500000, "Rupees Fifteen Thousand Only"),
        (12345600, "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six Only"),
        (
            123456789,
            "Rupees Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven and Eighty Nine Paise Only",
        ),
        (50, "Rupees Fifty Paise Only"),
        (
            10000000000,
            "Rupees Ten Crore Only",
        ),
        (
            -12300,
            "Minus Rupees One Hundred Twenty Three Only",
        ),
    ],
)
def test_paise_to_words(paise: int, expected: str) -> None:
    assert paise_to_words(paise) == expected


def test_paise_to_words_rejects_non_int() -> None:
    with pytest.raises(TypeError):
        paise_to_words(123.45)  # type: ignore[arg-type]
