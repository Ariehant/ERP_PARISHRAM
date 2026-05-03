"""Integration test for the import worker pipeline.

Workers each open their own connection (via ``open_connection()``), so the
test points the data dir at a temp directory and runs the migrator there
before kicking the worker off. We use a ``QEventLoop`` to await the QThread
without a qtbot fixture (so this also runs without showing any windows).
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("openpyxl")


def _redirect_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SCHOOL_ERP_DATA", str(tmp_path))
    import app.config

    importlib.reload(app.config)
    # Reload modules that captured the old DB_PATH at import time.
    import app.db.connection as conn_mod
    import app.db.migrator as migrator_mod
    import app.utils.photos as photos_mod
    import app.workers.student_import as workers_mod

    importlib.reload(conn_mod)
    importlib.reload(migrator_mod)
    importlib.reload(photos_mod)
    importlib.reload(workers_mod)
    return tmp_path


def test_validate_then_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qtbot) -> None:
    _redirect_data_dir(tmp_path, monkeypatch)

    from PySide6.QtCore import QEventLoop

    from app.db.connection import open_connection
    from app.db.migrator import run_migrations
    from app.reports.student_excel import write_template
    from app.workers.student_import import (
        StudentImportCommitWorker,
        StudentImportValidateWorker,
    )

    # Bootstrap the DB at the redirected path.
    boot = open_connection()
    run_migrations(boot)
    boot.close()

    # Use the template (which has one valid sample row) as the input file.
    template = write_template(tmp_path / "in.xlsx")

    # ---- Stage 1: validate ----
    validate = StudentImportValidateWorker(template)
    rows: list = []

    def _capture(payload):
        rows.extend(payload)

    validate.finished_with_rows.connect(_capture)
    loop = QEventLoop()
    validate.finished.connect(loop.quit)
    validate.start()
    loop.exec()

    assert len(rows) == 1
    assert rows[0].is_valid is True

    # ---- Stage 2: commit ----
    commit = StudentImportCommitWorker(rows)
    inserted: list[int] = []
    commit.finished_with_count.connect(inserted.append)
    loop2 = QEventLoop()
    commit.finished.connect(loop2.quit)
    commit.start()
    loop2.exec()

    assert inserted == [1]

    # Verify the row landed in the DB.
    conn = open_connection()
    try:
        from app.repositories import student_repo

        assert student_repo.count(conn) == 1
    finally:
        conn.close()
