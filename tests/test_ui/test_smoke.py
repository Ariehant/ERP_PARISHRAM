"""Phase 1 UI smoke tests using pytest-qt.

Skip the entire file if Qt cannot find a usable platform (some CI envs).
"""

from __future__ import annotations

import os
import sqlite3

import pytest

# Force offscreen so headless CI works.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")


from app.models.user import User
from app.repositories import user_repo
from app.services.setup_service import SetupRequest, perform_initial_setup
from app.utils.security import hash_password


def _seed_admin(conn: sqlite3.Connection) -> None:
    user_repo.create_user(
        conn,
        User(
            id=None,
            username="admin",
            password_hash=hash_password("hunter2x"),
            role="admin",
            full_name="Principal",
            is_active=True,
        ),
    )


def _seed_setup(conn: sqlite3.Connection) -> None:
    perform_initial_setup(
        conn,
        SetupRequest(
            school_name="Parishram Public School",
            address="Lucknow",
            phone="9999999999",
            email="x@y.test",
            affiliation_no="A1",
            academic_year_label="2025-26",
            academic_year_start="2025-04-01",
            academic_year_end="2026-03-31",
            admin_username="admin",
            admin_full_name="Principal",
            admin_password="hunter2x",
        ),
    )


def test_main_window_opens(qtbot, conn: sqlite3.Connection) -> None:
    _seed_setup(conn)
    user = user_repo.get_by_username(conn, "admin")
    assert user is not None

    from app.ui.main_window import MainWindow

    win = MainWindow(conn, user)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    # Sidebar has every module entry.
    assert win.sidebar.count() >= 5
    # Stack has matching pages.
    assert win.stack.count() == win.sidebar.count()
    # Selecting a different sidebar row switches the stack.
    win.sidebar.setCurrentRow(1)
    assert win.stack.currentIndex() == 1


def test_login_dialog_rejects_bad_password(qtbot, conn: sqlite3.Connection) -> None:
    _seed_admin(conn)

    from app.ui.login_dialog import LoginDialog

    dlg = LoginDialog(conn)
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)
    dlg.username.setText("admin")
    dlg.password.setText("WRONG")
    dlg._try_login()

    assert dlg.user is None
    assert dlg.error_label.isVisible()
    assert dlg.error_label.text() != ""


def test_login_dialog_accepts_good_password(qtbot, conn: sqlite3.Connection) -> None:
    _seed_admin(conn)

    from app.ui.login_dialog import LoginDialog

    dlg = LoginDialog(conn)
    qtbot.addWidget(dlg)
    dlg.username.setText("admin")
    dlg.password.setText("hunter2x")
    dlg._try_login()

    assert dlg.user is not None
    assert dlg.user.username == "admin"
