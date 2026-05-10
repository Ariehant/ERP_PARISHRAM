"""Convert paise to an Indian-English words string.

Used by receipts: "Total in words: Rupees One Lakh Twenty Three Thousand
Four Hundred Fifty Six and Seventy Eight Paise Only".

Indian numbering uses Crore (10^7), Lakh (10^5), Thousand (10^3), Hundred.
"""

from __future__ import annotations

_ONES = (
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
_TENS = (
    "",
    "",
    "Twenty",
    "Thirty",
    "Forty",
    "Fifty",
    "Sixty",
    "Seventy",
    "Eighty",
    "Ninety",
)


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    if ones == 0:
        return _TENS[tens]
    return f"{_TENS[tens]} {_ONES[ones]}"


def _three_digits(n: int) -> str:
    """0..999 -> words."""
    hundreds, rest = divmod(n, 100)
    parts: list[str] = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} Hundred")
    if rest:
        parts.append(_two_digits(rest))
    return " ".join(parts) if parts else ""


def _rupees_to_words(rupees: int) -> str:
    if rupees == 0:
        return "Zero"
    parts: list[str] = []
    crore, rest = divmod(rupees, 10_000_000)
    if crore:
        parts.append(f"{_indian_number(crore)} Crore")
    lakh, rest = divmod(rest, 100_000)
    if lakh:
        parts.append(f"{_two_digits(lakh)} Lakh")
    thousand, rest = divmod(rest, 1_000)
    if thousand:
        parts.append(f"{_two_digits(thousand)} Thousand")
    if rest:
        parts.append(_three_digits(rest))
    return " ".join(parts)


def _indian_number(n: int) -> str:
    """Render any non-negative integer in Indian groupings."""
    if n < 100:
        return _two_digits(n)
    if n < 1_000:
        return _three_digits(n)
    parts: list[str] = []
    crore, rest = divmod(n, 10_000_000)
    if crore:
        parts.append(f"{_indian_number(crore)} Crore")
    lakh, rest = divmod(rest, 100_000)
    if lakh:
        parts.append(f"{_two_digits(lakh)} Lakh")
    thousand, rest = divmod(rest, 1_000)
    if thousand:
        parts.append(f"{_two_digits(thousand)} Thousand")
    if rest:
        parts.append(_three_digits(rest))
    return " ".join(parts)


def paise_to_words(paise: int) -> str:
    """Convert integer paise to a friendly INR phrase suitable for receipts."""
    if not isinstance(paise, int):
        raise TypeError(f"expected int, got {type(paise).__name__}")
    sign = "Minus " if paise < 0 else ""
    paise = abs(paise)
    rupees, p = divmod(paise, 100)

    if rupees == 0 and p == 0:
        return f"{sign}Zero Rupees Only"

    pieces: list[str] = []
    if rupees:
        pieces.append(f"Rupees {_rupees_to_words(rupees)}")
    if p:
        # Receipts read better with "Rupees" prefix even for paise-only amounts.
        prefix = "" if rupees else "Rupees "
        pieces.append(f"{prefix}{_two_digits(p)} Paise")
    return f"{sign}{' and '.join(pieces)} Only"
