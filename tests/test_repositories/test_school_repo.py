from __future__ import annotations

import sqlite3

import pytest

from app.models.school import AcademicYear, School
from app.repositories import school_repo


def test_create_and_fetch_school(conn: sqlite3.Connection) -> None:
    assert school_repo.school_exists(conn) is False
    sid = school_repo.create_school(
        conn,
        School(id=None, name="Parishram Public School", address="Lucknow"),
    )
    assert sid > 0
    assert school_repo.school_exists(conn) is True

    fetched = school_repo.get_first_school(conn)
    assert fetched is not None
    assert fetched.name == "Parishram Public School"
    assert fetched.address == "Lucknow"
    assert fetched.created_at is not None


def test_create_academic_year_unique(conn: sqlite3.Connection) -> None:
    school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None, label="2025-26", start_date="2025-04-01", end_date="2026-03-31", is_active=True
        ),
    )
    # Same label → UNIQUE violation.
    with pytest.raises(sqlite3.IntegrityError):
        school_repo.create_academic_year(
            conn,
            AcademicYear(id=None, label="2025-26", start_date="2025-04-01", end_date="2026-03-31"),
        )


def test_set_active_academic_year(conn: sqlite3.Connection) -> None:
    a = school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None, label="2024-25", start_date="2024-04-01", end_date="2025-03-31", is_active=True
        ),
    )
    b = school_repo.create_academic_year(
        conn,
        AcademicYear(id=None, label="2025-26", start_date="2025-04-01", end_date="2026-03-31"),
    )
    school_repo.set_active_academic_year(conn, b)
    active = school_repo.get_active_academic_year(conn)
    assert active is not None
    assert active.id == b
    assert active.label == "2025-26"
    # And the previously active year is no longer active.
    rows = school_repo.list_academic_years(conn)
    by_id = {r.id: r for r in rows}
    assert by_id[a].is_active is False
