from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AuditLog:
    id: int | None
    action: str
    entity: str
    user_id: int | None = None
    entity_id: int | None = None
    timestamp: str | None = None
    details: str | None = None
