"""Audit-log repository (read + insert)."""

from __future__ import annotations

import sqlite3
from typing import Any


def record(
    conn: sqlite3.Connection,
    *,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    details: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO audit_log (user_id, action, entity, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, action, entity, entity_id, details),
    )
    return int(cur.lastrowid)


def list_page(
    conn: sqlite3.Connection,
    *,
    action: str | None = None,
    entity: str | None = None,
    user_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where, params = _filter_clauses(
        action=action,
        entity=entity,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
    )
    sql = (
        "SELECT a.id, a.user_id, u.username, a.action, a.entity, a.entity_id, "
        "       a.timestamp, a.details "
        "FROM audit_log a "
        "LEFT JOIN users u ON u.id = a.user_id "
        f"{where} "
        "ORDER BY a.id DESC LIMIT ? OFFSET ?"
    )
    cur = conn.execute(sql, [*params, limit, offset])
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "username": r[2] or "(system)",
            "action": r[3],
            "entity": r[4],
            "entity_id": r[5],
            "timestamp": r[6],
            "details": r[7],
        }
        for r in cur.fetchall()
    ]


def count(
    conn: sqlite3.Connection,
    *,
    action: str | None = None,
    entity: str | None = None,
    user_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    where, params = _filter_clauses(
        action=action,
        entity=entity,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
    )
    cur = conn.execute(f"SELECT COUNT(*) FROM audit_log a {where}", params)
    return int(cur.fetchone()[0])


def distinct_actions(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT DISTINCT action FROM audit_log ORDER BY action")
    return [r[0] for r in cur.fetchall()]


def distinct_entities(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT DISTINCT entity FROM audit_log ORDER BY entity")
    return [r[0] for r in cur.fetchall()]


def _filter_clauses(
    *,
    action: str | None,
    entity: str | None,
    user_id: int | None,
    date_from: str | None,
    date_to: str | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if action:
        clauses.append("a.action = ?")
        params.append(action)
    if entity:
        clauses.append("a.entity = ?")
        params.append(entity)
    if user_id is not None:
        clauses.append("a.user_id = ?")
        params.append(user_id)
    if date_from:
        clauses.append("a.timestamp >= ?")
        params.append(f"{date_from} 00:00:00")
    if date_to:
        clauses.append("a.timestamp <= ?")
        params.append(f"{date_to} 23:59:59")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params
