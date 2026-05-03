"""SQLite connection factory.

Rules from PROJECT_BRIEF.md:
- WAL mode, foreign_keys ON, etc. — applied on every connection open.
- One long-lived connection on the UI thread for reads.
- Worker threads open their *own* connection. Never share across threads.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH

# All PRAGMAs we want set on every connection. Run once at open time.
_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA temp_store = MEMORY",
    "PRAGMA cache_size = -20000",
    "PRAGMA mmap_size = 134217728",
)


def open_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a new SQLite connection with project PRAGMAs applied.

    Each thread that needs DB access should call this directly.
    """
    target = Path(db_path) if db_path is not None else DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(target),
        timeout=30.0,
        isolation_level=None,  # autocommit; we manage transactions explicitly.
        check_same_thread=True,
    )
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        for pragma in _PRAGMAS:
            cur.execute(pragma)
    finally:
        cur.close()
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Wrap a block in BEGIN/COMMIT (or ROLLBACK on exception).

    We use ``isolation_level=None`` (autocommit), so transactions must be
    opened explicitly. Use ``IMMEDIATE`` to acquire the write lock up front
    and avoid SQLITE_BUSY surprises mid-transaction.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
