"""Fee PDF worker -- runs receipt / ledger / defaulters off the UI thread."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.db.connection import open_connection

log = logging.getLogger(__name__)


class FeePDFWorker(QThread):
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
        from app.reports import fee_pdf

        conn = open_connection()
        try:
            if self._kind == "receipt_a4":
                fee_pdf.write_receipt_a4(self._target, conn, **self._params)
            elif self._kind == "receipt_thermal":
                fee_pdf.write_receipt_thermal(self._target, conn, **self._params)
            elif self._kind == "ledger":
                fee_pdf.write_ledger(self._target, conn, **self._params)
            elif self._kind == "defaulters":
                fee_pdf.write_defaulters(self._target, conn, **self._params)
            else:
                self.error.emit(f"Unknown report kind: {self._kind!r}")
                return
        except Exception as exc:
            log.exception("Fee PDF generation failed")
            self.error.emit(str(exc))
            return
        finally:
            conn.close()

        self.finished_with_path.emit(str(self._target))
