from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class GradeBand:
    id: int | None
    grade: str
    min_percent: float
    max_percent: float
    remarks: str | None = None
