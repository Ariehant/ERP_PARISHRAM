"""Student business logic — validation + create/update + import-row checks.

UI hands raw dicts/dataclasses to this layer; this layer normalises strings,
validates, and writes via the repository inside a transaction.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, replace
from typing import Any

from app.db.connection import transaction
from app.models.people import Student
from app.repositories import student_repo
from app.utils.errors import ValidationError
from app.utils.formatters import parse_iso_date

log = logging.getLogger(__name__)

VALID_GENDERS = ("M", "F", "O")
VALID_STATUSES = ("active", "transferred", "passed_out", "inactive")
_PHONE_RE = re.compile(r"^\+?\d[\d\s\-]{6,14}$")
_AADHAAR_RE = re.compile(r"^\d{12}$")
_PINCODE_RE = re.compile(r"^\d{6}$")
_ADMISSION_NO_RE = re.compile(r"^[A-Za-z0-9/\-_]+$")


def _strip_or_none(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _require_str(value: Any, *, field: str, label: str) -> str:
    s = _strip_or_none(value)
    if s is None:
        raise ValidationError(f"{label} is required.", field=field)
    return s


def _validate_phone(value: str | None, *, field: str, label: str) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", "", value)
    if not _PHONE_RE.match(cleaned):
        raise ValidationError(f"{label} is not a valid phone number.", field=field)
    return cleaned


def _validate_iso_date(value: str | None, *, field: str, label: str) -> str | None:
    if value is None:
        return None
    try:
        return parse_iso_date(value)
    except ValueError as exc:
        raise ValidationError(f"{label} must be in YYYY-MM-DD format.", field=field) from exc


def _normalise(student: Student) -> Student:
    """Apply trimming + uppercase tweaks; produce a clean dataclass."""
    admission_no = _require_str(student.admission_no, field="admission_no", label="Admission no.")
    if not _ADMISSION_NO_RE.match(admission_no):
        raise ValidationError(
            "Admission no. may only contain letters, digits, '/', '-', '_'.",
            field="admission_no",
        )

    first = _require_str(student.first_name, field="first_name", label="First name")
    admission_date = _require_str(
        student.admission_date, field="admission_date", label="Admission date"
    )
    admission_date = _validate_iso_date(
        admission_date, field="admission_date", label="Admission date"
    )

    dob = _validate_iso_date(_strip_or_none(student.dob), field="dob", label="Date of birth")

    gender = _strip_or_none(student.gender)
    if gender is not None:
        gender = gender.upper()
        if gender not in VALID_GENDERS:
            raise ValidationError(
                f"Gender must be one of {', '.join(VALID_GENDERS)}.", field="gender"
            )

    status = _strip_or_none(student.status) or "active"
    if status not in VALID_STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(VALID_STATUSES)}.", field="status")

    pincode = _strip_or_none(student.pincode)
    if pincode is not None and not _PINCODE_RE.match(pincode):
        raise ValidationError("Pincode must be 6 digits.", field="pincode")

    aadhaar = _strip_or_none(student.aadhaar)
    if aadhaar is not None:
        aadhaar = re.sub(r"\s+", "", aadhaar)
        if not _AADHAAR_RE.match(aadhaar):
            raise ValidationError("Aadhaar must be 12 digits.", field="aadhaar")

    return replace(
        student,
        admission_no=admission_no,
        first_name=first,
        last_name=_strip_or_none(student.last_name),
        dob=dob,
        gender=gender,
        blood_group=_strip_or_none(student.blood_group),
        admission_date=admission_date or "",
        status=status,
        father_name=_strip_or_none(student.father_name),
        father_phone=_validate_phone(
            _strip_or_none(student.father_phone),
            field="father_phone",
            label="Father's phone",
        ),
        father_occupation=_strip_or_none(student.father_occupation),
        mother_name=_strip_or_none(student.mother_name),
        mother_phone=_validate_phone(
            _strip_or_none(student.mother_phone),
            field="mother_phone",
            label="Mother's phone",
        ),
        mother_occupation=_strip_or_none(student.mother_occupation),
        guardian_name=_strip_or_none(student.guardian_name),
        guardian_phone=_validate_phone(
            _strip_or_none(student.guardian_phone),
            field="guardian_phone",
            label="Guardian's phone",
        ),
        address=_strip_or_none(student.address),
        city=_strip_or_none(student.city),
        state=_strip_or_none(student.state),
        pincode=pincode,
        aadhaar=aadhaar,
        prev_school=_strip_or_none(student.prev_school),
        category=_strip_or_none(student.category),
        religion=_strip_or_none(student.religion),
    )


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------
def create_student(conn: sqlite3.Connection, student: Student) -> int:
    clean = _normalise(student)
    if student_repo.admission_no_exists(conn, clean.admission_no):
        raise ValidationError(
            f"Admission no. {clean.admission_no!r} is already in use.",
            field="admission_no",
        )
    with transaction(conn):
        new_id = student_repo.create(conn, clean)
    log.info("Created student id=%s admission_no=%s", new_id, clean.admission_no)
    return new_id


def update_student(conn: sqlite3.Connection, student: Student) -> None:
    if student.id is None:
        raise ValueError("update_student requires student.id")
    clean = _normalise(student)
    if student_repo.admission_no_exists(conn, clean.admission_no, exclude_id=student.id):
        raise ValidationError(
            f"Admission no. {clean.admission_no!r} is already in use.",
            field="admission_no",
        )
    with transaction(conn):
        student_repo.update(conn, clean)
    log.info("Updated student id=%s", student.id)


# ---------------------------------------------------------------------------
# Import row support
# ---------------------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class ImportRow:
    """One row from the import preview. ``errors`` is empty for valid rows."""

    line: int  # 1-indexed within the data area (excluding header)
    student: Student | None
    errors: tuple[str, ...]
    raw: dict[str, Any]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_import_row(
    conn: sqlite3.Connection,
    line: int,
    raw: dict[str, Any],
    *,
    seen_admission_nos: set[str],
) -> ImportRow:
    """Build an ``ImportRow`` from a raw dict.

    Cross-row uniqueness is checked against ``seen_admission_nos`` (the caller
    seeds and updates that set as it walks the sheet). DB uniqueness is checked
    against ``students``.
    """
    errors: list[str] = []
    candidate = Student(
        id=None,
        admission_no=str(raw.get("admission_no") or "").strip(),
        first_name=str(raw.get("first_name") or "").strip(),
        last_name=_strip_or_none(raw.get("last_name")),
        roll_no=_coerce_int(raw.get("roll_no"), "roll_no", errors),
        dob=_strip_or_none(raw.get("dob")),
        gender=_strip_or_none(raw.get("gender")),
        blood_group=_strip_or_none(raw.get("blood_group")),
        admission_date=str(raw.get("admission_date") or "").strip(),
        status=_strip_or_none(raw.get("status")) or "active",
        father_name=_strip_or_none(raw.get("father_name")),
        father_phone=_strip_or_none(raw.get("father_phone")),
        mother_name=_strip_or_none(raw.get("mother_name")),
        mother_phone=_strip_or_none(raw.get("mother_phone")),
        address=_strip_or_none(raw.get("address")),
        city=_strip_or_none(raw.get("city")),
        state=_strip_or_none(raw.get("state")),
        pincode=_strip_or_none(raw.get("pincode")),
        aadhaar=_strip_or_none(raw.get("aadhaar")),
        prev_school=_strip_or_none(raw.get("prev_school")),
        category=_strip_or_none(raw.get("category")),
        religion=_strip_or_none(raw.get("religion")),
    )

    try:
        clean = _normalise(candidate)
    except ValidationError as exc:
        errors.append(exc.message)
        return ImportRow(line=line, student=None, errors=tuple(errors), raw=raw)

    if clean.admission_no in seen_admission_nos:
        errors.append(f"Duplicate admission no. {clean.admission_no!r} earlier in this file.")
    elif student_repo.admission_no_exists(conn, clean.admission_no):
        errors.append(f"Admission no. {clean.admission_no!r} already exists in the database.")
    else:
        seen_admission_nos.add(clean.admission_no)

    return ImportRow(
        line=line,
        student=clean if not errors else None,
        errors=tuple(errors),
        raw=raw,
    )


def _coerce_int(value: Any, field: str, errors: list[str]) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{field} must be an integer (got {value!r}).")
        return None


def commit_import(conn: sqlite3.Connection, rows: list[ImportRow]) -> int:
    """Insert all valid rows in a single transaction. Returns insert count."""
    inserted = 0
    with transaction(conn):
        for row in rows:
            if not row.is_valid or row.student is None:
                continue
            student_repo.create(conn, row.student)
            inserted += 1
    log.info("Imported %d students", inserted)
    return inserted
