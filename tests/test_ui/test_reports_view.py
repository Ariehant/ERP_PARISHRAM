from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")


from app.models.school import AcademicYear
from app.models.structure import Class
from app.repositories import class_repo, school_repo


def _seed(conn: sqlite3.Connection) -> int:
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
    cur = conn.execute(
        "INSERT INTO students (admission_no, first_name, admission_date, class_id, status) "
        "VALUES ('ADM/1', 'Aarav', '2025-04-01', ?, 'active')",
        (cid,),
    )
    return int(cur.lastrowid)


def test_reports_hub_renders(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn)
    from app.ui.views.reports.view import ReportsHubView

    view = ReportsHubView(conn)
    qtbot.addWidget(view)
    # Hub is just a static layout -- no failures means render is OK.


def test_class_picker_dialog(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn)
    from app.ui.views.reports.pickers import ClassPickerDialog

    dlg = ClassPickerDialog(conn)
    qtbot.addWidget(dlg)
    assert dlg.combo.count() >= 1
    assert dlg.combo.currentData() is not None


def test_student_picker_dialog_finds_by_admission(qtbot, conn: sqlite3.Connection) -> None:
    sid = _seed(conn)
    from app.ui.views.reports.pickers import StudentPickerDialog

    dlg = StudentPickerDialog(conn)
    qtbot.addWidget(dlg)
    dlg.adm.setText("ADM/1")
    dlg._on_ok()
    assert dlg.params == {"student_id": sid}


def test_student_picker_dialog_unknown_admission(
    qtbot, conn: sqlite3.Connection, monkeypatch
) -> None:
    _seed(conn)
    from PySide6.QtWidgets import QMessageBox

    from app.ui.views.reports.pickers import StudentPickerDialog

    captured: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: captured.append(args[2]) or QMessageBox.StandardButton.Ok,
    )
    dlg = StudentPickerDialog(conn)
    qtbot.addWidget(dlg)
    dlg.adm.setText("DOESNT_EXIST")
    dlg._on_ok()
    assert dlg.params == {}
    assert any("Not found" in c or "No student" in c for c in captured)
