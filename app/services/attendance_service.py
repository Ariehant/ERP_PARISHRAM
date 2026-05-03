"""Attendance business logic.

Percentage convention (used by the monthly summary, low-attendance, and
all PDF reports):

    effective_present = P + L      # late counts as attended
    effective_total   = P + A + L  # holidays excluded from denominator
    percentage        = effective_present / effective_total * 100

Documented in PHASE_4_NOTES.md so it's easy to revisit.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from app.db.connection import transaction
from app.repositories import attendance_repo
from app.utils.errors import ValidationError
from app.utils.formatters import parse_iso_date

log = logging.getLogger(__name__)

VALID_STATUSES = attendance_repo.VALID_STATUSES
DEFAULT_LOW_ATTENDANCE_THRESHOLD = 75.0


@dataclass(slots=True, frozen=True)
class StudentMonthlySummary:
    student_id: int
    roll_no: int | None
    first_name: str
    last_name: str | None
    p: int
    a: int
    l: int  # noqa: E741 — matches schema status code 'L'
    h: int

    @property
    def total_marked(self) -> int:
        return self.p + self.a + self.l + self.h

    @property
    def effective_total(self) -> int:
        """P + A + L (holidays excluded)."""
        return self.p + self.a + self.l

    @property
    def percentage(self) -> float:
        if self.effective_total == 0:
            return 0.0
        return ((self.p + self.l) / self.effective_total) * 100.0

    @property
    def display_name(self) -> str:
        return " ".join(filter(None, [self.first_name, self.last_name]))


# ---------------------------------------------------------------------------
def save_class_attendance(
    conn: sqlite3.Connection,
    *,
    class_id: int,
    date_iso: str,
    marks: dict[int, str],
    marked_by: int | None = None,
) -> int:
    """Save the daily attendance grid in a single transaction.

    ``marks`` maps ``student_id`` to one of ``P/A/L/H``. Students missing
    from the dict are left untouched.
    """
    if class_id is None:
        raise ValidationError("Pick a class first.", field="class_id")
    try:
        date_iso = parse_iso_date(date_iso)
    except ValueError as exc:
        raise ValidationError("Date must be in YYYY-MM-DD format.", field="date") from exc

    if not marks:
        raise ValidationError("Mark at least one student before saving.")

    # Validate every status up front so a single bad value rolls everything back.
    for student_id, status in marks.items():
        if status not in VALID_STATUSES:
            raise ValidationError(
                f"Invalid status {status!r} for student {student_id}.",
                field="status",
            )

    # Make sure every student belongs to the named class — protects against a
    # stale roster cached in the UI.
    placeholders = ",".join("?" for _ in marks)
    cur = conn.execute(
        f"SELECT id FROM students WHERE class_id = ? AND id IN ({placeholders})",
        [class_id, *marks.keys()],
    )
    valid_ids = {row[0] for row in cur.fetchall()}
    invalid = set(marks.keys()) - valid_ids
    if invalid:
        raise ValidationError(
            f"Some students are not in this class anymore: {sorted(invalid)}.",
        )

    with transaction(conn):
        count = attendance_repo.upsert_marks(
            conn, date_iso=date_iso, marks=marks, marked_by=marked_by
        )
    log.info("Saved %d attendance row(s) for class=%s date=%s", count, class_id, date_iso)
    return count


def class_summary(
    conn: sqlite3.Connection, class_id: int, year: int, month: int
) -> list[StudentMonthlySummary]:
    rows = attendance_repo.monthly_summary_for_class(conn, class_id, year, month)
    return [
        StudentMonthlySummary(
            student_id=r["student_id"],
            roll_no=r["roll_no"],
            first_name=r["first_name"],
            last_name=r["last_name"],
            p=r["p"],
            a=r["a"],
            l=r["l"],
            h=r["h"],
        )
        for r in rows
    ]


def low_attendance(
    conn: sqlite3.Connection,
    class_id: int,
    year: int,
    month: int,
    *,
    threshold: float = DEFAULT_LOW_ATTENDANCE_THRESHOLD,
) -> list[StudentMonthlySummary]:
    """Return students whose attendance is below ``threshold``.

    Students with no marked sessions (effective_total == 0) are skipped so we
    don't flag every kid in a school that hasn't started taking attendance yet.
    """
    return [
        s
        for s in class_summary(conn, class_id, year, month)
        if s.effective_total > 0 and s.percentage < threshold
    ]


def daily_register(conn: sqlite3.Connection, class_id: int, date_iso: str) -> list[dict]:
    """Return the list-for-PDF for the daily register.

    Each dict has ``roll_no``, ``name``, ``status``.
    """
    rows = attendance_repo.list_for_class_and_date(conn, class_id, date_iso)
    out = []
    for student_id, roll_no, first_name, last_name, status in rows:
        out.append(
            {
                "student_id": student_id,
                "roll_no": roll_no,
                "name": " ".join(filter(None, [first_name, last_name])),
                "status": status,
            }
        )
    return out
