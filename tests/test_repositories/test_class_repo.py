from __future__ import annotations

import sqlite3

import pytest

from app.models.school import AcademicYear
from app.models.structure import Class, Subject
from app.repositories import class_repo, school_repo


def _year(conn: sqlite3.Connection, label: str = "2025-26") -> int:
    return school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label=label,
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_active=True,
        ),
    )


def test_create_and_list_classes(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid_a = class_repo.create_class(
        conn, Class(id=None, name="5", section="A", academic_year_id=yid)
    )
    cid_b = class_repo.create_class(
        conn, Class(id=None, name="5", section="B", academic_year_id=yid)
    )
    rows = class_repo.list_for_year(conn, yid)
    assert {c.id for c in rows} == {cid_a, cid_b}
    assert class_repo.count_for_year(conn, yid) == 2


def test_unique_within_year(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    class_repo.create_class(conn, Class(id=None, name="6", section="A", academic_year_id=yid))
    with pytest.raises(sqlite3.IntegrityError):
        class_repo.create_class(conn, Class(id=None, name="6", section="A", academic_year_id=yid))


def test_class_exists_for_year_excludes_self(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid = class_repo.create_class(conn, Class(id=None, name="7", section="A", academic_year_id=yid))
    assert (
        class_repo.class_exists_for_year(conn, name="7", section="A", academic_year_id=yid) is True
    )
    assert (
        class_repo.class_exists_for_year(
            conn, name="7", section="A", academic_year_id=yid, exclude_id=cid
        )
        is False
    )


def test_replace_subjects_diff_apply(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid = class_repo.create_class(conn, Class(id=None, name="8", section="A", academic_year_id=yid))

    class_repo.replace_subjects_for_class(
        conn,
        cid,
        [
            Subject(id=None, name="Math", class_id=cid, max_marks=100),
            Subject(id=None, name="English", class_id=cid, max_marks=100),
        ],
    )
    subjects = class_repo.list_subjects_for_class(conn, cid)
    assert {s.name for s in subjects} == {"Math", "English"}
    math = next(s for s in subjects if s.name == "Math")
    english = next(s for s in subjects if s.name == "English")

    # Update Math, drop English, add Science.
    class_repo.replace_subjects_for_class(
        conn,
        cid,
        [
            Subject(id=math.id, name="Mathematics", class_id=cid, max_marks=120),
            Subject(id=None, name="Science", class_id=cid, max_marks=80),
        ],
    )
    subjects = class_repo.list_subjects_for_class(conn, cid)
    by_name = {s.name: s for s in subjects}
    assert set(by_name.keys()) == {"Mathematics", "Science"}
    assert by_name["Mathematics"].max_marks == 120
    # English was deleted.
    assert english.id not in {s.id for s in subjects}


def test_delete_class_cascades_subjects(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid = class_repo.create_class(conn, Class(id=None, name="9", section="A", academic_year_id=yid))
    class_repo.create_subject(conn, Subject(id=None, name="Hindi", class_id=cid, max_marks=100))
    assert class_repo.list_subjects_for_class(conn, cid)

    class_repo.delete_class(conn, cid)
    assert class_repo.get_class(conn, cid) is None
    assert class_repo.list_subjects_for_class(conn, cid) == []


def test_count_students_in_class(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid = class_repo.create_class(
        conn, Class(id=None, name="10", section="A", academic_year_id=yid)
    )
    assert class_repo.count_students_in_class(conn, cid) == 0
    conn.execute(
        "INSERT INTO students (admission_no, first_name, admission_date, class_id) "
        "VALUES (?, ?, ?, ?)",
        ("A/1", "X", "2025-04-01", cid),
    )
    assert class_repo.count_students_in_class(conn, cid) == 1
