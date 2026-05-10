from __future__ import annotations

import sqlite3

from app.models.grade_scale import GradeBand
from app.repositories import grade_scale_repo


def test_seed_loaded_from_migration(conn: sqlite3.Connection) -> None:
    bands = grade_scale_repo.list_all(conn)
    grades = {b.grade for b in bands}
    assert {"A+", "A", "B+", "B", "C+", "C", "D", "F"}.issubset(grades)


def test_grade_for_percent_default_seed(conn: sqlite3.Connection) -> None:
    assert grade_scale_repo.grade_for_percent(conn, 95.0) == "A+"
    assert grade_scale_repo.grade_for_percent(conn, 85.0) == "A"
    assert grade_scale_repo.grade_for_percent(conn, 33.0) == "D"
    assert grade_scale_repo.grade_for_percent(conn, 0.0) == "F"


def test_replace_all(conn: sqlite3.Connection) -> None:
    grade_scale_repo.replace_all(
        conn,
        [
            GradeBand(id=None, grade="PASS", min_percent=40.0, max_percent=100.0),
            GradeBand(id=None, grade="FAIL", min_percent=0.0, max_percent=39.99),
        ],
    )
    bands = grade_scale_repo.list_all(conn)
    assert {b.grade for b in bands} == {"PASS", "FAIL"}
    assert grade_scale_repo.grade_for_percent(conn, 50.0) == "PASS"
    assert grade_scale_repo.grade_for_percent(conn, 20.0) == "FAIL"
