"""Reports-hub PDF worker.

Single QThread, dispatches on ``kind``. Each kind maps to a generator
function in either ``app.reports.report_card_pdf`` or
``app.reports.general_pdfs``. Workers open their own DB connections per
the brief.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.db.connection import open_connection

log = logging.getLogger(__name__)


class ReportsPDFWorker(QThread):
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
        from app.reports import general_pdfs, report_card_pdf

        dispatch = {
            "profile": general_pdfs.write_profile,
            "roster": general_pdfs.write_class_roster,
            "mark_sheet": general_pdfs.write_mark_sheet,
            "admission_register": general_pdfs.write_admission_register,
            "withdrawal_register": general_pdfs.write_withdrawal_register,
            "tc": general_pdfs.write_transfer_certificate,
            "character_cert": general_pdfs.write_character_certificate,
            "id_cards": general_pdfs.write_id_card_sheet,
            "report_card": report_card_pdf.write_report_card,
            "report_cards_batch": report_card_pdf.write_class_report_cards,
        }
        func = dispatch.get(self._kind)
        if func is None:
            self.error.emit(f"Unknown report kind: {self._kind!r}")
            return

        conn = open_connection()
        try:
            func(self._target, conn, **self._params)
        except Exception as exc:
            log.exception("Reports PDF generation failed")
            self.error.emit(str(exc))
            return
        finally:
            conn.close()

        self.finished_with_path.emit(str(self._target))
