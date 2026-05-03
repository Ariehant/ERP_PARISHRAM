"""Pytest fixtures.

Each test gets a fresh, fully-migrated, in-memory SQLite DB by way of a
temp file on disk (SQLite shared in-memory has thread / cross-connection
quirks; a temp file is simpler and just as fast for our scale).
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

# Make the Qt offscreen platform the default for headless test environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    """A migrated connection on a fresh temp DB."""
    from app.db.connection import open_connection
    from app.db.migrator import run_migrations

    c = open_connection(db_path)
    run_migrations(c)
    try:
        yield c
    finally:
        c.close()


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the app's data dir into a fresh temp dir for UI/integration tests."""
    monkeypatch.setenv("SCHOOL_ERP_DATA", str(tmp_path))
    # Force config to re-read the env var by reloading the module.
    import importlib

    import app.config as config

    importlib.reload(config)
    return tmp_path
