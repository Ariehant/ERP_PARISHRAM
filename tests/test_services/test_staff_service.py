from __future__ import annotations

import sqlite3

import pytest

from app.models.people import Staff
from app.models.school import AcademicYear
from app.models.structure import Class
from app.repositories import class_repo, school_repo, staff_repo
from app.services import staff_service
from app.utils.errors import ValidationError


def _staff(emp_code: str = "EMP/1", **overrides) -> Staff:
    base = dict(
        id=None,
        emp_code=emp_code,
        name="Asha Mehta",
        role="TEACHER",
        phone="98 765-43210",
        email="asha@x.test",
        joining_date="2024-04-01",
        qualification="M.Ed.",
        is_active=True,
    )
    base.update(overrides)
    return Staff(**base)


def test_create_normalises(conn: sqlite3.Connection) -> None:
    sid = staff_service.create_staff(conn, _staff())
    s = staff_repo.get(conn, sid)
    assert s is not None
    assert s.role == "teacher"  # case-folded
    assert s.phone == "98765-43210"  # spaces removed


def test_blank_name_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        staff_service.create_staff(conn, _staff(name="  "))
    assert exc.value.field == "name"


def test_invalid_role_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        staff_service.create_staff(conn, _staff(role="janitor"))
    assert exc.value.field == "role"


def test_invalid_email_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        staff_service.create_staff(conn, _staff(email="not-an-email"))
    assert exc.value.field == "email"


def test_duplicate_emp_code_rejected(conn: sqlite3.Connection) -> None:
    staff_service.create_staff(conn, _staff("DUP/1"))
    with pytest.raises(ValidationError):
        staff_service.create_staff(conn, _staff("DUP/1"))


def test_update_blocks_clash(conn: sqlite3.Connection) -> None:
    a = staff_service.create_staff(conn, _staff("A/1"))
    staff_service.create_staff(conn, _staff("B/1"))
    fetched = staff_repo.get(conn, a)
    assert fetched is not None
    from dataclasses import replace

    with pytest.raises(ValidationError):
        staff_service.update_staff(conn, replace(fetched, emp_code="B/1"))


def test_delete_blocks_when_class_teacher(conn: sqlite3.Connection) -> None:
    sid = staff_service.create_staff(conn, _staff())
    yid = school_repo.create_academic_year(
        conn,
        AcademicYear(id=None, label="2025-26", start_date="2025-04-01", end_date="2026-03-31"),
    )
    class_repo.create_class(
        conn,
        Class(id=None, name="5", section="A", academic_year_id=yid, class_teacher_id=sid),
    )
    with pytest.raises(ValidationError):
        staff_service.delete_staff(conn, sid)


def test_delete_succeeds_when_unreferenced(conn: sqlite3.Connection) -> None:
    sid = staff_service.create_staff(conn, _staff())
    staff_service.delete_staff(conn, sid)
    assert staff_repo.get(conn, sid) is None
