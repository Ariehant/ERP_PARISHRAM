from __future__ import annotations

from pathlib import Path

from app.db.connection import open_connection
from app.db.migrator import run_migrations


def test_migrations_apply_idempotently(db_path: Path) -> None:
    conn = open_connection(db_path)
    try:
        applied_first = run_migrations(conn)
        assert "001_initial.sql" in applied_first

        # Sanity-check key tables exist.
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        for required in (
            "schools",
            "academic_years",
            "students",
            "staff",
            "classes",
            "subjects",
            "attendance",
            "exams",
            "marks",
            "fee_structure",
            "fee_payments",
            "fee_payment_items",
            "users",
            "audit_log",
            "schema_migrations",
        ):
            assert required in tables, f"missing table: {required}"

        # Re-running is a no-op.
        applied_second = run_migrations(conn)
        assert applied_second == []
    finally:
        conn.close()


def test_pragmas_set(db_path: Path) -> None:
    conn = open_connection(db_path)
    try:
        cur = conn.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1
        cur = conn.execute("PRAGMA journal_mode")
        assert cur.fetchone()[0].lower() == "wal"
    finally:
        conn.close()
