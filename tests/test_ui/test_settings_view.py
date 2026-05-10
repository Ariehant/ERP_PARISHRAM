from __future__ import annotations

import importlib
import os
import sqlite3
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")


from app.models.school import School
from app.repositories import school_repo


def test_settings_view_renders_six_tabs(qtbot, conn: sqlite3.Connection) -> None:
    school_repo.create_school(conn, School(id=None, name="Demo School"))
    from app.ui.views.settings.view import SettingsView

    view = SettingsView(conn)
    qtbot.addWidget(view)
    assert view.tabs.count() == 6
    titles = [view.tabs.tabText(i) for i in range(view.tabs.count())]
    assert "School" in titles
    assert "Audit log" in titles


def test_school_tab_save_round_trip(qtbot, conn: sqlite3.Connection) -> None:
    school_repo.create_school(conn, School(id=None, name="Old Name", address="Old address"))
    from app.ui.views.settings.school_tab import SchoolTab

    tab = SchoolTab(conn)
    qtbot.addWidget(tab)
    assert tab.name.text() == "Old Name"
    tab.name.setText("New Name")
    tab.address.setPlainText("New address")

    from PySide6.QtWidgets import QMessageBox

    captured: list[str] = []
    qtbot.addWidget(tab)
    orig = QMessageBox.information

    def _capture(*args, **kwargs):
        captured.append(args[2])
        return QMessageBox.StandardButton.Ok

    QMessageBox.information = _capture  # type: ignore[assignment]
    try:
        tab._save()
    finally:
        QMessageBox.information = orig  # type: ignore[assignment]

    fresh = school_repo.get_first_school(conn)
    assert fresh is not None
    assert fresh.name == "New Name"
    assert fresh.address == "New address"


def test_audit_tab_lists_records(qtbot, conn: sqlite3.Connection) -> None:
    from app.repositories import audit_log_repo

    audit_log_repo.record(
        conn, user_id=None, action="login", entity="users", entity_id=1, details="admin"
    )
    from app.ui.views.settings.audit_tab import AuditLogTab

    tab = AuditLogTab(conn)
    qtbot.addWidget(tab)
    assert tab._model.total_rows >= 1


def test_backup_tab_lists_existing(
    qtbot, conn: sqlite3.Connection, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SCHOOL_ERP_DATA", str(tmp_path))
    import app.config

    importlib.reload(app.config)
    import app.services.backup_service as bs

    importlib.reload(bs)

    bdir = app.config.BACKUP_DIR
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "auto_20250101_000000.db").write_bytes(b"")

    from app.ui.views.settings.backup_tab import BackupTab

    tab = BackupTab(conn)
    qtbot.addWidget(tab)
    assert tab.list.count() >= 1
