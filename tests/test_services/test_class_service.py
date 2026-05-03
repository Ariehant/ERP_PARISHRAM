from __future__ import annotations

import sqlite3

import pytest

from app.models.school import AcademicYear
from app.models.structure import Class, Subject
from app.repositories import class_repo, school_repo
from app.services import class_service
from app.utils.errors import ValidationError


def _year(conn: sqlite3.Connection, label: str = "2025-26", active: bool = True) -> int:
    return school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label=label,
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_active=active,
        ),
    )


def _class(yid: int, **overrides) -> Class:
    base = dict(id=None, name="5", section="A", academic_year_id=yid, class_teacher_id=None)
    base.update(overrides)
    return Class(**base)


def _subject(name: str = "Math", **overrides) -> Subject:
    base = dict(id=None, name=name, class_id=0, code=None, max_marks=100, is_optional=False)
    base.update(overrides)
    return Subject(**base)


def test_save_creates_class_and_subjects(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid = class_service.save_class(
        conn,
        _class(yid),
        [_subject("Math"), _subject("English", code="ENG", max_marks=80)],
    )
    assert cid > 0
    subjects = class_repo.list_subjects_for_class(conn, cid)
    assert {s.name for s in subjects} == {"Math", "English"}
    english = next(s for s in subjects if s.name == "English")
    assert english.max_marks == 80


def test_save_blocks_blank_name(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    with pytest.raises(ValidationError) as exc:
        class_service.save_class(conn, _class(yid, name=" "), [])
    assert exc.value.field == "name"


def test_save_blocks_duplicate_within_year(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    class_service.save_class(conn, _class(yid), [])
    with pytest.raises(ValidationError):
        class_service.save_class(conn, _class(yid), [])


def test_save_blocks_duplicate_subjects(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    with pytest.raises(ValidationError):
        class_service.save_class(conn, _class(yid), [_subject("Math"), _subject("math")])


def test_save_blocks_zero_max_marks(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    with pytest.raises(ValidationError):
        class_service.save_class(conn, _class(yid), [_subject(max_marks=0)])


def test_save_updates_class_and_diffs_subjects(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid = class_service.save_class(
        conn,
        _class(yid),
        [_subject("Math"), _subject("English")],
    )
    cls = class_repo.get_class(conn, cid)
    subjects = class_repo.list_subjects_for_class(conn, cid)
    math = next(s for s in subjects if s.name == "Math")

    # Rename English -> Hindi (drop), keep Math, add Science.
    class_service.save_class(
        conn,
        Class(
            id=cid,
            name="5",
            section="B",
            academic_year_id=cls.academic_year_id,
            class_teacher_id=None,  # type: ignore[union-attr]
        ),
        [
            Subject(
                id=math.id, name="Math", class_id=cid, code=None, max_marks=120, is_optional=False
            ),
            Subject(
                id=None, name="Science", class_id=cid, code=None, max_marks=100, is_optional=False
            ),
        ],
    )
    after = class_repo.get_class(conn, cid)
    assert after is not None
    assert after.section == "B"
    after_subs = class_repo.list_subjects_for_class(conn, cid)
    by_name = {s.name: s for s in after_subs}
    assert set(by_name.keys()) == {"Math", "Science"}
    assert by_name["Math"].max_marks == 120


def test_delete_blocks_when_students_attached(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid = class_service.save_class(conn, _class(yid), [_subject("Math")])
    conn.execute(
        "INSERT INTO students (admission_no, first_name, admission_date, class_id) "
        "VALUES (?, ?, ?, ?)",
        ("A/1", "X", "2025-04-01", cid),
    )
    with pytest.raises(ValidationError):
        class_service.delete_class(conn, cid)


def test_delete_succeeds_when_empty(conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    cid = class_service.save_class(conn, _class(yid), [_subject("Math")])
    class_service.delete_class(conn, cid)
    assert class_repo.get_class(conn, cid) is None
