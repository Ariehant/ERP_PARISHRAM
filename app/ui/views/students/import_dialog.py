"""Excel import preview + commit dialog.

Walkflow:
    1. User picks a file (or downloads the template).
    2. ``StudentImportValidateWorker`` validates rows on a worker thread.
    3. The preview table shows valid rows in normal style and invalid rows
       highlighted in red with their error messages.
    4. "Import valid rows" spawns ``StudentImportCommitWorker``.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.reports.student_excel import write_template
from app.services.student_service import ImportRow
from app.workers.student_import import (
    StudentImportCommitWorker,
    StudentImportValidateWorker,
)

log = logging.getLogger(__name__)

_HEADERS = (
    "Line",
    "Admission no.",
    "Name",
    "Date of birth",
    "Gender",
    "Errors",
)
_ERROR_BG = QBrush(QColor("#fde2e2"))


class StudentImportDialog(QDialog):
    """Pick → validate → preview → commit. Emits ``imported`` count on accept."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn  # used by callers; workers open their own conns
        self._rows: list[ImportRow] = []
        self.imported_count: int = 0
        self._validate_worker: StudentImportValidateWorker | None = None
        self._commit_worker: StudentImportCommitWorker | None = None

        self.setWindowTitle("Import students from Excel")
        self.setMinimumSize(820, 520)

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.path_label = QLabel("Pick an Excel (.xlsx) file to begin.")
        self.path_label.setWordWrap(True)
        top.addWidget(self.path_label, 1)
        self.pick_btn = QPushButton("Pick file…")
        self.pick_btn.clicked.connect(self._on_pick)
        self.template_btn = QPushButton("Save template…")
        self.template_btn.clicked.connect(self._on_template)
        top.addWidget(self.pick_btn)
        top.addWidget(self.template_btn)
        layout.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setColumnCount(len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        # Buttons
        self.buttons = QDialogButtonBox()
        self.cancel_btn = self.buttons.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        self.cancel_btn.clicked.connect(self.reject)
        self.import_btn = self.buttons.addButton(
            "Import valid rows", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._on_import)
        layout.addWidget(self.buttons)

    # ------------------------------------------------------------------
    def _on_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save import template",
            "students_template.xlsx",
            "Excel files (*.xlsx)",
        )
        if not path:
            return
        try:
            written = write_template(path)
        except Exception as exc:
            QMessageBox.critical(self, "Template", f"Could not write template: {exc}")
            return
        QMessageBox.information(self, "Template", f"Template saved to:\n{written}")

    def _on_pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick Excel file",
            "",
            "Excel files (*.xlsx)",
        )
        if not path:
            return
        if not Path(path).is_file():
            QMessageBox.warning(self, "File", "That file does not exist.")
            return
        self.path_label.setText(path)
        self._start_validation(path)

    def _start_validation(self, path: str) -> None:
        self.import_btn.setEnabled(False)
        self.pick_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.summary_label.setText("Validating…")
        self.table.setRowCount(0)

        worker = StudentImportValidateWorker(path, parent=self)
        worker.progress.connect(self._on_progress)
        worker.error.connect(self._on_validate_error)
        worker.finished_with_rows.connect(self._on_validation_done)
        worker.finished.connect(self._on_worker_finished)
        self._validate_worker = worker
        worker.start()

    def _on_progress(self, current: int, total: int) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(current)

    def _on_validate_error(self, message: str) -> None:
        self.progress.setVisible(False)
        self.pick_btn.setEnabled(True)
        QMessageBox.warning(self, "Import", message)
        self.summary_label.setText("")

    def _on_validation_done(self, rows: list[ImportRow]) -> None:
        self._rows = rows
        valid = sum(1 for r in rows if r.is_valid)
        invalid = len(rows) - valid
        self.summary_label.setText(
            f"Validated {len(rows)} row(s): {valid} valid, {invalid} with errors."
        )
        self._populate_table(rows)
        self.import_btn.setEnabled(valid > 0)
        self.progress.setVisible(False)
        self.pick_btn.setEnabled(True)

    def _populate_table(self, rows: list[ImportRow]) -> None:
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            raw = row.raw
            cells = [
                str(row.line),
                str(raw.get("admission_no") or ""),
                f"{raw.get('first_name') or ''} {raw.get('last_name') or ''}".strip(),
                str(raw.get("dob") or ""),
                str(raw.get("gender") or ""),
                "; ".join(row.errors) if row.errors else "OK",
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if not row.is_valid:
                    item.setBackground(_ERROR_BG)
                if c in (0, 4):
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                self.table.setItem(r, c, item)

    # ------------------------------------------------------------------
    def _on_import(self) -> None:
        valid = [r for r in self._rows if r.is_valid]
        if not valid:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm import",
            f"Import {len(valid)} student(s) into the database?\n"
            "This runs in a single transaction — if anything fails, "
            "nothing will be inserted.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.import_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.pick_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.summary_label.setText("Importing…")

        worker = StudentImportCommitWorker(self._rows, parent=self)
        worker.progress.connect(self._on_progress)
        worker.error.connect(self._on_commit_error)
        worker.finished_with_count.connect(self._on_commit_done)
        worker.finished.connect(self._on_worker_finished)
        self._commit_worker = worker
        worker.start()

    def _on_commit_error(self, message: str) -> None:
        self.progress.setVisible(False)
        self.import_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.pick_btn.setEnabled(True)
        QMessageBox.critical(self, "Import failed", message)

    def _on_commit_done(self, count: int) -> None:
        self.imported_count = count
        QMessageBox.information(self, "Import complete", f"Imported {count} student(s).")
        self.accept()

    def _on_worker_finished(self) -> None:
        # Tidy worker references when the QThread finishes.
        for slot in ("_validate_worker", "_commit_worker"):
            worker = getattr(self, slot)
            if worker is not None and not worker.isRunning():
                worker.deleteLater()
                setattr(self, slot, None)

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        for worker in (self._validate_worker, self._commit_worker):
            if worker is not None and worker.isRunning():
                worker.cancel()
                worker.wait(3000)
        super().closeEvent(event)
