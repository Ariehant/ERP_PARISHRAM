from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")


from app.models.school import AcademicYear
from app.models.structure import Class
from app.repositories import attendance_repo, class_repo, school_repo


def _seed(conn: sqlite3.Connection, n: int = 3) -> tuple[int, list[int]]:
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


def test_attendance_view_renders(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn)
    from app.ui.views.attendance.view import AttendanceView

    view = AttendanceView(conn)
    qtbot.addWidget(view)
    assert view.tabs.count() == 3
    # Daily tab is open by default.
    assert view.daily_view.table.rowCount() == 3
    # Switching to monthly populates day columns.
    view.tabs.setCurrentIndex(1)
    assert view.monthly_view.table.columnCount() >= 3  # Roll + Name + at least one day
    view.tabs.setCurrentIndex(2)
    assert view.reports_view.class_combo.count() >= 1


def test_mark_all_present_and_save(qtbot, conn: sqlite3.Connection) -> None:
    cid, _sids = _seed(conn)
    from app.ui.views.attendance.daily_view import DailyAttendanceView

    view = DailyAttendanceView(conn)
    qtbot.addWidget(view)
    view.date_edit.setDate(view.date_edit.date().fromString("2025-05-01", "yyyy-MM-dd"))
    view._reload()
    view._mark_all_present()
    view._save()

    rows = attendance_repo.list_for_class_and_date(conn, cid, "2025-05-01")
    assert all(r[4] == "P" for r in rows)


def test_save_blocks_when_nothing_marked(qtbot, conn: sqlite3.Connection, monkeypatch) -> None:
    _seed(conn)
    from app.ui.views.attendance.daily_view import DailyAttendanceView

    view = DailyAttendanceView(conn)
    qtbot.addWidget(view)

    captured: list[str] = []
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: captured.append(args[2]) or QMessageBox.StandardButton.Ok,
    )
    view._save()
    assert any("Mark all" in c or "no students" in c.lower() for c in captured)
