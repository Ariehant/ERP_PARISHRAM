from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Exam:
    id: int | None
    name: str
    academic_year_id: int
    exam_type: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    weightage: int = 100


@dataclass(slots=True, frozen=True)
class Mark:
    id: int | None
    exam_id: int
    student_id: int
    subject_id: int
    max_marks: int
    marks_obtained: float | None = None
    grade: str | None = None
    remarks: str | None = None
