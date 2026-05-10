from __future__ import annotations

import sqlite3

from app.models.exam import Exam, Mark
from app.models.school import AcademicYear
from app.models.structure import Class, Subject
from app.repositories import class_repo, exam_repo, mark_repo, school_repo


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
        conn, Subject(id=None, name="English", class_id=cid, max_marks=100)
    )
    eid = exam_repo.create(
        conn,
        Exam(id=None, name="Test", academic_year_id=yid),
    )
    sids = []
    for i in range(2):
        cur = conn.execute(
            "INSERT INTO students (admission_no, first_name, admission_date, class_id, status) "
            "VALUES (?, ?, ?, ?, 'active')",
            (f"ADM/{i + 1}", f"S{i + 1}", "2025-04-01", cid),
        )
        sids.append(int(cur.lastrowid))
    return cid, eid, sids, [s1, s2]


def test_upsert_inserts_then_updates(conn: sqlite3.Connection) -> None:
    cid, eid, sids, [sub_id, _] = _seed(conn)
    mark_repo.upsert(
        conn,
        Mark(
            id=None,
            exam_id=eid,
            student_id=sids[0],
            subject_id=sub_id,
            marks_obtained=80.0,
            max_marks=100,
            grade="A",
        ),
    )
    rows = mark_repo.list_for_class_and_exam(conn, cid, eid)
    assert len(rows) == 1
    assert rows[0]["marks_obtained"] == 80.0

    # Re-upsert -- should update, not duplicate.
    mark_repo.upsert(
        conn,
        Mark(
            id=None,
            exam_id=eid,
            student_id=sids[0],
            subject_id=sub_id,
            marks_obtained=90.0,
            max_marks=100,
            grade="A+",
        ),
    )
    rows = mark_repo.list_for_class_and_exam(conn, cid, eid)
    assert len(rows) == 1
    assert rows[0]["marks_obtained"] == 90.0
    assert rows[0]["grade"] == "A+"


def test_delete_one(conn: sqlite3.Connection) -> None:
    cid, eid, sids, [sub_id, _] = _seed(conn)
    mark_repo.upsert(
        conn,
        Mark(
            id=None,
            exam_id=eid,
            student_id=sids[0],
            subject_id=sub_id,
            marks_obtained=50.0,
            max_marks=100,
        ),
    )
    mark_repo.delete_one(conn, eid, sids[0], sub_id)
    assert mark_repo.list_for_class_and_exam(conn, cid, eid) == []
