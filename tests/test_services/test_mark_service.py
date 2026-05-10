from __future__ import annotations

import sqlite3

import pytest

from app.models.exam import Exam
from app.models.school import AcademicYear
from app.models.structure import Class, Subject
from app.repositories import class_repo, exam_repo, mark_repo, school_repo
from app.services import mark_service
from app.utils.errors import ValidationError


def _seed(conn: sqlite3.Connection) -> tuple[int, int, list[int], list[int]]:
    yid = school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label="2025-26",
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_active=True,
        ),
    )
    cid = class_repo.create_class(conn, Class(id=None, name="5", section="A", academic_year_id=yid))
    s1 = class_repo.create_subject(conn, Subject(id=None, name="Math", class_id=cid, max_marks=100))
    s2 = class_repo.create_subject(
        conn, Subject(id=None, name="English", class_id=cid, max_marks=80)
    )
    eid = exam_repo.create(
        conn,
        Exam(id=None, name="Mid-term", academic_year_id=yid),
    )
    sids: list[int] = []
    for i in range(3):
        cur = conn.execute(
            "INSERT INTO students (admission_no, first_name, admission_date, class_id, status) "
            "VALUES (?, ?, ?, ?, 'active')",
            (f"ADM/{i + 1:03d}", f"Stu{i + 1:02d}", "2025-04-01", cid),
        )
        sids.append(int(cur.lastrowid))
    return cid, eid, sids, [s1, s2]


def test_save_class_exam_marks_auto_grades(conn: sqlite3.Connection) -> None:
    cid, eid, sids, [math_id, eng_id] = _seed(conn)
    inputs = [
        # 95/100 -> A+
        mark_service.MarkInput(student_id=sids[0], subject_id=math_id, marks_obtained=95.0),
        # 60/80 = 75% -> B+
        mark_service.MarkInput(student_id=sids[0], subject_id=eng_id, marks_obtained=60.0),
        # 30/100 -> F
        mark_service.MarkInput(student_id=sids[1], subject_id=math_id, marks_obtained=30.0),
    ]
    count = mark_service.save_class_exam_marks(conn, class_id=cid, exam_id=eid, inputs=inputs)
    assert count == 3

    rows = mark_repo.list_for_class_and_exam(conn, cid, eid)
    by_key = {(r["student_id"], r["subject_id"]): r for r in rows}
    assert by_key[(sids[0], math_id)]["grade"] == "A+"
    assert by_key[(sids[0], eng_id)]["grade"] == "B+"
    assert by_key[(sids[1], math_id)]["grade"] == "F"


def test_save_skips_blank_inputs(conn: sqlite3.Connection) -> None:
    cid, eid, sids, [math_id, _] = _seed(conn)
    inputs = [
        mark_service.MarkInput(student_id=sids[0], subject_id=math_id, marks_obtained=80.0),
        mark_service.MarkInput(student_id=sids[1], subject_id=math_id, marks_obtained=None),
    ]
    count = mark_service.save_class_exam_marks(conn, class_id=cid, exam_id=eid, inputs=inputs)
    assert count == 1


def test_save_rejects_marks_above_max(conn: sqlite3.Connection) -> None:
    cid, eid, sids, [math_id, _] = _seed(conn)
    with pytest.raises(ValidationError):
        mark_service.save_class_exam_marks(
            conn,
            class_id=cid,
            exam_id=eid,
            inputs=[
                mark_service.MarkInput(student_id=sids[0], subject_id=math_id, marks_obtained=101.0)
            ],
        )


def test_save_rejects_negative_marks(conn: sqlite3.Connection) -> None:
    cid, eid, sids, [math_id, _] = _seed(conn)
    with pytest.raises(ValidationError):
        mark_service.save_class_exam_marks(
            conn,
            class_id=cid,
            exam_id=eid,
            inputs=[
                mark_service.MarkInput(student_id=sids[0], subject_id=math_id, marks_obtained=-1.0)
            ],
        )


def test_save_rejects_subject_not_in_class(conn: sqlite3.Connection) -> None:
    cid, eid, sids, _ = _seed(conn)
    # Subject from a different class.
    other_cid = class_repo.create_class(
        conn,
        Class(
            id=None,
            name="6",
            section="A",
            academic_year_id=conn.execute("SELECT id FROM academic_years LIMIT 1").fetchone()[0],
        ),
    )
    other_sub = class_repo.create_subject(
        conn, Subject(id=None, name="Hindi", class_id=other_cid, max_marks=100)
    )
    with pytest.raises(ValidationError):
        mark_service.save_class_exam_marks(
            conn,
            class_id=cid,
            exam_id=eid,
            inputs=[
                mark_service.MarkInput(
                    student_id=sids[0], subject_id=other_sub, marks_obtained=50.0
                )
            ],
        )


def test_save_rejects_student_not_in_class(conn: sqlite3.Connection) -> None:
    cid, eid, _sids, [math_id, _] = _seed(conn)
    yid = conn.execute("SELECT id FROM academic_years LIMIT 1").fetchone()[0]
    other_cid = class_repo.create_class(
        conn, Class(id=None, name="6", section="A", academic_year_id=yid)
    )
    cur = conn.execute(
        "INSERT INTO students (admission_no, first_name, admission_date, class_id, status) "
        "VALUES ('OUT/1', 'X', '2025-04-01', ?, 'active')",
        (other_cid,),
    )
    out_sid = int(cur.lastrowid)
    with pytest.raises(ValidationError):
        mark_service.save_class_exam_marks(
            conn,
            class_id=cid,
            exam_id=eid,
            inputs=[
                mark_service.MarkInput(student_id=out_sid, subject_id=math_id, marks_obtained=50.0)
            ],
        )


def test_load_grid_seeds_existing(conn: sqlite3.Connection) -> None:
    cid, eid, sids, [math_id, _] = _seed(conn)
    mark_service.save_class_exam_marks(
        conn,
        class_id=cid,
        exam_id=eid,
        inputs=[
            mark_service.MarkInput(student_id=sids[0], subject_id=math_id, marks_obtained=70.0)
        ],
    )
    grid = mark_service.load_grid(conn, cid, eid)
    assert grid[(sids[0], math_id)]["marks_obtained"] == 70.0
    assert grid[(sids[0], math_id)]["grade"] == "B+"
