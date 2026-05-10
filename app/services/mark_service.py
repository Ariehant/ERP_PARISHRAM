"""Marks save/load with auto-grade.

UI hands the service a flat list of ``MarkInput`` rows for a class+exam.
The service validates each row, computes the grade by looking up the
``grade_scales`` table via :func:`grade_scale_service.grade_for_percent`,
and upserts everything in a single transaction.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from app.db.connection import transaction
from app.models.exam import Mark
from app.repositories import (
    class_repo,
    exam_repo,
    mark_repo,
    student_repo,
)
from app.services import grade_scale_service
from app.utils.errors import ValidationError

log = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class MarkInput:
    """A single grid cell that the user entered."""

    student_id: int
    subject_id: int
    marks_obtained: float | None  # None means "no entry yet" -> skipped


def grade_for(percent: float, conn: sqlite3.Connection) -> str | None:
    return grade_scale_service.grade_for_percent(conn, percent)


def save_class_exam_marks(
    conn: sqlite3.Connection,
    *,
    class_id: int,
    exam_id: int,
    inputs: list[MarkInput],
) -> int:
    """Validate + upsert. Returns the count of rows written.

    ``inputs`` for cells the user left blank are skipped (not deleted). Use
    ``clear_one`` to remove a previously-recorded mark.
    """
    if class_id is None or exam_id is None:
        raise ValidationError("Pick a class and an exam first.")

    exam = exam_repo.get(conn, exam_id)
    if exam is None:
        raise ValidationError("Exam not found.")
    if exam.academic_year_id is None:
        raise ValidationError("Exam has no academic year.")

    # Build subject -> max_marks map for the class (single fetch).
    subjects = class_repo.list_subjects_for_class(conn, class_id)
    subject_max: dict[int, int] = {s.id: s.max_marks for s in subjects if s.id is not None}

    # Build the set of valid student ids in this class.
    student_ids = {
        s.id
        for s in student_repo.list_all_for_export(conn, class_id=class_id, status="active")
        if s.id is not None
    }

    rows_to_write: list[Mark] = []
    for inp in inputs:
        if inp.marks_obtained is None:
            continue
        if inp.student_id not in student_ids:
            raise ValidationError(
                f"Student #{inp.student_id} is not in this class.",
            )
        if inp.subject_id not in subject_max:
            raise ValidationError(
                f"Subject #{inp.subject_id} is not part of this class.",
            )
        max_marks = subject_max[inp.subject_id]
        if inp.marks_obtained < 0 or inp.marks_obtained > max_marks:
            raise ValidationError(
                f"Marks for student #{inp.student_id} / subject #{inp.subject_id} "
                f"must be between 0 and {max_marks} (got {inp.marks_obtained}).",
                field="marks_obtained",
            )
        percent = (inp.marks_obtained / max_marks) * 100.0 if max_marks else 0.0
        grade = grade_scale_service.grade_for_percent(conn, percent)
        rows_to_write.append(
            Mark(
                id=None,
                exam_id=exam_id,
                student_id=inp.student_id,
                subject_id=inp.subject_id,
                marks_obtained=float(inp.marks_obtained),
                max_marks=max_marks,
                grade=grade,
            )
        )

    with transaction(conn):
        for m in rows_to_write:
            mark_repo.upsert(conn, m)
    log.info("Saved %d marks for class=%s exam=%s", len(rows_to_write), class_id, exam_id)
    return len(rows_to_write)


def clear_one(conn: sqlite3.Connection, *, exam_id: int, student_id: int, subject_id: int) -> None:
    with transaction(conn):
        mark_repo.delete_one(conn, exam_id, student_id, subject_id)


def load_grid(conn: sqlite3.Connection, class_id: int, exam_id: int) -> dict[tuple[int, int], dict]:
    """Build ``{(student_id, subject_id): {marks_obtained, grade}}``.

    Used by the marks-entry view to seed initial values.
    """
    rows = mark_repo.list_for_class_and_exam(conn, class_id, exam_id)
    return {(r["student_id"], r["subject_id"]): r for r in rows}
