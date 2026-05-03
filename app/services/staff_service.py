"""Staff business logic — validation + create/update + delete-with-guard."""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import replace

from app.db.connection import transaction
from app.models.people import Staff
from app.repositories import staff_repo
from app.utils.errors import ValidationError
from app.utils.formatters import parse_iso_date

log = logging.getLogger(__name__)

VALID_ROLES = ("teacher", "admin", "accountant", "principal")
_PHONE_RE = re.compile(r"^\+?\d[\d\s\-]{6,14}$")
_EMP_CODE_RE = re.compile(r"^[A-Za-z0-9/\-_]+$")


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _validate_phone(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", "", value)
    if not _PHONE_RE.match(cleaned):
        raise ValidationError("Phone is not a valid number.", field="phone")
    return cleaned


def _validate_email(value: str | None) -> str | None:
    if value is None:
        return None
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValidationError("Email looks invalid.", field="email")
    return value


def _normalise(staff: Staff) -> Staff:
    emp_code = (staff.emp_code or "").strip()
    if not emp_code:
        raise ValidationError("Employee code is required.", field="emp_code")
    if not _EMP_CODE_RE.match(emp_code):
        raise ValidationError(
            "Employee code may only contain letters, digits, '/', '-', '_'.",
            field="emp_code",
        )
    name = (staff.name or "").strip()
    if not name:
        raise ValidationError("Name is required.", field="name")
    role = (staff.role or "").strip().lower()
    if role not in VALID_ROLES:
        raise ValidationError(f"Role must be one of {', '.join(VALID_ROLES)}.", field="role")

    joining = _strip_or_none(staff.joining_date)
    if joining is not None:
        try:
            joining = parse_iso_date(joining)
        except ValueError as exc:
            raise ValidationError(
                "Joining date must be in YYYY-MM-DD format.",
                field="joining_date",
            ) from exc

    return replace(
        staff,
        emp_code=emp_code,
        name=name,
        role=role,
        phone=_validate_phone(_strip_or_none(staff.phone)),
        email=_validate_email(_strip_or_none(staff.email)),
        joining_date=joining,
        qualification=_strip_or_none(staff.qualification),
    )


# ---------------------------------------------------------------------------
def create_staff(conn: sqlite3.Connection, staff: Staff) -> int:
    clean = _normalise(staff)
    if staff_repo.emp_code_exists(conn, clean.emp_code):
        raise ValidationError(
            f"Employee code {clean.emp_code!r} is already in use.", field="emp_code"
        )
    with transaction(conn):
        new_id = staff_repo.create(conn, clean)
    log.info("Created staff id=%s emp_code=%s role=%s", new_id, clean.emp_code, clean.role)
    return new_id


def update_staff(conn: sqlite3.Connection, staff: Staff) -> None:
    if staff.id is None:
        raise ValueError("update_staff requires staff.id")
    clean = _normalise(staff)
    if staff_repo.emp_code_exists(conn, clean.emp_code, exclude_id=staff.id):
        raise ValidationError(
            f"Employee code {clean.emp_code!r} is already in use.", field="emp_code"
        )
    with transaction(conn):
        staff_repo.update(conn, clean)
    log.info("Updated staff id=%s", staff.id)


def delete_staff(conn: sqlite3.Connection, staff_id: int) -> None:
    """Hard delete. Refuses if the staff member is set as class teacher."""
    cur = conn.execute("SELECT COUNT(*) FROM classes WHERE class_teacher_id = ?", (staff_id,))
    refs = int(cur.fetchone()[0])
    if refs > 0:
        raise ValidationError(
            f"Cannot delete: this staff member is the class teacher of "
            f"{refs} class(es). Reassign first."
        )
    with transaction(conn):
        staff_repo.delete(conn, staff_id)
    log.info("Deleted staff id=%s", staff_id)
