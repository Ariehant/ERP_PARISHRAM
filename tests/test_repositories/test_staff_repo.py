from __future__ import annotations

import sqlite3

import pytest

from app.models.people import Staff
from app.repositories import staff_repo


def _staff(emp_code: str = "EMP/1", **overrides) -> Staff:
    base = dict(
        id=None,
        emp_code=emp_code,
        name="Asha Mehta",
        role="teacher",
        phone="9876543210",
        email="asha@x.test",
        joining_date="2024-04-01",
        qualification="M.Ed.",
        is_active=True,
    )
    base.update(overrides)
    return Staff(**base)


def test_create_and_get(conn: sqlite3.Connection) -> None:
    sid = staff_repo.create(conn, _staff())
    s = staff_repo.get(conn, sid)
    assert s is not None and s.emp_code == "EMP/1"
    assert staff_repo.emp_code_exists(conn, "EMP/1") is True


def test_emp_code_unique(conn: sqlite3.Connection) -> None:
    staff_repo.create(conn, _staff("DUP/1"))
    with pytest.raises(sqlite3.IntegrityError):
        staff_repo.create(conn, _staff("DUP/1"))


def test_emp_code_exists_excludes_self(conn: sqlite3.Connection) -> None:
    sid = staff_repo.create(conn, _staff("X/1"))
    assert staff_repo.emp_code_exists(conn, "X/1", exclude_id=sid) is False


def test_filter_by_role_and_active(conn: sqlite3.Connection) -> None:
    staff_repo.create(conn, _staff("T/1", role="teacher"))
    staff_repo.create(conn, _staff("T/2", role="teacher", is_active=False))
    staff_repo.create(conn, _staff("A/1", role="admin"))

    assert staff_repo.count(conn, role="teacher") == 2
    assert staff_repo.count(conn, role="teacher", is_active=True) == 1
    assert staff_repo.count(conn, is_active=False) == 1


def test_search(conn: sqlite3.Connection) -> None:
    staff_repo.create(conn, _staff("S/1", name="Riya Khanna"))
    staff_repo.create(conn, _staff("S/2", name="Mohit Gupta"))
    assert staff_repo.count(conn, search="Riya") == 1
    assert staff_repo.count(conn, search="S/2") == 1


def test_list_active_teachers(conn: sqlite3.Connection) -> None:
    staff_repo.create(conn, _staff("T/1", role="teacher"))
    staff_repo.create(conn, _staff("T/2", role="teacher", is_active=False))
    staff_repo.create(conn, _staff("A/1", role="admin"))
    teachers = staff_repo.list_active_teachers(conn)
    assert {t.emp_code for t in teachers} == {"T/1"}


def test_paged(conn: sqlite3.Connection) -> None:
    for i in range(7):
        staff_repo.create(conn, _staff(f"P/{i}", name=f"Z{i}"))
    page1 = staff_repo.list_page(conn, limit=5, offset=0)
    page2 = staff_repo.list_page(conn, limit=5, offset=5)
    assert len(page1) == 5
    assert len(page2) == 2
