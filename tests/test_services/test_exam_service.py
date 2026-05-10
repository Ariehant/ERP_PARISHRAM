from __future__ import annotations

import sqlite3

import pytest

from app.models.exam import Exam, Mark
from app.models.school import AcademicYear
from app.repositories import exam_repo, mark_repo, school_repo
from app.services import exam_service
from app.utils.errors import ValidationError


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


def test_create_normalises(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    eid = exam_service.create_exam(
        conn,
        Exam(
            id=None,
            name="  Mid-term I  ",
            academic_year_id=yid,
            exam_type="MIDTERM",
            start_date="2025-09-01",
            end_date="2025-09-08",
        ),
    )
    e = exam_repo.get(conn, eid)
    assert e is not None
    assert e.name == "Mid-term I"
    assert e.exam_type == "midterm"


def test_blank_name_rejected(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    with pytest.raises(ValidationError):
        exam_service.create_exam(conn, Exam(id=None, name=" ", academic_year_id=yid))


def test_invalid_type_rejected(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    with pytest.raises(ValidationError):
        exam_service.create_exam(
            conn,
            Exam(id=None, name="X", academic_year_id=yid, exam_type="quiz"),
        )


def test_start_after_end_rejected(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    with pytest.raises(ValidationError):
        exam_service.create_exam(
            conn,
            Exam(
                id=None,
                name="X",
                academic_year_id=yid,
                start_date="2025-09-10",
                end_date="2025-09-05",
            ),
        )


def test_delete_blocks_when_marks_recorded(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    eid = exam_service.create_exam(conn, Exam(id=None, name="X", academic_year_id=yid))
    # Set up a student + subject.
    cur = conn.execute(
        "INSERT INTO classes (name, section, academic_year_id) VALUES ('5','A',?)",
        (yid,),
    )
    cid = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO subjects (name, class_id, max_marks) VALUES ('Math', ?, 100)",
        (cid,),
    )
    sub_id = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO students (admission_no, first_name, admission_date, class_id, status) "
        "VALUES ('ADM/1', 'X', '2025-04-01', ?, 'active')",
        (cid,),
    )
    student_id = int(cur.lastrowid)
    mark_repo.upsert(
        conn,
        Mark(
            id=None,
            exam_id=eid,
            student_id=student_id,
            subject_id=sub_id,
            marks_obtained=50.0,
            max_marks=100,
        ),
    )
    with pytest.raises(ValidationError):
        exam_service.delete_exam(conn, eid)
