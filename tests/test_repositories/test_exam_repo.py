from __future__ import annotations

import sqlite3

from app.models.exam import Exam
from app.models.school import AcademicYear
from app.repositories import exam_repo, school_repo


def _year(conn: sqlite3.Connection) -> int:
    return school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label="2025-26",
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_active=True,
        ),
    )


def test_create_and_list(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    a = exam_repo.create(
        conn,
        Exam(
            id=None,
            name="Mid-term I",
            academic_year_id=yid,
            exam_type="midterm",
            start_date="2025-09-01",
            end_date="2025-09-08",
        ),
    )
    b = exam_repo.create(
        conn,
        Exam(
            id=None,
            name="Final",
            academic_year_id=yid,
            exam_type="final",
            start_date="2026-02-01",
            end_date="2026-02-10",
        ),
    )
    rows = exam_repo.list_for_year(conn, yid)
    assert {e.id for e in rows} == {a, b}
    # Sorted by start_date ascending.
    assert rows[0].id == a


def test_count_marks_for_exam(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    eid = exam_repo.create(
        conn,
        Exam(id=None, name="X", academic_year_id=yid, weightage=100),
    )
    assert exam_repo.count_marks_for_exam(conn, eid) == 0
