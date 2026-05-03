from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")


from app.models.people import Staff
from app.models.school import AcademicYear
from app.models.structure import Class, Subject
from app.repositories import school_repo
from app.services import class_service, staff_service


def _year(conn: sqlite3.Connection) -> int:
    return school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label="2025-26",
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_active=True,
        ),
    )


def test_masters_view_renders_both_tabs(qtbot, conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    class_service.save_class(
        conn,
        Class(id=None, name="5", section="A", academic_year_id=yid),
        [Subject(id=None, name="Math", class_id=0, max_marks=100)],
    )
    staff_service.create_staff(
        conn,
        Staff(id=None, emp_code="EMP/1", name="Asha", role="teacher"),
    )

    from app.ui.views.masters.view import MastersView

    view = MastersView(conn)
    qtbot.addWidget(view)

    # Tabs exist.
    assert view.tabs.count() == 2

    # Classes tab shows 1 class.
    assert view.classes_view._model.total_rows == 1

    # Switching tabs.
    view.tabs.setCurrentIndex(1)
    assert view.staff_view._model.total_rows == 1
    view.tabs.setCurrentIndex(0)
    assert view.classes_view._model.total_rows == 1


def test_class_form_shows_active_year_default(qtbot, conn: sqlite3.Connection) -> None:
    _year(conn)
    from app.ui.views.masters.class_form import ClassFormDialog

    dlg = ClassFormDialog(conn)
    qtbot.addWidget(dlg)
    # Active year should be selected by default.
    assert dlg.year_combo.count() == 1
    assert dlg.year_combo.currentData() is not None


def test_student_form_class_combo_populated(qtbot, conn: sqlite3.Connection) -> None:
    yid = _year(conn)
    class_service.save_class(
        conn,
        Class(id=None, name="5", section="A", academic_year_id=yid),
        [],
    )
    class_service.save_class(
        conn,
        Class(id=None, name="5", section="B", academic_year_id=yid),
        [],
    )

    from app.ui.views.students.form_dialog import StudentFormDialog

    dlg = StudentFormDialog(conn)
    qtbot.addWidget(dlg)
    # First entry is "(unassigned)", then both classes.
    assert dlg.class_combo.count() == 3
    assert dlg.class_combo.itemData(0) is None
    assert "5-A" in dlg.class_combo.itemText(1)
