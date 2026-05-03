"""Apply numbered ``.sql`` files from ``app/db/migrations/`` to the database.

Naming convention: ``NNN_description.sql`` (zero-padded). The migrator records
applied filenames in ``schema_migrations`` and skips them on subsequent runs.

Each migration file may contain multiple statements; the whole file runs in
one transaction. If a migration fails it rolls back, raises
``MigrationError``, and the database is left at the previous version.
"""

from __future__ import annotations

import contextlib
import logging
import re
import sqlite3
from pathlib import Path

from app.config import MIGRATIONS_DIR
from app.utils.errors import MigrationError

log = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^(\d{3,})_[A-Za-z0-9_\-]+\.sql$")


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _applied(conn: sqlite3.Connection) -> set[str]:
    cur = conn.execute("SELECT filename FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def _discover(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    files = []
    for p in directory.iterdir():
        if p.is_file() and _NAME_RE.match(p.name):
            files.append(p)
    files.sort(key=lambda p: p.name)
    return files


def run_migrations(conn: sqlite3.Connection, migrations_dir: Path | None = None) -> list[str]:
    """Apply every pending migration. Returns the list of filenames applied."""
    directory = migrations_dir or MIGRATIONS_DIR
    _ensure_migrations_table(conn)
    already = _applied(conn)
    applied: list[str] = []

    for path in _discover(directory):
        if path.name in already:
            continue
        log.info("Applying migration %s", path.name)
        body = path.read_text(encoding="utf-8")
        # executescript() does its own transaction management, so we wrap the
        # body with BEGIN/COMMIT inside the script for atomicity. (The conn
        # is in autocommit mode — isolation_level=None — so no outer tx.)
        script = "BEGIN;\n" + body + "\nCOMMIT;"
        try:
            conn.executescript(script)
        except sqlite3.Error as exc:
            with contextlib.suppress(sqlite3.OperationalError):
                conn.execute("ROLLBACK")
            raise MigrationError(f"Migration {path.name} failed: {exc}") from exc
        try:
            conn.execute("INSERT INTO schema_migrations(filename) VALUES (?)", (path.name,))
        except sqlite3.Error as exc:
            raise MigrationError(
                f"Migration {path.name} applied but bookkeeping failed: {exc}"
            ) from exc
        applied.append(path.name)

    return applied
