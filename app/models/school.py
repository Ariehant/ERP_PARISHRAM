from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class School:
    id: int | None
    name: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    logo_path: str | None = None
    affiliation_no: str | None = None
    created_at: str | None = None


@dataclass(slots=True, frozen=True)
class AcademicYear:
    id: int | None
    label: str
    start_date: str
    end_date: str
    is_active: bool = False
