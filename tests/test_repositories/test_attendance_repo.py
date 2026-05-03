from __future__ import annotations

import sqlite3

import pytest

from app.models.school import AcademicYear
from app.models.structure import Class
from app.repositories import attendance_repo, class_repo, school_repo


def _seed_class_with_students(conn: sqlite3.Connection, n: int = 3) -> tuple[int, list[int]]:
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
    student_ids: list[int] = []
    for i in range(n):
        cur = conn.execute(
            "INSERT INTO students (admission_no, first_name, admission_date, class_id, status, roll_no) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (f"ADM/{i + 1:03d}", f"Student{i + 1:02d}", "2025-04-01", cid, i + 1),
        )
        student_ids.append(int(cur.lastrowid))
    return cid, student_ids


def test_list_for_class_and_date_includes_unmarked(conn: sqlite3.Connection) -> None:
    cid, _sids = _seed_class_with_students(conn)
    rows = attendance_repo.list_for_class_and_date(conn, cid, "2025-05-01")
    assert len(rows) == 3
    assert all(r[4] is None for r in rows)


def test_upsert_marks_inserts_then_updates(conn: sqlite3.Connection) -> None:
    cid, sids = _seed_class_with_students(conn)
    written = attendance_repo.upsert_marks(
        conn,
        date_iso="2025-05-01",
        marks={sids[0]: "P", sids[1]: "A", sids[2]: "L"},
    )
    assert written == 3

    # Re-mark the first student — should update, not error.
    written = attendance_repo.upsert_marks(conn, date_iso="2025-05-01", marks={sids[0]: "L"})
    assert written == 1
    rows = attendance_repo.list_for_class_and_date(conn, cid, "2025-05-01")
    statuses = {r[0]: r[4] for r in rows}
    assert statuses[sids[0]] == "L"


def test_upsert_rejects_invalid_status(conn: sqlite3.Connection) -> None:
    _cid, sids = _seed_class_with_students(conn)
    with pytest.raises(ValueError):
        attendance_repo.upsert_marks(conn, date_iso="2025-05-01", marks={sids[0]: "Z"})


def test_monthly_summary_counts(conn: sqlite3.Connection) -> None:
    cid, sids = _seed_class_with_students(conn)
    # Student 0: 3 P, 1 A, 1 L
    for i, status in enumerate(["P", "P", "P", "A", "L"], start=1):
        attendance_repo.upsert_marks(conn, date_iso=f"2025-05-{i:02d}", marks={sids[0]: status})
    # Student 1: 1 P, 4 H
    for i, status in enumerate(["P", "H", "H", "H", "H"], start=1):
        attendance_repo.upsert_marks(conn, date_iso=f"2025-05-{i:02d}", marks={sids[1]: status})

    summary = attendance_repo.monthly_summary_for_class(conn, cid, 2025, 5)
    by_id = {row["student_id"]: row for row in summary}
    assert by_id[sids[0]]["p"] == 3
    assert by_id[sids[0]]["a"] == 1
    assert by_id[sids[0]]["l"] == 1
    assert by_id[sids[0]]["h"] == 0
    assert by_id[sids[1]]["p"] == 1
    assert by_id[sids[1]]["h"] == 4
    # Student 2 has no rows yet.
    assert by_id[sids[2]]["p"] == 0
    assert by_id[sids[2]]["a"] == 0


def test_monthly_summary_excludes_other_months(conn: sqlite3.Connection) -> None:
    cid, sids = _seed_class_with_students(conn)
    attendance_repo.upsert_marks(conn, date_iso="2025-04-30", marks={sids[0]: "P"})
    attendance_repo.upsert_marks(conn, date_iso="2025-05-01", marks={sids[0]: "A"})
    attendance_repo.upsert_marks(conn, date_iso="2025-06-01", marks={sids[0]: "L"})

    summary = attendance_repo.monthly_summary_for_class(conn, cid, 2025, 5)
    target = next(r for r in summary if r["student_id"] == sids[0])
    assert target["p"] == 0
    assert target["a"] == 1
    assert target["l"] == 0


def test_clear_for_class_and_date(conn: sqlite3.Connection) -> None:
    cid, sids = _seed_class_with_students(conn)
    attendance_repo.upsert_marks(conn, date_iso="2025-05-01", marks={sid: "P" for sid in sids})
    cleared = attendance_repo.clear_for_class_and_date(conn, cid, "2025-05-01")
    assert cleared == 3
    rows = attendance_repo.list_for_class_and_date(conn, cid, "2025-05-01")
    assert all(r[4] is None for r in rows)


def test_inactive_students_excluded(conn: sqlite3.Connection) -> None:
    cid, sids = _seed_class_with_students(conn)
    conn.execute("UPDATE students SET status = 'inactive' WHERE id = ?", (sids[2],))
    rows = attendance_repo.list_for_class_and_date(conn, cid, "2025-05-01")
    assert {r[0] for r in rows} == {sids[0], sids[1]}
