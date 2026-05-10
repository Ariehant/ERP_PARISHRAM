"""Grade scale CRUD + grade lookup."""

from __future__ import annotations

import sqlite3

from app.models.grade_scale import GradeBand


def _row_to_band(row: sqlite3.Row) -> GradeBand:
    return GradeBand(
        id=row["id"],
        grade=row["grade"],
        min_percent=float(row["min_percent"]),
        max_percent=float(row["max_percent"]),
        remarks=row["remarks"],
    )


def list_all(conn: sqlite3.Connection) -> list[GradeBand]:
    cur = conn.execute(
        "SELECT id, grade, min_percent, max_percent, remarks "
        "FROM grade_scales ORDER BY min_percent DESC, id"
    )
    return [_row_to_band(r) for r in cur.fetchall()]


def grade_for_percent(conn: sqlite3.Connection, percent: float) -> str | None:
    """Return the grade letter for ``percent``, or ``None`` if none matches."""
    cur = conn.execute(
        "SELECT grade FROM grade_scales "
        "WHERE ? >= min_percent AND ? <= max_percent "
        "ORDER BY min_percent DESC LIMIT 1",
        (percent, percent),
    )
    row = cur.fetchone()
    return row[0] if row else None


def upsert(conn: sqlite3.Connection, band: GradeBand) -> int:
    if band.id is None:
        cur = conn.execute(
            "INSERT INTO grade_scales (grade, min_percent, max_percent, remarks) "
            "VALUES (?, ?, ?, ?)",
            (band.grade, band.min_percent, band.max_percent, band.remarks),
        )
        return int(cur.lastrowid)
    conn.execute(
        "UPDATE grade_scales SET grade = ?, min_percent = ?, max_percent = ?, remarks = ? "
        "WHERE id = ?",
        (band.grade, band.min_percent, band.max_percent, band.remarks, band.id),
    )
    return band.id


def delete(conn: sqlite3.Connection, band_id: int) -> None:
    conn.execute("DELETE FROM grade_scales WHERE id = ?", (band_id,))


def replace_all(conn: sqlite3.Connection, bands: list[GradeBand]) -> None:
    """Replace every row with the supplied list. Caller wraps in a transaction."""
    conn.execute("DELETE FROM grade_scales")
    for b in bands:
        conn.execute(
            "INSERT INTO grade_scales (grade, min_percent, max_percent, remarks) "
            "VALUES (?, ?, ?, ?)",
            (b.grade, b.min_percent, b.max_percent, b.remarks),
        )
