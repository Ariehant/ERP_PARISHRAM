from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class User:
    id: int | None
    username: str
    password_hash: str
    role: str  # admin/operator/viewer
    full_name: str | None = None
    is_active: bool = True
    created_at: str | None = None
