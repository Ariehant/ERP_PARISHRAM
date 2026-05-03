from __future__ import annotations

import sqlite3

import pytest

from app.models.people import Student
from app.repositories import student_repo


def _student(admission_no: str = "ADM/2025/001", **overrides) -> Student:
    base = dict(
        id=None,
        admission_no=admission_no,
        first_name="Aarav",
        last_name="Sharma",
        admission_date="2025-04-01",
        roll_no=1,
        dob="2014-08-15",
        gender="M",
        status="active",
        father_name="Rajeev",
        father_phone="9876543210",
    )
    base.update(overrides)
    return Student(**base)


def test_create_and_get(conn: sqlite3.Connection) -> None:
    sid = student_repo.create(conn, _student())
    assert sid > 0
    fetched = student_repo.get(conn, sid)
    assert fetched is not None
    assert fetched.admission_no == "ADM/2025/001"
    assert fetched.created_at is not None
    assert student_repo.admission_no_exists(conn, "ADM/2025/001") is True


def test_admission_no_unique(conn: sqlite3.Connection) -> None:
    student_repo.create(conn, _student("DUP/1"))
    with pytest.raises(sqlite3.IntegrityError):
        student_repo.create(conn, _student("DUP/1"))


def test_admission_no_exists_excludes_self(conn: sqlite3.Connection) -> None:
    sid = student_repo.create(conn, _student("EXCL/1"))
    assert student_repo.admission_no_exists(conn, "EXCL/1") is True
    assert student_repo.admission_no_exists(conn, "EXCL/1", exclude_id=sid) is False


def test_update_changes_fields(conn: sqlite3.Connection) -> None:
    sid = student_repo.create(conn, _student("UPD/1", first_name="Arav"))
    fetched = student_repo.get(conn, sid)
    assert fetched is not None
    from dataclasses import replace

    student_repo.update(conn, replace(fetched, first_name="Aarav", last_name="Sharma"))
    again = student_repo.get(conn, sid)
    assert again is not None
    assert again.first_name == "Aarav"
    assert again.last_name == "Sharma"


def test_set_status_and_delete_cascade(conn: sqlite3.Connection) -> None:
    sid = student_repo.create(conn, _student("DEL/1"))
    student_repo.set_status(conn, sid, "transferred")
    assert (student_repo.get(conn, sid)).status == "transferred"  # type: ignore[union-attr]

    # Adding an attendance row to verify the cascade fires.
    conn.execute(
        "INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)",
        (sid, "2025-04-01", "P"),
    )
    student_repo.delete(conn, sid)
    assert student_repo.get(conn, sid) is None
    cur = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ?", (sid,))
    assert cur.fetchone()[0] == 0


def test_count_and_list_page(conn: sqlite3.Connection) -> None:
    for i in range(0, 12):
        student_repo.create(
            conn,
            _student(
                admission_no=f"PAGE/{i:03d}",
                first_name=f"Student{i:02d}",
            ),
        )
    assert student_repo.count(conn) == 12
    page1 = student_repo.list_page(conn, limit=5, offset=0)
    page2 = student_repo.list_page(conn, limit=5, offset=5)
    page3 = student_repo.list_page(conn, limit=5, offset=10)
    assert len(page1) == 5
    assert len(page2) == 5
    assert len(page3) == 2
    # Pages should not overlap.
    ids_first_two = {s.id for s in page1} | {s.id for s in page2}
    assert ids_first_two & {s.id for s in page3} == set()


def test_search_filters_by_name_and_admission(conn: sqlite3.Connection) -> None:
    student_repo.create(conn, _student("SRC/1", first_name="Riya", last_name="Singh"))
    student_repo.create(conn, _student("SRC/2", first_name="Aman", last_name="Khan"))
    assert student_repo.count(conn, search="Riya") == 1
    assert student_repo.count(conn, search="SRC/2") == 1
    assert student_repo.count(conn, search="khan") == 1  # case-insensitive LIKE
    assert student_repo.count(conn, search="nope") == 0


def test_status_filter(conn: sqlite3.Connection) -> None:
    s1 = student_repo.create(conn, _student("ST/1"))
    student_repo.create(conn, _student("ST/2", status="inactive"))
    student_repo.set_status(conn, s1, "active")
    assert student_repo.count(conn, status="active") == 1
    assert student_repo.count(conn, status="inactive") == 1
