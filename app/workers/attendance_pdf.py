"""QThread worker for attendance PDFs.

Runs on its own connection. ``kind`` selects which generator to call:

- ``"daily"``    — needs ``class_id`` and ``date_iso``
- ``"monthly"``  — needs ``class_id``, ``year``, ``month``
- ``"low"``      — needs ``class_id``, ``year``, ``month``, ``threshold``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.db.connection import open_connection

log = logging.getLogger(__name__)


class AttendancePDFWorker(QThread):
    error = Signal(str)
    finished_with_path = Signal(str)

    def __init__(
        self,
        target: str | Path,
        kind: str,
        params: dict[str, Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._target = Path(target)
        self._kind = kind
        self._params = dict(params)

    def run(self) -> None:
        try:
            from app.reports import attendance_pdf
        except Exception as exc:
            self.error.emit(f"Could not load PDF library: {exc}")
            return

        conn = open_connection()
        try:
            if self._kind == "daily":
                attendance_pdf.write_daily_register(self._target, conn, **self._params)
            elif self._kind == "monthly":
                attendance_pdf.write_monthly_summary(self._target, conn, **self._params)
            elif self._kind == "low":
                attendance_pdf.write_low_attendance(self._target, conn, **self._params)
            else:
                self.error.emit(f"Unknown report kind: {self._kind!r}")
                return
        except Exception as exc:
            log.exception("Attendance PDF generation failed")
            self.error.emit(str(exc))
            return
        finally:
            conn.close()

        self.finished_with_path.emit(str(self._target))
