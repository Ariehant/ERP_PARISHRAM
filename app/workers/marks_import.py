"""Marks import workers (validate, then commit).

Same two-stage pattern as the student import: a validate worker reads the
file and produces a list of :class:`MarksImportRow` for the preview UI,
then a commit worker upserts every valid cell in a single transaction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.db.connection import open_connection
from app.repositories import class_repo, student_repo

log = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class MarksCellInput:
    student_id: int
    subject_id: int
    marks_obtained: float


@dataclass(slots=True, frozen=True)
class MarksImportRow:
    """One xlsx row, after validation."""

    line: int
    admission_no: str
    student_name: str | None
    student_id: int | None
    cells: tuple[MarksCellInput, ...]
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


class _CancellableThread(QThread):
    error = Signal(str)
    progress = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True


class MarksImportValidateWorker(_CancellableThread):
    finished_with_rows = Signal(list)

    def __init__(
        self,
        file_path: str | Path,
        class_id: int,
        exam_id: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._path = Path(file_path)
        self._class_id = class_id
        self._exam_id = exam_id

    def run(self) -> None:
        from app.reports.marks_excel import parse_subject_header, read_rows

        try:
            raw_rows = read_rows(self._path)
        except Exception as exc:
            self.error.emit(f"Could not read file: {exc}")
            return
        if not raw_rows:
            self.error.emit("The file contains no data rows.")
            return

        conn = open_connection()
        try:
            subjects = class_repo.list_subjects_for_class(conn, self._class_id)
            subject_by_name: dict[str, int] = {
                s.name.lower(): s.id for s in subjects if s.id is not None
            }
            subject_max: dict[int, int] = {s.id: s.max_marks for s in subjects if s.id is not None}
            roster = student_repo.list_all_for_export(
                conn, class_id=self._class_id, status="active"
            )
            by_adm: dict[str, int] = {s.admission_no: s.id for s in roster if s.id is not None}
            roster_names: dict[int, str] = {
                s.id: " ".join(filter(None, [s.first_name, s.last_name]))
                for s in roster
                if s.id is not None
            }

            # Header validation -- we need the column → subject_id mapping.
            sample = raw_rows[0]
            header_to_subject: dict[str, int] = {}
            unknown_headers: list[str] = []
            for h in sample["marks"]:
                name, _max = parse_subject_header(h)
                sid = subject_by_name.get(name.lower())
                if sid is None:
                    unknown_headers.append(h)
                else:
                    header_to_subject[h] = sid

            results: list[MarksImportRow] = []
            total = len(raw_rows)
            for i, raw in enumerate(raw_rows, start=1):
                if self._cancelled:
                    return
                errors: list[str] = []
                if unknown_headers and i == 1:
                    errors.append(
                        "Unknown subject column(s): " + ", ".join(repr(h) for h in unknown_headers)
                    )
                admission_no = raw["admission_no"]
                student_id = by_adm.get(admission_no)
                if student_id is None:
                    errors.append(
                        f"No active student with admission no. {admission_no!r} in this class."
                    )

                cells: list[MarksCellInput] = []
                for h, value in raw["marks"].items():
                    if value is None:
                        continue
                    sid = header_to_subject.get(h)
                    if sid is None:
                        # Already reported above as an unknown header.
                        continue
                    max_marks = subject_max[sid]
                    if value < 0 or value > max_marks:
                        errors.append(f"{h}: {value} is outside 0..{max_marks}")
                        continue
                    if student_id is not None:
                        cells.append(
                            MarksCellInput(
                                student_id=student_id,
                                subject_id=sid,
                                marks_obtained=float(value),
                            )
                        )
                if student_id is not None and not cells and not errors:
                    errors.append("No marks entered for this student.")

                results.append(
                    MarksImportRow(
                        line=i,
                        admission_no=admission_no,
                        student_name=roster_names.get(student_id) if student_id else None,
                        student_id=student_id,
                        cells=tuple(cells),
                        errors=tuple(errors),
                    )
                )
                self.progress.emit(i, total)
        finally:
            conn.close()

        self.finished_with_rows.emit(results)


class MarksImportCommitWorker(_CancellableThread):
    finished_with_count = Signal(int)

    def __init__(self, exam_id: int, rows: list[MarksImportRow], parent=None) -> None:
        super().__init__(parent)
        self._exam_id = exam_id
        self._rows = list(rows)

    def run(self) -> None:
        from app.services import mark_service

        valid_rows = [r for r in self._rows if r.is_valid]
        if not valid_rows:
            self.error.emit("No valid rows to import.")
            return

        # Flatten into the service's MarkInput list.
        flat: list[mark_service.MarkInput] = []
        class_id = None
        for r in valid_rows:
            if r.student_id is None:
                continue
            for cell in r.cells:
                flat.append(
                    mark_service.MarkInput(
                        student_id=cell.student_id,
                        subject_id=cell.subject_id,
                        marks_obtained=cell.marks_obtained,
                    )
                )

        if not flat:
            self.error.emit("No cells to import.")
            return

        # We need class_id for the service. Look it up from the first row's student.
        from app.repositories import student_repo

        conn = open_connection()
        try:
            first_student = student_repo.get(conn, flat[0].student_id)
            if first_student is None or first_student.class_id is None:
                self.error.emit("Could not resolve class for the imported students.")
                return
            class_id = first_student.class_id
            try:
                count = mark_service.save_class_exam_marks(
                    conn, class_id=class_id, exam_id=self._exam_id, inputs=flat
                )
            except Exception as exc:
                log.exception("Marks commit failed")
                self.error.emit(str(exc))
                return
        finally:
            conn.close()

        self.progress.emit(count, count)
        self.finished_with_count.emit(count)
