from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Document:
    id: int | None
    student_id: int
    doc_type: str
    file_path: str
    uploaded_at: str | None = None


@dataclass(slots=True, frozen=True)
class Remark:
    id: int | None
    student_id: int
    date: str
    note: str
    category: str | None = None
    by_user: int | None = None
