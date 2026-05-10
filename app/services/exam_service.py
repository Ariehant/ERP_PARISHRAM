"""Exam validation + create/update/delete."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import replace

from app.db.connection import transaction
from app.models.exam import Exam
from app.repositories import exam_repo
from app.utils.errors import ValidationError
from app.utils.formatters import parse_iso_date

log = logging.getLogger(__name__)

VALID_EXAM_TYPES = ("unit", "midterm", "final", "practice")


def _validate(exam: Exam) -> Exam:
    name = (exam.name or "").strip()
    if not name:
        raise ValidationError("Exam name is required.", field="name")
    if exam.academic_year_id is None:
        raise ValidationError("Academic year is required.", field="academic_year_id")
    exam_type = (exam.exam_type or "").strip().lower() or None
    if exam_type is not None and exam_type not in VALID_EXAM_TYPES:
        raise ValidationError(
            f"Type must be one of {', '.join(VALID_EXAM_TYPES)}.", field="exam_type"
        )
    start = exam.start_date.strip() if exam.start_date else None
    end = exam.end_date.strip() if exam.end_date else None
    if start:
        try:
            start = parse_iso_date(start)
        except ValueError as exc:
            raise ValidationError("Start date must be YYYY-MM-DD.", field="start_date") from exc
    else:
        start = None
    if end:
        try:
            end = parse_iso_date(end)
        except ValueError as exc:
            raise ValidationError("End date must be YYYY-MM-DD.", field="end_date") from exc
    else:
        end = None
    if start and end and start > end:
        raise ValidationError("Start date must be on or before end date.", field="end_date")
    weightage = exam.weightage if exam.weightage is not None else 100
    if weightage <= 0 or weightage > 1000:
        raise ValidationError("Weightage must be between 1 and 1000.", field="weightage")
    return replace(
        exam,
        name=name,
        exam_type=exam_type,
        start_date=start,
        end_date=end,
        weightage=weightage,
    )


def create_exam(conn: sqlite3.Connection, exam: Exam) -> int:
    clean = _validate(exam)
    with transaction(conn):
        new_id = exam_repo.create(conn, clean)
    log.info("Created exam id=%s name=%r", new_id, clean.name)
    return new_id


def update_exam(conn: sqlite3.Connection, exam: Exam) -> None:
    if exam.id is None:
        raise ValueError("update_exam requires exam.id")
    clean = _validate(exam)
    with transaction(conn):
        exam_repo.update(conn, clean)
    log.info("Updated exam id=%s", exam.id)


def delete_exam(conn: sqlite3.Connection, exam_id: int) -> None:
    """Hard delete. Marks rows cascade. Refuses if marks already exist."""
    n = exam_repo.count_marks_for_exam(conn, exam_id)
    if n > 0:
        raise ValidationError(
            f"Cannot delete: {n} mark(s) have been recorded for this exam. "
            "Clear them first or keep the exam.",
        )
    with transaction(conn):
        exam_repo.delete(conn, exam_id)
    log.info("Deleted exam id=%s", exam_id)
