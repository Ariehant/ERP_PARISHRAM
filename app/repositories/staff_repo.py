"""Staff repository — CRUD + paged list + dropdown helpers."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.models.people import Staff


def _row_to_staff(row: sqlite3.Row) -> Staff:
    return Staff(
        id=row["id"],
        emp_code=row["emp_code"],
        name=row["name"],
        role=row["role"],
        phone=row["phone"],
        email=row["email"],
        joining_date=row["joining_date"],
        qualification=row["qualification"],
        is_active=bool(row["is_active"]),
    )


_COLS = "id, emp_code, name, role, phone, email, joining_date, qualification, is_active"


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def create(conn: sqlite3.Connection, staff: Staff) -> int:
    cur = conn.execute(
        """
        INSERT INTO staff (
            emp_code, name, role, phone, email, joining_date, qualification, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            staff.emp_code,
            staff.name,
            staff.role,
            staff.phone,
            staff.email,
            staff.joining_date,
            staff.qualification,
            1 if staff.is_active else 0,
        ),
    )
    return int(cur.lastrowid)


def update(conn: sqlite3.Connection, staff: Staff) -> None:
    if staff.id is None:
        raise ValueError("update requires staff.id")
    conn.execute(
        """
        UPDATE staff SET
            emp_code = ?, name = ?, role = ?, phone = ?, email = ?,
            joining_date = ?, qualification = ?, is_active = ?
        WHERE id = ?
        """,
        (
            staff.emp_code,
            staff.name,
            staff.role,
            staff.phone,
            staff.email,
            staff.joining_date,
            staff.qualification,
            1 if staff.is_active else 0,
            staff.id,
        ),
    )


def delete(conn: sqlite3.Connection, staff_id: int) -> None:
    conn.execute("DELETE FROM staff WHERE id = ?", (staff_id,))


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def get(conn: sqlite3.Connection, staff_id: int) -> Staff | None:
    cur = conn.execute(f"SELECT {_COLS} FROM staff WHERE id = ?", (staff_id,))
    row = cur.fetchone()
    return _row_to_staff(row) if row else None


def get_by_emp_code(conn: sqlite3.Connection, emp_code: str) -> Staff | None:
    cur = conn.execute(f"SELECT {_COLS} FROM staff WHERE emp_code = ?", (emp_code,))
    row = cur.fetchone()
    return _row_to_staff(row) if row else None


def emp_code_exists(
    conn: sqlite3.Connection, emp_code: str, *, exclude_id: int | None = None
) -> bool:
    if exclude_id is None:
        cur = conn.execute("SELECT 1 FROM staff WHERE emp_code = ? LIMIT 1", (emp_code,))
    else:
        cur = conn.execute(
            "SELECT 1 FROM staff WHERE emp_code = ? AND id != ? LIMIT 1",
            (emp_code, exclude_id),
        )
    return cur.fetchone() is not None


def _build_filter(
    *, search: str | None, role: str | None, is_active: bool | None
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if search:
        like = f"%{search.strip()}%"
        clauses.append("(emp_code LIKE ? OR name LIKE ? OR role LIKE ?)")
        params.extend([like, like, like])
    if role:
        clauses.append("role = ?")
        params.append(role)
    if is_active is not None:
        clauses.append("is_active = ?")
        params.append(1 if is_active else 0)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def count(
    conn: sqlite3.Connection,
    *,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> int:
    where, params = _build_filter(search=search, role=role, is_active=is_active)
    cur = conn.execute(f"SELECT COUNT(*) FROM staff{where}", params)
    return int(cur.fetchone()[0])


def list_page(
    conn: sqlite3.Connection,
    *,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Staff]:
    where, params = _build_filter(search=search, role=role, is_active=is_active)
    sql = f"SELECT {_COLS} FROM staff{where} ORDER BY name COLLATE NOCASE, id LIMIT ? OFFSET ?"
    cur = conn.execute(sql, [*params, limit, offset])
    return [_row_to_staff(r) for r in cur.fetchall()]


def list_active_teachers(conn: sqlite3.Connection) -> list[Staff]:
    """Used to populate the class-teacher dropdown."""
    cur = conn.execute(
        f"SELECT {_COLS} FROM staff WHERE role = 'teacher' AND is_active = 1 "
        "ORDER BY name COLLATE NOCASE, id"
    )
    return [_row_to_staff(r) for r in cur.fetchall()]
