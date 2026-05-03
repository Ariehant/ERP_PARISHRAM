from __future__ import annotations

import sqlite3

import pytest

from app.models.school import AcademicYear
from app.models.structure import Class
from app.repositories import attendance_repo, class_repo, school_repo
from app.services import attendance_service
from app.utils.errors import ValidationError


def _seed(conn: sqlite3.Connection, n: int = 4) -> tuple[int, list[int]]:
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
    sids: list[int] = []
    for i in range(n):
        cur = conn.execute(
            "INSERT INTO students (admission_no, first_name, admission_date, class_id, status, roll_no) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (f"ADM/{i + 1:03d}", f"Stu{i + 1:02d}", "2025-04-01", cid, i + 1),
        )
        sids.append(int(cur.lastrowid))
    return cid, sids


def test_save_class_attendance_happy_path(conn: sqlite3.Connection) -> None:
    cid, sids = _seed(conn)
    written = attendance_service.save_class_attendance(
        conn,
        class_id=cid,
        date_iso="2025-05-01",
        marks={sids[0]: "P", sids[1]: "A"},
    )
    assert written == 2


def test_save_rejects_bad_date(conn: sqlite3.Connection) -> None:
    cid, sids = _seed(conn)
    with pytest.raises(ValidationError) as exc:
        attendance_service.save_class_attendance(
            conn, class_id=cid, date_iso="01-05-2025", marks={sids[0]: "P"}
        )
    assert exc.value.field == "date"


def test_save_rejects_bad_status(conn: sqlite3.Connection) -> None:
    cid, sids = _seed(conn)
    with pytest.raises(ValidationError):
        attendance_service.save_class_attendance(
            conn, class_id=cid, date_iso="2025-05-01", marks={sids[0]: "Z"}
        )


def test_save_rejects_empty_marks(conn: sqlite3.Connection) -> None:
    cid, _ = _seed(conn)
    with pytest.raises(ValidationError):
        attendance_service.save_class_attendance(
            conn, class_id=cid, date_iso="2025-05-01", marks={}
        )


def test_save_rejects_student_not_in_class(conn: sqlite3.Connection) -> None:
    cid, sids = _seed(conn)
    yid = school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label="2026-27",
            start_date="2026-04-01",
            end_date="2027-03-31",
        ),
    )
    other_cid = class_repo.create_class(
        conn, Class(id=None, name="6", section="A", academic_year_id=yid)
    )
    cur = conn.execute(
        "INSERT INTO students (admission_no, first_name, admission_date, class_id) "
        "VALUES ('OTHER/1', 'X', '2026-04-01', ?)",
        (other_cid,),
    )
    other_student = int(cur.lastrowid)
    with pytest.raises(ValidationError):
        attendance_service.save_class_attendance(
            conn,
            class_id=cid,
            date_iso="2025-05-01",
            marks={sids[0]: "P", other_student: "P"},
        )
    # And nothing was written (transaction rolled back at validation).
    rows = attendance_repo.list_for_class_and_date(conn, cid, "2025-05-01")
    assert all(r[4] is None for r in rows)


def test_class_summary_percentage(conn: sqlite3.Connection) -> None:
    cid, sids = _seed(conn)
    # Student 0: 3 P, 1 A, 1 L → present_eff = 4, total_eff = 5 → 80%
    for i, status in enumerate(["P", "P", "P", "A", "L"], start=1):
        attendance_service.save_class_attendance(
            conn,
            class_id=cid,
            date_iso=f"2025-05-{i:02d}",
            marks={sids[0]: status},
        )

    summary = attendance_service.class_summary(conn, cid, 2025, 5)
    target = next(s for s in summary if s.student_id == sids[0])
    assert target.percentage == pytest.approx(80.0)
    assert target.effective_total == 5


def test_low_attendance_threshold(conn: sqlite3.Connection) -> None:
    cid, sids = _seed(conn)
    # Student 0: 4 P, 1 A → 80%
    for i, status in enumerate(["P", "P", "P", "P", "A"], start=1):
        attendance_service.save_class_attendance(
            conn,
            class_id=cid,
            date_iso=f"2025-05-{i:02d}",
            marks={sids[0]: status},
        )
    # Student 1: 2 P, 3 A → 40%
    for i, status in enumerate(["P", "P", "A", "A", "A"], start=1):
        attendance_service.save_class_attendance(
            conn,
            class_id=cid,
            date_iso=f"2025-05-{i:02d}",
            marks={sids[1]: status},
        )

    low = attendance_service.low_attendance(conn, cid, 2025, 5, threshold=75.0)
    low_ids = {s.student_id for s in low}
    assert sids[1] in low_ids
    assert sids[0] not in low_ids
    # Students with no marked sessions are skipped.
    assert sids[2] not in low_ids


def test_holidays_excluded_from_percentage(conn: sqlite3.Connection) -> None:
    cid, sids = _seed(conn)
    # 2 P, 1 H → percentage = 100% (holiday excluded)
    for i, status in enumerate(["P", "P", "H"], start=1):
        attendance_service.save_class_attendance(
            conn,
            class_id=cid,
            date_iso=f"2025-05-{i:02d}",
            marks={sids[0]: status},
        )
    summary = attendance_service.class_summary(conn, cid, 2025, 5)
    target = next(s for s in summary if s.student_id == sids[0])
    assert target.h == 1
    assert target.effective_total == 2
    assert target.percentage == pytest.approx(100.0)
