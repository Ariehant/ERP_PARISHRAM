"""Exam repository -- CRUD scoped to academic year."""

from __future__ import annotations

import sqlite3

from app.models.exam import Exam

_COLS = "id, name, academic_year_id, exam_type, start_date, end_date, weightage"


def _row_to_exam(row: sqlite3.Row) -> Exam:
    return Exam(
        id=row["id"],
        name=row["name"],
        academic_year_id=row["academic_year_id"],
        exam_type=row["exam_type"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        weightage=row["weightage"],
    )


def create(conn: sqlite3.Connection, exam: Exam) -> int:
    cur = conn.execute(
        "INSERT INTO exams (name, academic_year_id, exam_type, start_date, end_date, weightage) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            exam.name,
            exam.academic_year_id,
            exam.exam_type,
            exam.start_date,
            exam.end_date,
            exam.weightage,
        ),
    )
    return int(cur.lastrowid)


def update(conn: sqlite3.Connection, exam: Exam) -> None:
    if exam.id is None:
        raise ValueError("update requires exam.id")
    conn.execute(
        "UPDATE exams SET name = ?, academic_year_id = ?, exam_type = ?, "
        "start_date = ?, end_date = ?, weightage = ? WHERE id = ?",
        (
            exam.name,
            exam.academic_year_id,
            exam.exam_type,
            exam.start_date,
            exam.end_date,
            exam.weightage,
            exam.id,
        ),
    )


def delete(conn: sqlite3.Connection, exam_id: int) -> None:
    """Hard delete. ON DELETE CASCADE removes related marks rows."""
    conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))


def get(conn: sqlite3.Connection, exam_id: int) -> Exam | None:
    cur = conn.execute(f"SELECT {_COLS} FROM exams WHERE id = ?", (exam_id,))
    row = cur.fetchone()
    return _row_to_exam(row) if row else None


def list_for_year(conn: sqlite3.Connection, academic_year_id: int) -> list[Exam]:
    cur = conn.execute(
        f"SELECT {_COLS} FROM exams WHERE academic_year_id = ? "
        "ORDER BY start_date IS NULL, start_date, id",
        (academic_year_id,),
    )
    return [_row_to_exam(r) for r in cur.fetchall()]


def count_marks_for_exam(conn: sqlite3.Connection, exam_id: int) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM marks WHERE exam_id = ?", (exam_id,))
    return int(cur.fetchone()[0])
