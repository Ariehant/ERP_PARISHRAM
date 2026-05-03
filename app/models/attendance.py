from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Attendance:
    id: int | None
    student_id: int
    date: str
    status: str  # 'P', 'A', 'L', 'H'
    marked_by: int | None = None
    marked_at: str | None = None
