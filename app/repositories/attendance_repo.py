"""Attendance repository.

Status semantics: ``P`` = present, ``A`` = absent, ``L`` = late, ``H`` =
holiday. The dates table is one row per ``(student_id, date)`` (UNIQUE),
so writes use ``INSERT ... ON CONFLICT`` to upsert in a single statement.
"""

from __future__ import annotations

import sqlite3
from typing import Any

VALID_STATUSES = ("P", "A", "L", "H")


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    """Return half-open ISO date range for the given month."""
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1..12 (got {month})")
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"
    return start, end


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def list_for_class_and_date(
    conn: sqlite3.Connection, class_id: int, date_iso: str
) -> list[tuple[int, int | None, str, str | None, str | None]]:
    """Return every student in the class with the saved status (or None).

    Tuple shape: ``(student_id, roll_no, first_name, last_name, status)``.
    """
    cur = conn.execute(
        """
        SELECT s.id, s.roll_no, s.first_name, s.last_name, a.status
        FROM students s
        LEFT JOIN attendance a ON a.student_id = s.id AND a.date = ?
        WHERE s.class_id = ? AND s.status = 'active'
        ORDER BY s.roll_no IS NULL, s.roll_no,
                 s.first_name COLLATE NOCASE, s.id
        """,
        (date_iso, class_id),
    )
    return [tuple(row) for row in cur.fetchall()]  # type: ignore[misc]


def list_monthly_for_class(
    conn: sqlite3.Connection, class_id: int, year: int, month: int
) -> list[tuple[int, str, str]]:
    """All ``(student_id, date, status)`` rows for the class in that month."""
    start, end = _month_bounds(year, month)
    cur = conn.execute(
        """
        SELECT a.student_id, a.date, a.status
        FROM attendance a
        INNER JOIN students s ON s.id = a.student_id
        WHERE s.class_id = ? AND a.date >= ? AND a.date < ?
        ORDER BY a.student_id, a.date
        """,
        (class_id, start, end),
    )
    return [(r[0], r[1], r[2]) for r in cur.fetchall()]


def monthly_summary_for_class(
    conn: sqlite3.Connection, class_id: int, year: int, month: int
) -> list[dict[str, Any]]:
    """Per-student counts for the class in the month.

    Returned dicts contain ``student_id``, ``roll_no``, ``first_name``,
    ``last_name``, ``p``, ``a``, ``l``, ``h``. Counts are zero for students
    with no rows that month.
    """
    start, end = _month_bounds(year, month)
    cur = conn.execute(
        """
        SELECT
            s.id,
            s.roll_no,
            s.first_name,
            s.last_name,
            COALESCE(SUM(CASE WHEN a.status = 'P' THEN 1 ELSE 0 END), 0) AS p,
            COALESCE(SUM(CASE WHEN a.status = 'A' THEN 1 ELSE 0 END), 0) AS a,
            COALESCE(SUM(CASE WHEN a.status = 'L' THEN 1 ELSE 0 END), 0) AS l,
            COALESCE(SUM(CASE WHEN a.status = 'H' THEN 1 ELSE 0 END), 0) AS h
        FROM students s
        LEFT JOIN attendance a
            ON a.student_id = s.id
            AND a.date >= ? AND a.date < ?
        WHERE s.class_id = ? AND s.status = 'active'
        GROUP BY s.id
        ORDER BY s.roll_no IS NULL, s.roll_no,
                 s.first_name COLLATE NOCASE, s.id
        """,
        (start, end, class_id),
    )
    return [
        {
            "student_id": r[0],
            "roll_no": r[1],
            "first_name": r[2],
            "last_name": r[3],
            "p": int(r[4] or 0),
            "a": int(r[5] or 0),
            "l": int(r[6] or 0),
            "h": int(r[7] or 0),
        }
        for r in cur.fetchall()
    ]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def upsert_marks(
    conn: sqlite3.Connection,
    *,
    date_iso: str,
    marks: dict[int, str],
    marked_by: int | None = None,
) -> int:
    """Upsert ``{student_id: status}`` for ``date_iso``.

    Returns the number of rows written. Caller is expected to wrap this in
    a transaction.
    """
    count = 0
    for student_id, status in marks.items():
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status {status!r} for student {student_id}")
        conn.execute(
            """
            INSERT INTO attendance (student_id, date, status, marked_by, marked_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(student_id, date) DO UPDATE SET
                status = excluded.status,
                marked_by = excluded.marked_by,
                marked_at = datetime('now')
            """,
            (student_id, date_iso, status, marked_by),
        )
        count += 1
    return count


def clear_for_class_and_date(conn: sqlite3.Connection, class_id: int, date_iso: str) -> int:
    """Delete all attendance rows for ``class_id`` on ``date_iso``. Returns count."""
    cur = conn.execute(
        """
        DELETE FROM attendance
        WHERE date = ? AND student_id IN (SELECT id FROM students WHERE class_id = ?)
        """,
        (date_iso, class_id),
    )
    return cur.rowcount or 0
