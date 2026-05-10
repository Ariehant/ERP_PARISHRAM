"""Per-student fee ledger view + PDF export."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories import student_repo
from app.services import fee_service
from app.utils.formatters import format_date, format_inr
from app.workers.fee_pdf import FeePDFWorker

log = logging.getLogger(__name__)

_LEDGER_HEADERS = ("Date", "Receipt", "Mode", "Head", "Amount")
_PENDING_HEADERS = ("Head", "Frequency", "Due", "Paid", "Outstanding")


class FeeLedgerView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._student_id: int | None = None
        self._pdf_worker: FeePDFWorker | None = None
        self._progress: QProgressDialog | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Lookup bar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Admission no.:"))
        self.admission_input = QLineEdit()
        self.admission_input.returnPressed.connect(self._lookup)
        bar.addWidget(self.admission_input, 1)
        self.lookup_btn = QPushButton("Look up")
        self.lookup_btn.clicked.connect(self._lookup)
        bar.addWidget(self.lookup_btn)
        self.export_btn = QPushButton("Export PDF...")
        self.export_btn.clicked.connect(self._export_pdf)
        self.export_btn.setEnabled(False)
        bar.addWidget(self.export_btn)
        layout.addLayout(bar)

        self.student_label = QLabel("No student selected.")
        font = self.student_label.font()
        font.setBold(True)
        self.student_label.setFont(font)
        layout.addWidget(self.student_label)

        layout.addWidget(QLabel("Payments"))
        self.ledger_table = QTableWidget(0, len(_LEDGER_HEADERS))
        self.ledger_table.setHorizontalHeaderLabels(list(_LEDGER_HEADERS))
        self.ledger_table.verticalHeader().setVisible(False)
        self.ledger_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ledger_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ledger_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.ledger_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.ledger_table, 1)

        layout.addWidget(QLabel("Outstanding by head"))
        self.pending_table = QTableWidget(0, len(_PENDING_HEADERS))
        self.pending_table.setHorizontalHeaderLabels(list(_PENDING_HEADERS))
        self.pending_table.verticalHeader().setVisible(False)
        self.pending_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pending_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pending_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.pending_table)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

    def refresh(self) -> None:
        if self._student_id is not None:
            self._load(self._student_id)

    def _lookup(self) -> None:
        text = self.admission_input.text().strip()
        if not text:
            return
        student = student_repo.get_by_admission_no(self._conn, text)
        if student is None:
            QMessageBox.warning(self, "Not found", f"No student with adm. no. {text!r}.")
            return
        self._student_id = student.id
        full_name = " ".join(filter(None, [student.first_name, student.last_name]))
        self.student_label.setText(f"{full_name} ({student.admission_no})")
        self.export_btn.setEnabled(True)
        self._load(student.id)

    def _load(self, student_id: int) -> None:
        items = fee_service.ledger_for_student(self._conn, student_id)
        self.ledger_table.setRowCount(len(items))
        total_paid = 0
        for r, it in enumerate(items):
            self.ledger_table.setItem(r, 0, QTableWidgetItem(format_date(it["payment_date"])))
            self.ledger_table.setItem(r, 1, QTableWidgetItem(it["receipt_no"]))
            self.ledger_table.setItem(r, 2, QTableWidgetItem(it["mode"].upper()))
            self.ledger_table.setItem(r, 3, QTableWidgetItem(it["head"]))
            amount_item = QTableWidgetItem(format_inr(it["amount_paise"]))
            amount_item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight))
            self.ledger_table.setItem(r, 4, amount_item)
            total_paid += it["amount_paise"]

        pending = fee_service.pending_for_student(self._conn, student_id)
        self.pending_table.setRowCount(len(pending))
        total_out = 0
        for r, p in enumerate(pending):
            self.pending_table.setItem(r, 0, QTableWidgetItem(p.head))
            self.pending_table.setItem(r, 1, QTableWidgetItem(p.frequency))
            self.pending_table.setItem(r, 2, QTableWidgetItem(format_inr(p.total_due_paise)))
            self.pending_table.setItem(r, 3, QTableWidgetItem(format_inr(p.paid_paise)))
            outstanding_item = QTableWidgetItem(format_inr(p.outstanding_paise))
            self.pending_table.setItem(r, 4, outstanding_item)
            total_out += p.outstanding_paise

        self.summary_label.setText(
            f"Total paid: {format_inr(total_paid)} | Total outstanding: {format_inr(total_out)}"
        )

    def _export_pdf(self) -> None:
        if self._student_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save fee ledger PDF",
            f"ledger_{self._student_id}.pdf",
            "PDF files (*.pdf)",
        )
        if not path:
            return
        if self._pdf_worker is not None and self._pdf_worker.isRunning():
            QMessageBox.information(self, "Busy", "A PDF is already being generated.")
            return
        progress = QProgressDialog("Generating PDF...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        self._progress = progress

        worker = FeePDFWorker(Path(path), "ledger", {"student_id": self._student_id}, parent=self)
        worker.error.connect(self._on_error)
        worker.finished_with_path.connect(self._on_done)
        worker.finished.connect(self._cleanup)
        self._pdf_worker = worker
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
        if self._pdf_worker is not None:
            self._pdf_worker.deleteLater()
            self._pdf_worker = None
        self._progress = None
