"""Grade scale validation + replace-all save."""

from __future__ import annotations

import logging
import sqlite3

from app.db.connection import transaction
from app.models.grade_scale import GradeBand
from app.repositories import grade_scale_repo
from app.utils.errors import ValidationError

log = logging.getLogger(__name__)


def list_bands(conn: sqlite3.Connection) -> list[GradeBand]:
    return grade_scale_repo.list_all(conn)


def grade_for_percent(conn: sqlite3.Connection, percent: float) -> str | None:
    """Return the grade letter for ``percent``, or ``None`` if none matches."""
    if percent is None:
        return None
    return grade_scale_repo.grade_for_percent(conn, percent)


def _validate(bands: list[GradeBand]) -> list[GradeBand]:
    if not bands:
        raise ValidationError("At least one grade band is required.")
    seen_grades: set[str] = set()
    cleaned: list[GradeBand] = []
    for b in bands:
        grade = (b.grade or "").strip()
        if not grade:
            raise ValidationError("Grade name cannot be blank.", field="grade")
        if grade.lower() in seen_grades:
            raise ValidationError(f"Grade {grade!r} is duplicated.", field="grade")
        seen_grades.add(grade.lower())
        if not 0 <= b.min_percent <= 100:
            raise ValidationError(f"Min % for {grade!r} must be 0-100.", field="min_percent")
        if not 0 <= b.max_percent <= 100:
            raise ValidationError(f"Max % for {grade!r} must be 0-100.", field="max_percent")
        if b.min_percent > b.max_percent:
            raise ValidationError(
                f"For {grade!r}: min % ({b.min_percent}) is greater than max % ({b.max_percent}).",
                field="min_percent",
            )
        cleaned.append(
            GradeBand(
                id=b.id,
                grade=grade,
                min_percent=float(b.min_percent),
                max_percent=float(b.max_percent),
                remarks=(b.remarks.strip() if b.remarks else None) or None,
            )
        )
    # Check that bands don't overlap (sorting by min_percent).
    from itertools import pairwise

    cleaned_sorted = sorted(cleaned, key=lambda x: x.min_percent)
    for prev, curr in pairwise(cleaned_sorted):
        if curr.min_percent <= prev.max_percent:
            raise ValidationError(
                f"Bands overlap: {prev.grade!r} ({prev.min_percent}-"
                f"{prev.max_percent}) and {curr.grade!r} ({curr.min_percent}-"
                f"{curr.max_percent}).",
            )
    return cleaned


def save_all(conn: sqlite3.Connection, bands: list[GradeBand]) -> None:
    """Validate + replace all grade bands in a single transaction."""
    cleaned = _validate(bands)
    with transaction(conn):
        grade_scale_repo.replace_all(conn, cleaned)
    log.info("Saved %d grade bands", len(cleaned))
