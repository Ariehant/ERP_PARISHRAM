from __future__ import annotations

import sqlite3

import pytest

from app.models.grade_scale import GradeBand
from app.services import grade_scale_service
from app.utils.errors import ValidationError


def test_grade_for_percent_default(conn: sqlite3.Connection) -> None:
    assert grade_scale_service.grade_for_percent(conn, 95.0) == "A+"
    assert grade_scale_service.grade_for_percent(conn, 31.0) == "F"


def test_save_all_validates_overlap(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError):
        grade_scale_service.save_all(
            conn,
            [
                GradeBand(None, "A", 50.0, 100.0),
                GradeBand(None, "B", 40.0, 60.0),  # overlaps with A
            ],
        )


def test_save_all_validates_min_gt_max(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError):
        grade_scale_service.save_all(
            conn,
            [GradeBand(None, "X", 50.0, 30.0)],
        )


def test_save_all_validates_blank_grade(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError):
        grade_scale_service.save_all(conn, [GradeBand(None, "  ", 0.0, 100.0)])


def test_save_all_replaces(conn: sqlite3.Connection) -> None:
    grade_scale_service.save_all(
        conn,
        [
            GradeBand(None, "PASS", 40.0, 100.0),
            GradeBand(None, "FAIL", 0.0, 39.99),
        ],
    )
    bands = grade_scale_service.list_bands(conn)
    assert {b.grade for b in bands} == {"PASS", "FAIL"}
