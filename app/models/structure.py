from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Class:
    id: int | None
    name: str
    section: str
    academic_year_id: int
    class_teacher_id: int | None = None


@dataclass(slots=True, frozen=True)
class Subject:
    id: int | None
    name: str
    class_id: int
    code: str | None = None
    max_marks: int = 100
    is_optional: bool = False
