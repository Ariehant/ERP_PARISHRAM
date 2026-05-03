"""Class + Subject business logic.

The class form treats subjects as "inline rows", so the public entry point
is :func:`save_class`, which validates everything, then in one transaction:

- inserts or updates the class row,
- diff-applies the subjects (insert new, update existing, delete missing).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import replace

from app.db.connection import transaction
from app.models.structure import Class, Subject
from app.repositories import class_repo
from app.utils.errors import ValidationError

log = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:[ \-/][A-Za-z0-9]+)*$")
_SECTION_RE = re.compile(r"^[A-Za-z0-9]+$")


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _normalise_class(cls: Class) -> Class:
    name = (cls.name or "").strip()
    section = (cls.section or "").strip()
    if not name:
        raise ValidationError("Class name is required.", field="name")
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Class name may only contain letters, digits, spaces, '-' or '/'.",
            field="name",
        )
    if not section:
        raise ValidationError("Section is required.", field="section")
    if not _SECTION_RE.match(section):
        raise ValidationError("Section may only contain letters or digits.", field="section")
    if cls.academic_year_id is None:
        raise ValidationError("Academic year is required.", field="academic_year_id")
    return replace(cls, name=name, section=section)


def _normalise_subject(subject: Subject) -> Subject:
    name = (subject.name or "").strip()
    if not name:
        raise ValidationError("Subject name is required.", field="name")
    code = _strip_or_none(subject.code)
    if subject.max_marks is None or subject.max_marks <= 0:
        raise ValidationError(f"Subject {name!r} must have positive max marks.", field="max_marks")
    return replace(subject, name=name, code=code)


def save_class(
    conn: sqlite3.Connection,
    cls: Class,
    subjects: list[Subject],
) -> int:
    """Create or update a class together with its subjects.

    ``subjects`` may carry ``id=None`` for new rows. Returns the class id.
    """
    clean_class = _normalise_class(cls)

    # Cross-row uniqueness within (name, section, year).
    if class_repo.class_exists_for_year(
        conn,
        name=clean_class.name,
        section=clean_class.section,
        academic_year_id=clean_class.academic_year_id,
        exclude_id=clean_class.id,
    ):
        raise ValidationError(
            f"Class {clean_class.name}-{clean_class.section} already exists "
            "for this academic year.",
            field="name",
        )

    # Validate every subject up front so we don't half-write.
    seen_names: set[str] = set()
    clean_subjects: list[Subject] = []
    for s in subjects:
        clean = _normalise_subject(s)
        key = clean.name.lower()
        if key in seen_names:
            raise ValidationError(
                f"Subject {clean.name!r} appears more than once.",
                field="name",
            )
        seen_names.add(key)
        clean_subjects.append(clean)

    with transaction(conn):
        if clean_class.id is None:
            class_id = class_repo.create_class(conn, clean_class)
        else:
            class_id = clean_class.id
            class_repo.update_class(conn, clean_class)
        class_repo.replace_subjects_for_class(conn, class_id, clean_subjects)

    log.info(
        "Saved class id=%s %s-%s with %d subject(s)",
        class_id,
        clean_class.name,
        clean_class.section,
        len(clean_subjects),
    )
    return class_id


def delete_class(conn: sqlite3.Connection, class_id: int) -> None:
    """Hard delete. Subjects cascade away. Refuses if students are still attached."""
    student_count = class_repo.count_students_in_class(conn, class_id)
    if student_count > 0:
        raise ValidationError(
            f"Cannot delete: {student_count} student(s) are still assigned to "
            "this class. Move them first."
        )
    with transaction(conn):
        class_repo.delete_class(conn, class_id)
    log.info("Deleted class id=%s", class_id)
