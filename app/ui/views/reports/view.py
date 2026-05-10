"""Reports hub - one-stop list of every PDF report.

Layout: four group boxes (Students / Academic / Finance / Documents)
with a button per report. Each button opens a small picker dialog,
asks for a save path, and spawns ``ReportsPDFWorker`` on a thread.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.views.reports.pickers import (
    CharacterCertPickerDialog,
    ClassExamPickerDialog,
    ClassPickerDialog,
    StudentPickerDialog,
    TCPickerDialog,
    YearPickerDialog,
)
from app.workers.reports_pdf import ReportsPDFWorker

log = logging.getLogger(__name__)


class ReportsHubView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._worker: ReportsPDFWorker | None = None
        self._progress: QProgressDialog | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        intro = QLabel(
            "Pick a report. Each one runs in a background worker -- the UI "
            "stays responsive while the PDF is built."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._students_box())
        layout.addWidget(self._academic_box())
        layout.addWidget(self._finance_box())
        layout.addWidget(self._documents_box())
        layout.addStretch(1)

    def _section(self, title: str, buttons: list[tuple[str, callable]]) -> QGroupBox:
        box = QGroupBox(title)
        grid = QGridLayout(box)
        for i, (label, slot) in enumerate(buttons):
            row, col = divmod(i, 3)
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            grid.addWidget(btn, row, col)
        return box

    def _students_box(self) -> QGroupBox:
        return self._section(
            "Students",
            [
                ("Student profile...", self._on_profile),
                ("Class roster...", self._on_roster),
                ("Admission register...", self._on_admission_register),
                ("Withdrawal register...", self._on_withdrawal_register),
            ],
        )

    def _academic_box(self) -> QGroupBox:
        return self._section(
            "Academic",
            [
                ("Mark sheet...", self._on_mark_sheet),
                ("Report card - single...", self._on_report_card_single),
                ("Report card - whole class...", self._on_report_card_batch),
                ("Attendance reports...", self._on_attendance_link),
            ],
        )

    def _finance_box(self) -> QGroupBox:
        return self._section(
            "Finance",
            [
                ("Fee ledger / defaulters...", self._on_fee_link),
            ],
        )

    def _documents_box(self) -> QGroupBox:
        return self._section(
            "Documents",
            [
                ("Transfer certificate...", self._on_tc),
                ("Character certificate...", self._on_character_cert),
                ("ID card sheet...", self._on_id_cards),
            ],
        )

    # ------------------------------------------------------------------
    def _ask_save_path(self, default_name: str) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", default_name, "PDF files (*.pdf)")
        return Path(path) if path else None

    def _spawn(self, target: Path, kind: str, params: dict) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "A PDF is already being generated. Please wait.")
            return
        progress = QProgressDialog("Generating PDF...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        self._progress = progress

        worker = ReportsPDFWorker(target, kind, params, parent=self)
        worker.error.connect(self._on_error)
        worker.finished_with_path.connect(self._on_done)
        worker.finished.connect(self._cleanup)
        self._worker = worker
        worker.start()

    def _on_error(self, message: str) -> None:
        if self._progress is not None:
            self._progress.cancel()
        QMessageBox.critical(self, "PDF failed", message)

    def _on_done(self, path: str) -> None:
        if self._progress is not None:
            self._progress.cancel()
        QMessageBox.information(self, "PDF saved", f"Saved to:\n{path}")

    def _cleanup(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self._progress = None

    # ------------------------------------------------------------------
    # Slot wrappers -- each opens a picker, then spawns the worker.
    # ------------------------------------------------------------------
    def _open_picker(self, dialog_cls):
        dlg = dialog_cls(self._conn, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return None
        return dlg.params

    def _on_profile(self) -> None:
        params = self._open_picker(StudentPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"profile_{params['student_id']}.pdf")
        if path:
            self._spawn(path, "profile", params)

    def _on_roster(self) -> None:
        params = self._open_picker(ClassPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"roster_{params['class_id']}.pdf")
        if path:
            self._spawn(path, "roster", params)

    def _on_mark_sheet(self) -> None:
        params = self._open_picker(ClassExamPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"marksheet_{params['class_id']}_{params['exam_id']}.pdf")
        if path:
            self._spawn(path, "mark_sheet", params)

    def _on_report_card_single(self) -> None:
        params = self._open_picker(StudentPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"report_card_{params['student_id']}.pdf")
        if path:
            self._spawn(path, "report_card", params)

    def _on_report_card_batch(self) -> None:
        params = self._open_picker(ClassPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"report_cards_class_{params['class_id']}.pdf")
        if path:
            self._spawn(path, "report_cards_batch", params)

    def _on_admission_register(self) -> None:
        params = self._open_picker(YearPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"admission_register_{params['academic_year_id']}.pdf")
        if path:
            self._spawn(path, "admission_register", params)

    def _on_withdrawal_register(self) -> None:
        params = self._open_picker(YearPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"withdrawal_register_{params['academic_year_id']}.pdf")
        if path:
            self._spawn(path, "withdrawal_register", params)

    def _on_tc(self) -> None:
        params = self._open_picker(TCPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"tc_{params['student_id']}.pdf")
        if path:
            self._spawn(path, "tc", params)

    def _on_character_cert(self) -> None:
        params = self._open_picker(CharacterCertPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"character_cert_{params['student_id']}.pdf")
        if path:
            self._spawn(path, "character_cert", params)

    def _on_id_cards(self) -> None:
        params = self._open_picker(ClassPickerDialog)
        if params is None:
            return
        path = self._ask_save_path(f"id_cards_{params['class_id']}.pdf")
        if path:
            self._spawn(path, "id_cards", params)

    def _on_attendance_link(self) -> None:
        QMessageBox.information(
            self,
            "Attendance reports",
            "The Attendance module's 'Reports' tab generates daily registers, "
            "monthly summaries, and low-attendance lists. Open it from the "
            "sidebar.",
        )

    def _on_fee_link(self) -> None:
        QMessageBox.information(
            self,
            "Fee reports",
            "The Fees module has dedicated tabs for ledger and defaulter "
            "PDFs. Open it from the sidebar.",
        )

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        # Pickers re-fetch on each open, so nothing to do here.
        pass
