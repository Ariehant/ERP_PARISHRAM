from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")


from app.models.fee import FeeStructure
from app.models.school import AcademicYear
from app.models.structure import Class
from app.repositories import class_repo, school_repo
from app.services import fee_service


def _seed(conn: sqlite3.Connection) -> tuple[int, int]:
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
    sid = int(cur.lastrowid)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[FeeStructure(None, cid, yid, "Tuition", 50000, "monthly", None)],
    )
    return cid, sid


def test_fees_view_renders_four_tabs(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn)
    from app.ui.views.fees.view import FeesView

    view = FeesView(conn)
    qtbot.addWidget(view)
    assert view.tabs.count() == 4


def test_collection_view_lookup_and_save(qtbot, conn: sqlite3.Connection) -> None:
    _cid, sid = _seed(conn)
    from app.ui.views.fees.collection_view import FeeCollectionView

    view = FeeCollectionView(conn)
    qtbot.addWidget(view)

    view.admission_input.setText("ADM/1")
    view._lookup()
    assert view._student_id == sid
    # Pending row exists.
    assert view.table.rowCount() == 1

    # Tick the row, set amount, save.
    from PySide6.QtCore import Qt

    view.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    spin = view.table.cellWidget(0, 6)
    spin.setValue(500.0)  # Rs.500 = 50000 paise (one monthly instalment).

    # Replace QMessageBox so the test doesn't pop dialogs.
    from PySide6.QtWidgets import QMessageBox

    captured: list[str] = []
    orig_info = QMessageBox.information

    def _capture(parent, title, text, *args, **kwargs):
        captured.append(text)
        return QMessageBox.StandardButton.Ok

    QMessageBox.information = _capture  # type: ignore[assignment]
    try:
        view._save()
    finally:
        QMessageBox.information = orig_info  # type: ignore[assignment]

    assert any("RCP/2025-26/" in c for c in captured)
    assert view._last_receipt_no is not None
    assert view._last_receipt_no.startswith("RCP/2025-26/")


def test_defaulters_view_lists_unpaid(qtbot, conn: sqlite3.Connection) -> None:
    _cid, _sid = _seed(conn)
    from app.ui.views.fees.defaulters_view import FeeDefaultersView

    view = FeeDefaultersView(conn)
    qtbot.addWidget(view)
    # The seeded student has no payments + monthly fee structure -> defaulter.
    assert view.table.rowCount() == 1
