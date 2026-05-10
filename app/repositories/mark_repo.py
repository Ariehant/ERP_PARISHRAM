"""Marks repository -- upsert + lookup keyed by (exam, student, subject)."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.models.exam import Mark


def _row_to_mark(row: sqlite3.Row) -> Mark:
    return Mark(
        id=row["id"],
        exam_id=row["exam_id"],
        student_id=row["student_id"],
        subject_id=row["subject_id"],
        max_marks=row["max_marks"],
        marks_obtained=row["marks_obtained"],
        grade=row["grade"],
        remarks=row["remarks"],
    )


def upsert(conn: sqlite3.Connection, mark: Mark) -> None:
    """Insert or replace a single mark row.

    Caller is expected to wrap calls in a transaction.
    """
    conn.execute(
        """
        INSERT INTO marks (exam_id, student_id, subject_id, marks_obtained,
                           max_marks, grade, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exam_id, student_id, subject_id) DO UPDATE SET
            marks_obtained = excluded.marks_obtained,
            max_marks      = excluded.max_marks,
            grade          = excluded.grade,
            remarks        = excluded.remarks
        """,
        (
            mark.exam_id,
            mark.student_id,
            mark.subject_id,
            mark.marks_obtained,
            mark.max_marks,
            mark.grade,
            mark.remarks,
        ),
    )


def delete_one(conn: sqlite3.Connection, exam_id: int, student_id: int, subject_id: int) -> None:
    conn.execute(
        "DELETE FROM marks WHERE exam_id = ? AND student_id = ? AND subject_id = ?",
        (exam_id, student_id, subject_id),
    )


def list_for_class_and_exam(
    conn: sqlite3.Connection, class_id: int, exam_id: int
) -> list[dict[str, Any]]:
    """Return ``{student_id, subject_id, marks_obtained, max_marks, grade}`` rows
    for every mark already saved for the class+exam combo. The marks-entry
    grid joins this with the class roster + subjects to seed initial values.
    """
    cur = conn.execute(
        """
        SELECT m.student_id, m.subject_id, m.marks_obtained, m.max_marks, m.grade
        FROM marks m
        INNER JOIN students s ON s.id = m.student_id
        WHERE s.class_id = ? AND m.exam_id = ?
        """,
        (class_id, exam_id),
    )
    return [
        {
            "student_id": r[0],
            "subject_id": r[1],
            "marks_obtained": r[2],
            "max_marks": r[3],
            "grade": r[4],
        }
        for r in cur.fetchall()
    ]


def list_for_student_in_exam(conn: sqlite3.Connection, student_id: int, exam_id: int) -> list[Mark]:
    cur = conn.execute(
        "SELECT id, exam_id, student_id, subject_id, marks_obtained, max_marks, "
        "grade, remarks FROM marks WHERE student_id = ? AND exam_id = ? "
        "ORDER BY subject_id",
        (student_id, exam_id),
    )
    return [_row_to_mark(r) for r in cur.fetchall()]
