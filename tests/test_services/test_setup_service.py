from __future__ import annotations

import sqlite3

import pytest

from app.repositories import school_repo, user_repo
from app.services.setup_service import (
    SetupRequest,
    is_setup_complete,
    perform_initial_setup,
)
from app.utils.errors import ValidationError


def _good_request(**overrides: object) -> SetupRequest:
    base = dict(
        school_name="Parishram Public School",
        address="Lucknow",
        phone="9999999999",
        email="contact@parishram.test",
        affiliation_no="ABC123",
        academic_year_label="2025-26",
        academic_year_start="2025-04-01",
        academic_year_end="2026-03-31",
        admin_username="admin",
        admin_full_name="Principal",
        admin_password="hunter2x",
    )
    base.update(overrides)
    return SetupRequest(**base)  # type: ignore[arg-type]


def test_full_flow(conn: sqlite3.Connection) -> None:
    assert is_setup_complete(conn) is False
    uid = perform_initial_setup(conn, _good_request())
    assert uid > 0
    assert is_setup_complete(conn) is True

    # Side-effects landed.
    school = school_repo.get_first_school(conn)
    assert school is not None and school.name == "Parishram Public School"
    year = school_repo.get_active_academic_year(conn)
    assert year is not None and year.label == "2025-26"
    user = user_repo.get_by_username(conn, "admin")
    assert user is not None and user.role == "admin"


def test_cannot_run_twice(conn: sqlite3.Connection) -> None:
    perform_initial_setup(conn, _good_request())
    with pytest.raises(ValidationError):
        perform_initial_setup(conn, _good_request())


def test_validates_required_school_name(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        perform_initial_setup(conn, _good_request(school_name="   "))
    assert exc.value.field == "school_name"


def test_validates_password_length(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        perform_initial_setup(conn, _good_request(admin_password="abc"))
    assert exc.value.field == "admin_password"


def test_validates_year_dates(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError):
        perform_initial_setup(
            conn,
            _good_request(
                academic_year_start="2026-04-01",
                academic_year_end="2025-03-31",
            ),
        )


def test_rolls_back_on_failure(conn: sqlite3.Connection) -> None:
    """If the user insert fails, school + academic_year must NOT exist."""
    # Create a conflicting user first so the second insert collides.
    perform_initial_setup(conn, _good_request())

    # Wipe everything except users so we re-run setup but it will fail at user creation.
    conn.execute("DELETE FROM schools")
    conn.execute("DELETE FROM academic_years")
    # Now setup should attempt: school OK, year OK, user FAILS (UNIQUE).
    # is_setup_complete returns False (no school), so we get past the guard.
    with pytest.raises(sqlite3.IntegrityError):
        perform_initial_setup(conn, _good_request())

    # And the transaction was rolled back: no school, no year were created.
    assert school_repo.get_first_school(conn) is None
    assert school_repo.get_active_academic_year(conn) is None
