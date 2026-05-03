"""QThread workers for the Excel student-import pipeline.

There are two stages:

1. :class:`StudentImportValidateWorker` — opens the file, reads rows, runs
   each through ``student_service.validate_import_row``, and emits a list of
   ``ImportRow`` entries. The UI shows a preview so the user can inspect
   errors and decide whether to commit.
2. :class:`StudentImportCommitWorker` — given the validated rows, opens its
   *own* SQLite connection (workers must not share the UI's connection) and
   inserts every valid row in a single transaction.

Both workers expose ``progress(int, int)``, ``error(str)``, and a
``finished_with_*`` signal carrying the result. They support cancellation
via ``cancel()`` (cooperative — checked between rows).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.db.connection import open_connection
from app.reports.student_excel import read_rows
from app.services import student_service

log = logging.getLogger(__name__)


class _CancellableThread(QThread):
    """QThread with a tiny cancellation flag callers can poll."""

    error = Signal(str)
    progress = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class StudentImportValidateWorker(_CancellableThread):
    """Stage 1: read + validate. Emits ``finished_with_rows`` on success."""

    finished_with_rows = Signal(list)  # list[ImportRow]

    def __init__(self, file_path: str | Path, parent=None) -> None:
        super().__init__(parent)
        self._file_path = Path(file_path)

    def run(self) -> None:
        try:
            raw_rows = read_rows(self._file_path)
        except Exception as exc:
            log.exception("Could not read %s", self._file_path)
            self.error.emit(f"Could not read file: {exc}")
            return

        total = len(raw_rows)
        if total == 0:
            self.error.emit("The file contains no data rows.")
            return

        # Worker thread → its own connection. Read-only here.
        conn = open_connection()
        try:
            seen: set[str] = set()
            results = []
            for i, raw in enumerate(raw_rows, start=1):
                if self.cancelled:
                    return
                row = student_service.validate_import_row(
                    conn, line=i, raw=raw, seen_admission_nos=seen
                )
                results.append(row)
                self.progress.emit(i, total)
        finally:
            conn.close()

        self.finished_with_rows.emit(results)


class StudentImportCommitWorker(_CancellableThread):
    """Stage 2: insert valid rows in one transaction. Emits the insert count."""

    finished_with_count = Signal(int)

    def __init__(self, rows: list, parent=None) -> None:
        super().__init__(parent)
        self._rows = list(rows)

    def run(self) -> None:
        valid_rows = [r for r in self._rows if r.is_valid]
        total = len(valid_rows)
        if total == 0:
            self.error.emit("No valid rows to import.")
            return

        conn = open_connection()
        try:
            try:
                inserted = student_service.commit_import(conn, valid_rows)
            except Exception as exc:
                log.exception("Commit failed")
                self.error.emit(f"Could not import: {exc}")
                return
            # We commit in a single transaction inside the service; report
            # progress as 100% once we're done.
            self.progress.emit(total, total)
            self.finished_with_count.emit(inserted)
        finally:
            conn.close()


class StudentExportWorker(_CancellableThread):
    """Run the Excel export off the UI thread."""

    finished_with_path = Signal(str)

    def __init__(
        self,
        target_path: str | Path,
        *,
        search: str | None,
        class_id: int | None,
        status: str | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._target = Path(target_path)
        self._search = search
        self._class_id = class_id
        self._status = status

    def run(self) -> None:
        from app.reports.student_excel import write_export
        from app.repositories import student_repo

        conn = open_connection()
        try:
            students = student_repo.list_all_for_export(
                conn,
                search=self._search,
                class_id=self._class_id,
                status=self._status,
            )
        finally:
            conn.close()

        try:
            write_export(self._target, students)
        except Exception as exc:
            log.exception("Export failed")
            self.error.emit(f"Export failed: {exc}")
            return
        self.finished_with_path.emit(str(self._target))
