from __future__ import annotations

import sqlite3

from app.repositories import audit_log_repo


def test_record_and_list(conn: sqlite3.Connection) -> None:
    audit_log_repo.record(
        conn, user_id=None, action="login", entity="users", entity_id=1, details="alice"
    )
    # user_id=None for system events; a real user id would need a row in users.
    audit_log_repo.record(
        conn, user_id=None, action="create", entity="students", entity_id=42, details="ADM/1"
    )
    rows = audit_log_repo.list_page(conn)
    # Newest first.
    assert rows[0]["entity"] == "students"
    assert rows[1]["entity"] == "users"
    assert audit_log_repo.count(conn) == 2


def test_filter_by_action_and_entity(conn: sqlite3.Connection) -> None:
    audit_log_repo.record(conn, user_id=None, action="login", entity="users", entity_id=1)
    audit_log_repo.record(conn, user_id=None, action="create", entity="students")
    audit_log_repo.record(conn, user_id=None, action="create", entity="fee_payments")

    assert audit_log_repo.count(conn, action="create") == 2
    assert audit_log_repo.count(conn, entity="users") == 1
    assert audit_log_repo.count(conn, action="create", entity="students") == 1


def test_distinct_helpers(conn: sqlite3.Connection) -> None:
    audit_log_repo.record(conn, user_id=None, action="login", entity="users")
    audit_log_repo.record(conn, user_id=None, action="create", entity="students")
    assert "login" in audit_log_repo.distinct_actions(conn)
    assert "students" in audit_log_repo.distinct_entities(conn)
