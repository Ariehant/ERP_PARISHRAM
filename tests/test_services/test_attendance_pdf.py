"""Smoke tests for the attendance PDF generators.

We don't parse PDF content — only verify the file is non-empty and has the
right magic bytes, and that the generators don't throw on the no-data case.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

from app.models.school import AcademicYear, School
from app.models.structure import Class
from app.repositories import class_repo, school_repo
from app.services import attendance_service


def _seed(conn: sqlite3.Connection) -> int:
    school_repo.create_school(conn, School(id=None, name="Demo School", address="Lucknow"))
    yid = school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label="2025-26",
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_active=True,
        ),
    )
    cid = class_repo.create_class(conn, Class(id=None, name="5", section="A", academic_year_id=yid))
    for i in range(3):
        cur = conn.execute(
            "INSERT INTO students (admission_no, first_name, admission_date, class_id, status, roll_no) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (f"ADM/{i + 1:03d}", f"Stu{i + 1:02d}", "2025-04-01", cid, i + 1),
        )
        sid = int(cur.lastrowid)
        # Mark a few rows so the monthly + low reports have something to chew on.
        attendance_service.save_class_attendance(
            conn,
            class_id=cid,
            date_iso="2025-05-01",
            marks={sid: "P" if i < 2 else "A"},
        )
        attendance_service.save_class_attendance(
            conn, class_id=cid, date_iso="2025-05-02", marks={sid: "A"}
        )
    return cid


def _is_pdf(path: Path) -> bool:
    return path.is_file() and path.read_bytes()[:4] == b"%PDF"


def test_daily_register_pdf(tmp_path: Path, conn: sqlite3.Connection) -> None:
    cid = _seed(conn)
    from app.reports.attendance_pdf import write_daily_register

    out = write_daily_register(tmp_path / "daily.pdf", conn, cid, "2025-05-01")
    assert _is_pdf(out)


def test_monthly_summary_pdf(tmp_path: Path, conn: sqlite3.Connection) -> None:
    cid = _seed(conn)
    from app.reports.attendance_pdf import write_monthly_summary

    out = write_monthly_summary(tmp_path / "monthly.pdf", conn, cid, 2025, 5)
    assert _is_pdf(out)


def test_low_attendance_pdf(tmp_path: Path, conn: sqlite3.Connection) -> None:
    cid = _seed(conn)
    from app.reports.attendance_pdf import write_low_attendance

    out = write_low_attendance(tmp_path / "low.pdf", conn, cid, 2025, 5, 75.0)
    assert _is_pdf(out)


def test_pdf_generators_handle_empty_class(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """A class with no students should still produce a valid PDF."""
    school_repo.create_school(conn, School(id=None, name="Empty School"))
    yid = school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label="2025-26",
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_active=True,
        ),
    )
    cid = class_repo.create_class(conn, Class(id=None, name="9", section="A", academic_year_id=yid))
    from app.reports.attendance_pdf import (
        write_daily_register,
        write_low_attendance,
        write_monthly_summary,
    )

    assert _is_pdf(write_daily_register(tmp_path / "d.pdf", conn, cid, "2025-05-01"))
    assert _is_pdf(write_monthly_summary(tmp_path / "m.pdf", conn, cid, 2025, 5))
    assert _is_pdf(write_low_attendance(tmp_path / "l.pdf", conn, cid, 2025, 5, 75.0))
