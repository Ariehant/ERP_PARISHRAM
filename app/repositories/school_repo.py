"""School + AcademicYear repositories.

The first arg of every method is a ``sqlite3.Connection`` so callers (and
tests) can swap in their own connection.
"""

from __future__ import annotations

import sqlite3

from app.models.school import AcademicYear, School


# ---------------------------------------------------------------------------
# School
# ---------------------------------------------------------------------------
def _row_to_school(row: sqlite3.Row) -> School:
    return School(
        id=row["id"],
        name=row["name"],
        address=row["address"],
        phone=row["phone"],
        email=row["email"],
        logo_path=row["logo_path"],
        affiliation_no=row["affiliation_no"],
        created_at=row["created_at"],
    )


def get_first_school(conn: sqlite3.Connection) -> School | None:
    cur = conn.execute(
        "SELECT id, name, address, phone, email, logo_path, affiliation_no, created_at "
        "FROM schools ORDER BY id LIMIT 1"
    )
    row = cur.fetchone()
    return _row_to_school(row) if row else None


def school_exists(conn: sqlite3.Connection) -> bool:
    cur = conn.execute("SELECT 1 FROM schools LIMIT 1")
    return cur.fetchone() is not None


def create_school(conn: sqlite3.Connection, school: School) -> int:
    cur = conn.execute(
        """
        INSERT INTO schools (name, address, phone, email, logo_path, affiliation_no)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            school.name,
            school.address,
            school.phone,
            school.email,
            school.logo_path,
            school.affiliation_no,
        ),
    )
    return int(cur.lastrowid)


def update_school(conn: sqlite3.Connection, school: School) -> None:
    if school.id is None:
        raise ValueError("update_school requires school.id")
    conn.execute(
        """
        UPDATE schools
        SET name = ?, address = ?, phone = ?, email = ?,
            logo_path = ?, affiliation_no = ?
        WHERE id = ?
        """,
        (
            school.name,
            school.address,
            school.phone,
            school.email,
            school.logo_path,
            school.affiliation_no,
            school.id,
        ),
    )


# ---------------------------------------------------------------------------
# Academic year
# ---------------------------------------------------------------------------
def _row_to_year(row: sqlite3.Row) -> AcademicYear:
    return AcademicYear(
        id=row["id"],
        label=row["label"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        is_active=bool(row["is_active"]),
    )


def list_academic_years(conn: sqlite3.Connection) -> list[AcademicYear]:
    cur = conn.execute(
        "SELECT id, label, start_date, end_date, is_active "
        "FROM academic_years ORDER BY start_date DESC"
    )
    return [_row_to_year(r) for r in cur.fetchall()]


def get_active_academic_year(conn: sqlite3.Connection) -> AcademicYear | None:
    cur = conn.execute(
        "SELECT id, label, start_date, end_date, is_active "
        "FROM academic_years WHERE is_active = 1 ORDER BY start_date DESC LIMIT 1"
    )
    row = cur.fetchone()
    return _row_to_year(row) if row else None


def create_academic_year(conn: sqlite3.Connection, year: AcademicYear) -> int:
    cur = conn.execute(
        """
        INSERT INTO academic_years (label, start_date, end_date, is_active)
        VALUES (?, ?, ?, ?)
        """,
        (year.label, year.start_date, year.end_date, 1 if year.is_active else 0),
    )
    return int(cur.lastrowid)


def set_active_academic_year(conn: sqlite3.Connection, year_id: int) -> None:
    """Activate ``year_id`` and deactivate all others atomically."""
    conn.execute("UPDATE academic_years SET is_active = 0")
    conn.execute("UPDATE academic_years SET is_active = 1 WHERE id = ?", (year_id,))
