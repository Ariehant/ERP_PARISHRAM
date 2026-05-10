"""Atomic counters table.

Used for receipt numbers etc. Each ``next_value(name)`` call returns the
next integer for that counter name, allocating the row if needed. Caller
is expected to wrap this in a transaction (the fee service does).
"""

from __future__ import annotations

import sqlite3


def next_value(conn: sqlite3.Connection, name: str) -> int:
    """Increment and return the new value for counter ``name``."""
    cur = conn.execute(
        """
        INSERT INTO counters (name, value) VALUES (?, 1)
        ON CONFLICT(name) DO UPDATE SET value = value + 1
        RETURNING value
        """,
        (name,),
    )
    row = cur.fetchone()
    return int(row[0])


def peek(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("SELECT value FROM counters WHERE name = ?", (name,))
    row = cur.fetchone()
    return int(row[0]) if row else 0
