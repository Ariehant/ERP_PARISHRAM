"""Fee business logic.

Three jobs:
1. ``pending_for_student`` -- compute outstanding amount per fee head for
   a student (structure x months/instances elapsed - already paid).
2. ``collect_payment`` -- write a payment + items in one transaction with
   an atomically-allocated receipt number.
3. ``defaulters_for_class`` and ``ledger_for_student`` -- read-side
   helpers for the reports.

Frequency semantics (for the "instances elapsed" calc, capped to the
current academic year):
- ``monthly``    -> one instance per month from year-start to today, max 12.
- ``quarterly``  -> one per quarter (Apr-Jun, Jul-Sep, Oct-Dec, Jan-Mar).
- ``annual``     -> one for the whole year (always 1 once year started).
- ``one_time``   -> one for the whole year (same as annual).

If a student joined later in the year, instances are still computed from
the year start. The school can record a separate adjustment payment if
they pro-rate. Documented in PHASE_6_NOTES.md.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date

from app.db.connection import transaction
from app.models.fee import FeePayment, FeePaymentItem, FeeStructure
from app.repositories import (
    counters_repo,
    fee_payment_repo,
    fee_structure_repo,
    school_repo,
    student_repo,
)
from app.utils.errors import ValidationError
from app.utils.formatters import parse_iso_date

log = logging.getLogger(__name__)

VALID_FREQUENCIES = ("monthly", "quarterly", "annual", "one_time")
VALID_MODES = ("cash", "upi", "cheque", "card", "bank")


# ---------------------------------------------------------------------------
# Pending calculation
# ---------------------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class PendingHead:
    fee_structure_id: int
    head: str
    frequency: str
    instance_amount_paise: int
    instances_due: int
    total_due_paise: int
    paid_paise: int

    @property
    def outstanding_paise(self) -> int:
        return max(0, self.total_due_paise - self.paid_paise)


def _instances_due(frequency: str, year_start: date, year_end: date, today: date) -> int:
    """How many instances of a recurring fee have come due by ``today``.

    Capped to the academic year window.
    """
    if today < year_start:
        return 0
    if today > year_end:
        today = year_end
    months_elapsed = (today.year - year_start.year) * 12 + (today.month - year_start.month) + 1
    months_elapsed = max(0, min(12, months_elapsed))

    if frequency == "monthly":
        return months_elapsed
    if frequency == "quarterly":
        # Quarter 1 starts at month 1 of the academic year.
        return min(4, (months_elapsed + 2) // 3)
    if frequency in ("annual", "one_time"):
        return 1 if months_elapsed > 0 else 0
    raise ValueError(f"Unknown frequency: {frequency!r}")


def pending_for_student(
    conn: sqlite3.Connection,
    student_id: int,
    *,
    today: date | None = None,
) -> list[PendingHead]:
    """Per-head pending list for a student in the active year."""
    today = today or date.today()
    student = student_repo.get(conn, student_id)
    if student is None:
        raise ValidationError(f"Student #{student_id} not found.")
    if student.class_id is None:
        return []

    active = school_repo.get_active_academic_year(conn)
    if active is None or active.id is None:
        return []
    year_start = _parse_or_today(active.start_date)
    year_end = _parse_or_today(active.end_date)

    structure = fee_structure_repo.list_for_class(conn, student.class_id, active.id)
    out: list[PendingHead] = []
    for fs in structure:
        if fs.id is None:
            continue
        instances = _instances_due(fs.frequency, year_start, year_end, today)
        total_due = instances * fs.amount_paise
        paid = fee_payment_repo.total_paid_for_head(conn, student_id, fs.head)
        out.append(
            PendingHead(
                fee_structure_id=fs.id,
                head=fs.head,
                frequency=fs.frequency,
                instance_amount_paise=fs.amount_paise,
                instances_due=instances,
                total_due_paise=total_due,
                paid_paise=paid,
            )
        )
    return out


def _parse_or_today(iso: str | None) -> date:
    if not iso:
        return date.today()
    return date.fromisoformat(iso)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class PaymentItemInput:
    head: str
    amount_paise: int
    fee_structure_id: int | None = None
    for_month: int | None = None
    for_year: int | None = None


@dataclass(slots=True, frozen=True)
class PaymentResult:
    payment_id: int
    receipt_no: str


def _format_receipt_no(year_label: str, sequence: int) -> str:
    """``RCP/YYYY-YY/NNNNN`` per the brief."""
    return f"RCP/{year_label}/{sequence:05d}"


def _next_receipt_no(conn: sqlite3.Connection, year_label: str) -> str:
    counter_name = f"receipt_no::{year_label}"
    seq = counters_repo.next_value(conn, counter_name)
    return _format_receipt_no(year_label, seq)


def collect_payment(
    conn: sqlite3.Connection,
    *,
    student_id: int,
    payment_date: str,
    mode: str,
    items: list[PaymentItemInput],
    reference_no: str | None = None,
    remarks: str | None = None,
    collected_by: int | None = None,
) -> PaymentResult:
    """Create a fee_payments row + fee_payment_items rows in one transaction.

    Receipt number is allocated atomically from the counters table inside
    the same transaction.
    """
    student = student_repo.get(conn, student_id)
    if student is None:
        raise ValidationError(f"Student #{student_id} not found.")
    if mode not in VALID_MODES:
        raise ValidationError(f"Mode must be one of {', '.join(VALID_MODES)}.", field="mode")
    try:
        payment_date = parse_iso_date(payment_date)
    except ValueError as exc:
        raise ValidationError("Payment date must be YYYY-MM-DD.", field="payment_date") from exc
    if not items:
        raise ValidationError("At least one fee head is required.")
    cleaned_items: list[PaymentItemInput] = []
    total = 0
    for it in items:
        head = (it.head or "").strip()
        if not head:
            raise ValidationError("Head cannot be blank.", field="head")
        if it.amount_paise is None or it.amount_paise <= 0:
            raise ValidationError(f"Amount for {head!r} must be positive.", field="amount_paise")
        total += it.amount_paise
        cleaned_items.append(
            PaymentItemInput(
                head=head,
                amount_paise=int(it.amount_paise),
                fee_structure_id=it.fee_structure_id,
                for_month=it.for_month,
                for_year=it.for_year,
            )
        )

    active = school_repo.get_active_academic_year(conn)
    if active is None:
        raise ValidationError("No active academic year. Set one in Settings.")
    year_label = active.label

    with transaction(conn):
        receipt_no = _next_receipt_no(conn, year_label)
        payment_id = fee_payment_repo.create_payment(
            conn,
            FeePayment(
                id=None,
                student_id=student_id,
                receipt_no=receipt_no,
                payment_date=payment_date,
                amount_paise=total,
                mode=mode,
                reference_no=reference_no.strip() if reference_no else None,
                remarks=remarks.strip() if remarks else None,
                collected_by=collected_by,
            ),
        )
        for it in cleaned_items:
            fee_payment_repo.create_item(
                conn,
                FeePaymentItem(
                    id=None,
                    fee_payment_id=payment_id,
                    fee_structure_id=it.fee_structure_id,
                    head=it.head,
                    amount_paise=it.amount_paise,
                    for_month=it.for_month,
                    for_year=it.for_year,
                ),
            )

    log.info("Collected payment id=%s receipt=%s", payment_id, receipt_no)
    return PaymentResult(payment_id=payment_id, receipt_no=receipt_no)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class StudentDefaulter:
    student_id: int
    admission_no: str
    name: str
    class_label: str | None
    outstanding_paise: int


def defaulters_for_class(
    conn: sqlite3.Connection,
    class_id: int,
    *,
    today: date | None = None,
) -> list[StudentDefaulter]:
    """Active students in ``class_id`` with outstanding > 0."""
    today = today or date.today()
    out: list[StudentDefaulter] = []
    cur = conn.execute(
        "SELECT s.id, s.admission_no, s.first_name, s.last_name, "
        "       c.name, c.section "
        "FROM students s "
        "LEFT JOIN classes c ON c.id = s.class_id "
        "WHERE s.class_id = ? AND s.status = 'active' "
        "ORDER BY s.roll_no IS NULL, s.roll_no, s.first_name COLLATE NOCASE, s.id",
        (class_id,),
    )
    rows = cur.fetchall()
    for r in rows:
        sid, adm, first, last, cname, csec = r
        pending = pending_for_student(conn, sid, today=today)
        outstanding = sum(p.outstanding_paise for p in pending)
        if outstanding > 0:
            out.append(
                StudentDefaulter(
                    student_id=sid,
                    admission_no=adm,
                    name=" ".join(filter(None, [first, last])),
                    class_label=(f"{cname}-{csec}" if cname and csec else None),
                    outstanding_paise=outstanding,
                )
            )
    return out


def ledger_for_student(conn: sqlite3.Connection, student_id: int) -> list[dict]:
    """Flat ledger (chronological): one row per payment item."""
    return fee_payment_repo.list_items_for_student(conn, student_id)


# ---------------------------------------------------------------------------
# Structure save (replace-all per class+year)
# ---------------------------------------------------------------------------
def save_structure(
    conn: sqlite3.Connection,
    *,
    class_id: int,
    academic_year_id: int,
    rows: list[FeeStructure],
) -> None:
    cleaned: list[FeeStructure] = []
    seen_keys: set[tuple[str, str, int | None]] = set()
    for fs in rows:
        head = (fs.head or "").strip()
        if not head:
            raise ValidationError("Head cannot be blank.", field="head")
        freq = (fs.frequency or "").strip().lower()
        if freq not in VALID_FREQUENCIES:
            raise ValidationError(
                f"Frequency for {head!r} must be one of {', '.join(VALID_FREQUENCIES)}.",
                field="frequency",
            )
        if fs.amount_paise is None or fs.amount_paise <= 0:
            raise ValidationError(f"Amount for {head!r} must be positive.", field="amount_paise")
        due_month = fs.due_month
        if freq == "monthly" and due_month is not None and not 1 <= due_month <= 12:
            raise ValidationError(f"Due month for {head!r} must be 1-12.", field="due_month")
        key = (head.lower(), freq, due_month)
        if key in seen_keys:
            raise ValidationError(
                f"Duplicate row for head {head!r} / {freq} / month {due_month}.",
            )
        seen_keys.add(key)
        cleaned.append(
            FeeStructure(
                id=fs.id,
                class_id=class_id,
                academic_year_id=academic_year_id,
                head=head,
                amount_paise=int(fs.amount_paise),
                frequency=freq,
                due_month=due_month,
            )
        )

    with transaction(conn):
        fee_structure_repo.replace_for_class(conn, class_id, academic_year_id, cleaned)
    log.info(
        "Saved %d fee-structure row(s) for class=%s year=%s",
        len(cleaned),
        class_id,
        academic_year_id,
    )
