from __future__ import annotations

import sqlite3

from app.repositories import counters_repo


def test_next_value_starts_at_one_per_name(conn: sqlite3.Connection) -> None:
    assert counters_repo.next_value(conn, "receipts") == 1
    assert counters_repo.next_value(conn, "receipts") == 2
    assert counters_repo.next_value(conn, "receipts") == 3
    # Different counter name -> independent sequence.
    assert counters_repo.next_value(conn, "other") == 1


def test_peek(conn: sqlite3.Connection) -> None:
    assert counters_repo.peek(conn, "x") == 0
    counters_repo.next_value(conn, "x")
    counters_repo.next_value(conn, "x")
    assert counters_repo.peek(conn, "x") == 2
