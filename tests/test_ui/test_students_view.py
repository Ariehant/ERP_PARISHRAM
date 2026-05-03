from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")


from app.models.people import Student
from app.repositories import student_repo


def _seed(conn: sqlite3.Connection, n: int = 5) -> None:
    for i in range(n):
        student_repo.create(
            conn,
            Student(
                id=None,
                admission_no=f"ADM/{i:03d}",
                first_name=f"Student{i:02d}",
                last_name="Test",
                admission_date="2025-04-01",
                gender="M" if i % 2 == 0 else "F",
                status="active",
            ),
        )


def test_students_list_view_renders(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn, n=7)
    from app.ui.views.students.list_view import StudentsListView

    view = StudentsListView(conn)
    qtbot.addWidget(view)

    assert view._model.total_rows == 7
    assert view._model.rowCount() == 7

    # Selecting a row enables the edit/view/delete buttons.
    view._table.table.selectRow(0)
    assert view.edit_btn.isEnabled()
    assert view.view_btn.isEnabled()
    assert view.delete_btn.isEnabled()


def test_students_list_search_filters(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn, n=3)
    student_repo.create(
        conn,
        Student(
            id=None,
            admission_no="UNIQ/001",
            first_name="Riya",
            last_name="Singh",
            admission_date="2025-04-01",
            status="active",
        ),
    )

    from app.ui.views.students.list_view import StudentsListView

    view = StudentsListView(conn)
    qtbot.addWidget(view)

    view.search_edit.setText("Riya")
    view._on_filter_changed()
    assert view._model.total_rows == 1
    assert view._model.rowCount() == 1


def test_paged_table_pagination(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn, n=12)
    from app.config import DEFAULT_PAGE_SIZE  # noqa: F401 - sanity import
    from app.ui.views.students.list_view import StudentsListView

    view = StudentsListView(conn)
    qtbot.addWidget(view)

    # Force a small page size to exercise pagination.
    view._model._page_size = 5  # type: ignore[attr-defined]
    view._model.refresh()
    assert view._model.total_pages == 3
    assert view._model.rowCount() == 5

    view._model.next_page()
    assert view._model.page == 2
    assert view._model.rowCount() == 5

    view._model.next_page()
    assert view._model.page == 3
    assert view._model.rowCount() == 2

    view._model.next_page()  # capped at total_pages
    assert view._model.page == 3
