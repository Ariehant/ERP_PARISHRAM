"""Application entry point.

Boot sequence:
    1. Parse args, configure logging, ensure data dirs.
    2. Open DB connection, run migrations.
    3. If no school + admin → run SetupWizard.
    4. Else → show LoginDialog until a user is authenticated.
    5. Show MainWindow.
"""

from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import APP_NAME, ensure_runtime_dirs
from app.db.connection import open_connection
from app.db.migrator import run_migrations
from app.repositories import school_repo, user_repo
from app.services import setup_service
from app.ui.login_dialog import LoginDialog
from app.ui.main_window import MainWindow
from app.ui.setup_wizard import SetupWizard
from app.utils.errors import MigrationError
from app.utils.logging import configure_logging

log = logging.getLogger(__name__)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="school-erp", description=APP_NAME)
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv if argv is not None else sys.argv[1:]))

    ensure_runtime_dirs()
    configure_logging(debug=args.debug)
    log.info("Starting %s", APP_NAME)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    conn = open_connection()
    try:
        applied = run_migrations(conn)
        if applied:
            log.info("Applied migrations: %s", ", ".join(applied))
    except MigrationError as exc:
        QMessageBox.critical(None, "Database error", str(exc))
        return 2

    # Setup wizard if first run.
    if not setup_service.is_setup_complete(conn):
        wizard = SetupWizard(conn)
        if wizard.exec() == 0:
            log.info("Setup cancelled; exiting.")
            return 0
        # Setup created the first user — go straight into the app under that user.
        user = user_repo.get_by_username(conn, wizard.created_username or "")
        if user is None:
            QMessageBox.critical(
                None, "Setup error", "Setup completed but the new user could not be loaded."
            )
            return 3
    else:
        school = school_repo.get_first_school(conn)
        login = LoginDialog(conn, school_name=school.name if school else None)
        if login.exec() == 0:
            log.info("Login cancelled; exiting.")
            return 0
        assert login.user is not None
        user = login.user

    window = MainWindow(conn, user)
    window.show()

    # Auto-backup on clean shutdown -- the brief asks for one of these on
    # every successful exit (kept to the most recent 14 in data/backups/).
    def _on_quit() -> None:
        try:
            from app.services import backup_service

            backup_service.auto_backup(conn)
        except Exception as exc:
            log.warning("Auto-backup on shutdown failed: %s", exc)

    app.aboutToQuit.connect(_on_quit)
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
