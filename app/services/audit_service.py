"""Thin wrapper over the audit_log repository.

Call ``record_event`` from any service that needs to log a write. The
wrapper is best-effort: a failed audit insert logs the exception but does
not fail the calling transaction.
"""

from __future__ import annotations

import logging
import sqlite3

from app.repositories import audit_log_repo

log = logging.getLogger(__name__)


def record_event(
    conn: sqlite3.Connection,
    *,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    details: str | None = None,
) -> None:
    try:
        audit_log_repo.record(
            conn,
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details,
        )
    except sqlite3.Error as exc:
        log.warning("Audit log insert failed: %s", exc)
