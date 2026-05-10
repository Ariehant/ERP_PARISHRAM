from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest


def _redirect_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SCHOOL_ERP_DATA", str(tmp_path))
    # Reload every module that snapshotted config values at import time.
    import app.config

    importlib.reload(app.config)
    import app.db.connection as conn_module

    importlib.reload(conn_module)
    import app.services.backup_service as backup_module

    importlib.reload(backup_module)
    return tmp_path


def test_auto_backup_writes_under_backup_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _redirect_data(tmp_path, monkeypatch)
    from app.config import BACKUP_DIR
    from app.db.connection import open_connection
    from app.db.migrator import run_migrations
    from app.services import backup_service

    conn = open_connection()
    run_migrations(conn)
    target = backup_service.auto_backup(conn)
    conn.close()

    assert target.is_file()
    assert target.parent == BACKUP_DIR
    assert target.name.startswith("auto_") and target.suffix == ".db"


def test_auto_backup_trim_keeps_n(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _redirect_data(tmp_path, monkeypatch)
    from app.config import BACKUP_DIR
    from app.db.connection import open_connection
    from app.db.migrator import run_migrations
    from app.services import backup_service

    conn = open_connection()
    run_migrations(conn)
    # Drop pre-existing fakes to make the assertion exact.
    BACKUP_DIR.mkdir(exist_ok=True)
    for i in range(20):
        (BACKUP_DIR / f"auto_2024010{i:02d}_000000.db").write_bytes(b"")
    backup_service.auto_backup(conn)  # adds one + trims
    auto = list(BACKUP_DIR.glob("auto_*.db"))
    assert len(auto) <= 14
    conn.close()


def test_manual_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _redirect_data(tmp_path, monkeypatch)
    from app.db.connection import open_connection
    from app.db.migrator import run_migrations
    from app.services import backup_service

    conn = open_connection()
    run_migrations(conn)
    target = tmp_path / "manual.db"
    written = backup_service.manual_backup(conn, target)
    conn.close()

    assert written.is_file()
    # Resulting DB must be a valid SQLite file with our tables.
    check = sqlite3.connect(str(target))
    cur = check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
    assert cur.fetchone() is not None
    check.close()


def test_restore_renames_old_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _redirect_data(tmp_path, monkeypatch)
    from app.config import DB_PATH
    from app.db.connection import open_connection
    from app.db.migrator import run_migrations
    from app.services import backup_service

    # Set up the original DB.
    conn = open_connection()
    run_migrations(conn)
    conn.execute("INSERT INTO schools (name) VALUES ('Original School')")
    backup_path = tmp_path / "snapshot.db"
    backup_service.manual_backup(conn, backup_path)
    conn.close()

    # Mutate the live DB so we can prove the restore overwrote it.
    conn2 = open_connection()
    conn2.execute("UPDATE schools SET name = 'Mutated'")
    conn2.close()

    replaced = backup_service.restore_backup(backup_path)
    assert replaced.is_file()
    assert replaced.name.startswith(DB_PATH.name + ".replaced.")

    # New DB has the original school.
    fresh = open_connection()
    cur = fresh.execute("SELECT name FROM schools LIMIT 1")
    assert cur.fetchone()[0] == "Original School"
    fresh.close()
