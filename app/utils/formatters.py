"""Money and date formatting helpers. Single source of truth.

- Money is stored as integer paise. ``format_inr`` renders Indian comma style.
- Dates are stored as ISO ``YYYY-MM-DD`` strings. ``format_date`` re-renders
  them for display (default ``dd-mm-yyyy``).
"""

from __future__ import annotations

from datetime import date, datetime

from app.config import ISO_DATE_FMT, PAISE_PER_RUPEE


def _indian_grouping(integer_part: str) -> str:
    """Insert Indian-style commas: 1,23,456 (last 3, then groups of 2)."""
    if len(integer_part) <= 3:
        return integer_part
    head, tail = integer_part[:-3], integer_part[-3:]
    # Insert a comma every 2 digits from the right of ``head``.
    grouped = []
    while len(head) > 2:
        grouped.append(head[-2:])
        head = head[:-2]
    if head:
        grouped.append(head)
    grouped.reverse()
    return ",".join(grouped) + "," + tail


def format_inr(paise: int, *, with_symbol: bool = True) -> str:
    """Format integer paise as Indian-grouped INR with two decimals.

    ``format_inr(12345600)`` → ``₹1,23,456.00``.
    Negative values keep the minus sign in front of the symbol.
    """
    if not isinstance(paise, int):
        raise TypeError(f"format_inr expects int paise, got {type(paise).__name__}")
    sign = "-" if paise < 0 else ""
    paise_abs = abs(paise)
    rupees, p = divmod(paise_abs, PAISE_PER_RUPEE)
    grouped = _indian_grouping(str(rupees))
    body = f"{grouped}.{p:02d}"
    return f"{sign}₹{body}" if with_symbol else f"{sign}{body}"


def format_date(iso: str | date | datetime | None, fmt: str = "dd-mm-yyyy") -> str:
    """Render an ISO date string for display.

    ``fmt`` uses friendly tokens (``dd``, ``mm``, ``yyyy``) so callers don't
    need to know strftime codes. Empty / None inputs return an empty string.
    """
    if iso is None or iso == "":
        return ""
    if isinstance(iso, datetime):
        d = iso.date()
    elif isinstance(iso, date):
        d = iso
    else:
        d = datetime.strptime(iso, ISO_DATE_FMT).date()

    mapping = {
        "yyyy": f"{d.year:04d}",
        "mm": f"{d.month:02d}",
        "dd": f"{d.day:02d}",
    }
    out = fmt
    for token, value in mapping.items():
        out = out.replace(token, value)
    return out


def parse_iso_date(value: str) -> str:
    """Validate and normalise an ISO ``YYYY-MM-DD`` date string.

    Returns the canonical ISO string. Raises ``ValueError`` on bad input.
    """
    return datetime.strptime(value, ISO_DATE_FMT).date().isoformat()


def rupees_to_paise(rupees: float | int | str) -> int:
    """Convert a rupees value (e.g. user-entered) to integer paise.

    Uses string rounding to avoid binary-float drift on fractional rupees.
    """
    # Coerce to a Decimal-like via formatted string with 2 decimals.
    from decimal import ROUND_HALF_UP, Decimal

    dec = Decimal(str(rupees)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(dec * PAISE_PER_RUPEE)
