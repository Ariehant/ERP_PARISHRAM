"""First-run setup orchestration.

Validates inputs, then in one transaction creates the school row, the first
academic year (marked active), and the first admin user.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from app.db.connection import transaction
from app.models.school import AcademicYear, School
from app.models.user import User
from app.repositories import school_repo, user_repo
from app.utils.errors import ValidationError
from app.utils.formatters import parse_iso_date
from app.utils.security import hash_password

log = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SetupRequest:
    school_name: str
    address: str | None
    phone: str | None
    email: str | None
    affiliation_no: str | None
    academic_year_label: str
    academic_year_start: str  # ISO
    academic_year_end: str  # ISO
    admin_username: str
    admin_full_name: str | None
    admin_password: str


def _require(value: str | None, field: str, label: str) -> str:
    if not value or not value.strip():
        raise ValidationError(f"{label} is required.", field=field)
    return value.strip()


def is_setup_complete(conn: sqlite3.Connection) -> bool:
    """True iff a school *and* at least one user already exist."""
    return school_repo.school_exists(conn) and user_repo.any_user_exists(conn)


def perform_initial_setup(conn: sqlite3.Connection, req: SetupRequest) -> int:
    """Create school + academic year + first admin user. Returns user id."""
    if is_setup_complete(conn):
        raise ValidationError("Setup has already been completed.")

    school_name = _require(req.school_name, "school_name", "School name")
    label = _require(req.academic_year_label, "academic_year_label", "Academic year")

    try:
        start = parse_iso_date(req.academic_year_start)
        end = parse_iso_date(req.academic_year_end)
    except ValueError as exc:
        raise ValidationError(
            f"Academic year dates must be YYYY-MM-DD ({exc}).",
            field="academic_year_start",
        ) from exc

    if start >= end:
        raise ValidationError(
            "Academic year start date must be before end date.",
            field="academic_year_end",
        )

    username = _require(req.admin_username, "admin_username", "Admin username").lower()
    if " " in username:
        raise ValidationError("Admin username cannot contain spaces.", field="admin_username")
    password = req.admin_password or ""
    if len(password) < 6:
        raise ValidationError(
            "Admin password must be at least 6 characters.", field="admin_password"
        )

    password_hash = hash_password(password)

    school = School(
        id=None,
        name=school_name,
        address=req.address,
        phone=req.phone,
        email=req.email,
        affiliation_no=req.affiliation_no,
    )
    year = AcademicYear(
        id=None,
        label=label,
        start_date=start,
        end_date=end,
        is_active=True,
    )
    admin = User(
        id=None,
        username=username,
        password_hash=password_hash,
        role="admin",
        full_name=req.admin_full_name,
        is_active=True,
    )

    with transaction(conn):
        school_repo.create_school(conn, school)
        school_repo.create_academic_year(conn, year)
        user_id = user_repo.create_user(conn, admin)

    log.info(
        "Initial setup complete: school=%r, year=%r, admin=%r",
        school_name,
        label,
        username,
    )
    return user_id
