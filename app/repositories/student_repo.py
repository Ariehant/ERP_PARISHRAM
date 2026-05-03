"""Student repository — all SQL for the ``students`` table.

Returns ``Student`` dataclasses. Supports paged keyset-friendly listing with
search + filters; the count helper uses the same WHERE clause.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.models.people import Student

# Single source of truth for the SELECT column list. Keep the order in sync
# with ``_row_to_student`` so refactors stay safe.
_COLS = (
    "id, admission_no, roll_no, first_name, last_name, dob, gender, "
    "blood_group, photo_path, class_id, admission_date, status, father_name, "
    "father_phone, father_occupation, mother_name, mother_phone, "
    "mother_occupation, guardian_name, guardian_phone, address, city, state, "
    "pincode, aadhaar, prev_school, category, religion, created_at, updated_at"
)


def _row_to_student(row: sqlite3.Row) -> Student:
    return Student(
        id=row["id"],
        admission_no=row["admission_no"],
        roll_no=row["roll_no"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        dob=row["dob"],
        gender=row["gender"],
        blood_group=row["blood_group"],
        photo_path=row["photo_path"],
        class_id=row["class_id"],
        admission_date=row["admission_date"],
        status=row["status"],
        father_name=row["father_name"],
        father_phone=row["father_phone"],
        father_occupation=row["father_occupation"],
        mother_name=row["mother_name"],
        mother_phone=row["mother_phone"],
        mother_occupation=row["mother_occupation"],
        guardian_name=row["guardian_name"],
        guardian_phone=row["guardian_phone"],
        address=row["address"],
        city=row["city"],
        state=row["state"],
        pincode=row["pincode"],
        aadhaar=row["aadhaar"],
        prev_school=row["prev_school"],
        category=row["category"],
        religion=row["religion"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def create(conn: sqlite3.Connection, student: Student) -> int:
    cur = conn.execute(
        """
        INSERT INTO students (
            admission_no, roll_no, first_name, last_name, dob, gender,
            blood_group, photo_path, class_id, admission_date, status,
            father_name, father_phone, father_occupation,
            mother_name, mother_phone, mother_occupation,
            guardian_name, guardian_phone,
            address, city, state, pincode,
            aadhaar, prev_school, category, religion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student.admission_no,
            student.roll_no,
            student.first_name,
            student.last_name,
            student.dob,
            student.gender,
            student.blood_group,
            student.photo_path,
            student.class_id,
            student.admission_date,
            student.status,
            student.father_name,
            student.father_phone,
            student.father_occupation,
            student.mother_name,
            student.mother_phone,
            student.mother_occupation,
            student.guardian_name,
            student.guardian_phone,
            student.address,
            student.city,
            student.state,
            student.pincode,
            student.aadhaar,
            student.prev_school,
            student.category,
            student.religion,
        ),
    )
    return int(cur.lastrowid)


def update(conn: sqlite3.Connection, student: Student) -> None:
    if student.id is None:
        raise ValueError("update requires student.id")
    conn.execute(
        """
        UPDATE students SET
            admission_no = ?, roll_no = ?, first_name = ?, last_name = ?,
            dob = ?, gender = ?, blood_group = ?, photo_path = ?,
            class_id = ?, admission_date = ?, status = ?,
            father_name = ?, father_phone = ?, father_occupation = ?,
            mother_name = ?, mother_phone = ?, mother_occupation = ?,
            guardian_name = ?, guardian_phone = ?,
            address = ?, city = ?, state = ?, pincode = ?,
            aadhaar = ?, prev_school = ?, category = ?, religion = ?,
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            student.admission_no,
            student.roll_no,
            student.first_name,
            student.last_name,
            student.dob,
            student.gender,
            student.blood_group,
            student.photo_path,
            student.class_id,
            student.admission_date,
            student.status,
            student.father_name,
            student.father_phone,
            student.father_occupation,
            student.mother_name,
            student.mother_phone,
            student.mother_occupation,
            student.guardian_name,
            student.guardian_phone,
            student.address,
            student.city,
            student.state,
            student.pincode,
            student.aadhaar,
            student.prev_school,
            student.category,
            student.religion,
            student.id,
        ),
    )


def set_status(conn: sqlite3.Connection, student_id: int, status: str) -> None:
    conn.execute(
        "UPDATE students SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, student_id),
    )


def delete(conn: sqlite3.Connection, student_id: int) -> None:
    """Hard delete. ON DELETE CASCADE removes attendance/marks/fees rows."""
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def get(conn: sqlite3.Connection, student_id: int) -> Student | None:
    cur = conn.execute(f"SELECT {_COLS} FROM students WHERE id = ?", (student_id,))
    row = cur.fetchone()
    return _row_to_student(row) if row else None


def get_by_admission_no(conn: sqlite3.Connection, admission_no: str) -> Student | None:
    cur = conn.execute(f"SELECT {_COLS} FROM students WHERE admission_no = ?", (admission_no,))
    row = cur.fetchone()
    return _row_to_student(row) if row else None


def admission_no_exists(
    conn: sqlite3.Connection, admission_no: str, *, exclude_id: int | None = None
) -> bool:
    if exclude_id is None:
        cur = conn.execute("SELECT 1 FROM students WHERE admission_no = ? LIMIT 1", (admission_no,))
    else:
        cur = conn.execute(
            "SELECT 1 FROM students WHERE admission_no = ? AND id != ? LIMIT 1",
            (admission_no, exclude_id),
        )
    return cur.fetchone() is not None


def _build_filter(
    *, search: str | None, class_id: int | None, status: str | None
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if search:
        like = f"%{search.strip()}%"
        clauses.append(
            "(admission_no LIKE ? OR first_name LIKE ? OR last_name LIKE ? "
            "OR (first_name || ' ' || COALESCE(last_name, '')) LIKE ?)"
        )
        params.extend([like, like, like, like])
    if class_id is not None:
        clauses.append("class_id = ?")
        params.append(class_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def count(
    conn: sqlite3.Connection,
    *,
    search: str | None = None,
    class_id: int | None = None,
    status: str | None = None,
) -> int:
    where, params = _build_filter(search=search, class_id=class_id, status=status)
    cur = conn.execute(f"SELECT COUNT(*) FROM students{where}", params)
    return int(cur.fetchone()[0])


def list_page(
    conn: sqlite3.Connection,
    *,
    search: str | None = None,
    class_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Student]:
    where, params = _build_filter(search=search, class_id=class_id, status=status)
    sql = (
        f"SELECT {_COLS} FROM students{where} "
        "ORDER BY first_name COLLATE NOCASE, last_name COLLATE NOCASE, id "
        "LIMIT ? OFFSET ?"
    )
    cur = conn.execute(sql, [*params, limit, offset])
    return [_row_to_student(r) for r in cur.fetchall()]


def list_all_for_export(
    conn: sqlite3.Connection,
    *,
    search: str | None = None,
    class_id: int | None = None,
    status: str | None = None,
) -> list[Student]:
    """Stream-style "all rows that match" — used by the exporter (worker thread)."""
    where, params = _build_filter(search=search, class_id=class_id, status=status)
    sql = (
        f"SELECT {_COLS} FROM students{where} "
        "ORDER BY first_name COLLATE NOCASE, last_name COLLATE NOCASE, id"
    )
    cur = conn.execute(sql, params)
    return [_row_to_student(r) for r in cur.fetchall()]
