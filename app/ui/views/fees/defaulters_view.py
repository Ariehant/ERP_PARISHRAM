"""Defaulters view -- per-class list of students with outstanding fees."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories import class_repo, school_repo
from app.services import fee_service
from app.utils.formatters import format_inr
from app.workers.fee_pdf import FeePDFWorker

log = logging.getLogger(__name__)

_HEADERS = ("Adm. No.", "Name", "Outstanding")


class FeeDefaultersView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._pdf_worker: FeePDFWorker | None = None
        self._progress: QProgressDialog | None = None

        self._build_ui()
        self._populate_class_combo()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        self.class_combo.currentIndexChanged.connect(self._load)
        bar.addWidget(self.class_combo)
        bar.addStretch(1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load)
        bar.addWidget(self.refresh_btn)
        self.export_btn = QPushButton("Export PDF...")
        self.export_btn.clicked.connect(self._export_pdf)
        bar.addWidget(self.export_btn)
        layout.addLayout(bar)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

    def _populate_class_combo(self) -> None:
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        active = school_repo.get_active_academic_year(self._conn)
        if active is not None and active.id is not None:
            for cls in class_repo.list_for_year(self._conn, active.id):
                self.class_combo.addItem(f"{cls.name}-{cls.section}", cls.id)
        if self.class_combo.count() == 0:
            self.class_combo.addItem("(no classes)", None)
            self.class_combo.setEnabled(False)
        self.class_combo.blockSignals(False)

    def refresh(self) -> None:
        previous = self.class_combo.currentData()
        self._populate_class_combo()
        if previous is not None:
            i = self.class_combo.findData(previous)
            if i >= 0:
                self.class_combo.setCurrentIndex(i)
        self._load()

    def _load(self) -> None:
        cid = self.class_combo.currentData()
        self.table.setRowCount(0)
        if cid is None:
            self.summary_label.setText("Pick a class.")
            return
        rows = fee_service.defaulters_for_class(self._conn, cid)
        self.table.setRowCount(len(rows))
        total = 0
        for r, d in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(d.admission_no))
            self.table.setItem(r, 1, QTableWidgetItem(d.name))
            amount_item = QTableWidgetItem(format_inr(d.outstanding_paise))
            amount_item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight))
            self.table.setItem(r, 2, amount_item)
            total += d.outstanding_paise
        self.summary_label.setText(
            f"{len(rows)} defaulter(s). Total outstanding: {format_inr(total)}"
        )

    def _export_pdf(self) -> None:
        cid = self.class_combo.currentData()
        if cid is None:
            QMessageBox.warning(self, "Pick first", "Pick a class first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save defaulters PDF", "defaulters.pdf", "PDF files (*.pdf)"
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

        worker = FeePDFWorker(Path(path), "defaulters", {"class_id": cid}, parent=self)
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
