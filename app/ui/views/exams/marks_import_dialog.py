"""Marks import preview + commit dialog."""

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

from app.workers.marks_import import (
    MarksImportCommitWorker,
    MarksImportRow,
    MarksImportValidateWorker,
)

log = logging.getLogger(__name__)

_HEADERS = ("Line", "Adm. No.", "Student", "Cells", "Errors")
_ERROR_BG = QBrush(QColor("#fde2e2"))


class MarksImportDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        class_id: int,
        exam_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._class_id = class_id
        self._exam_id = exam_id
        self._rows: list[MarksImportRow] = []
        self.imported_count: int = 0
        self._validate_worker: MarksImportValidateWorker | None = None
        self._commit_worker: MarksImportCommitWorker | None = None

        self.setWindowTitle("Import marks from Excel")
        self.setMinimumSize(820, 480)

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.path_label = QLabel("Pick the filled-in template (.xlsx) to begin.")
        self.path_label.setWordWrap(True)
        top.addWidget(self.path_label, 1)
        self.pick_btn = QPushButton("Pick file...")
        self.pick_btn.clicked.connect(self._on_pick)
        top.addWidget(self.pick_btn)
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

        self.buttons = QDialogButtonBox()
        self.cancel_btn = self.buttons.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        self.cancel_btn.clicked.connect(self.reject)
        self.import_btn = self.buttons.addButton(
            "Import valid rows", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._on_commit)
        layout.addWidget(self.buttons)

    # ------------------------------------------------------------------
    def _on_pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pick marks file", "", "Excel files (*.xlsx)")
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
        self.summary_label.setText("Validating...")
        self.table.setRowCount(0)

        worker = MarksImportValidateWorker(path, self._class_id, self._exam_id, parent=self)
        worker.error.connect(self._on_validate_error)
        worker.progress.connect(self._on_progress)
        worker.finished_with_rows.connect(self._on_validation_done)
        worker.finished.connect(self._cleanup)
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

    def _on_validation_done(self, rows: list) -> None:
        self._rows = rows
        valid = sum(1 for r in rows if r.is_valid)
        invalid = len(rows) - valid
        cells = sum(len(r.cells) for r in rows if r.is_valid)
        self.summary_label.setText(
            f"Validated {len(rows)} row(s): {valid} valid ({cells} cells), {invalid} with errors."
        )
        self._populate(rows)
        self.import_btn.setEnabled(valid > 0)
        self.progress.setVisible(False)
        self.pick_btn.setEnabled(True)

    def _populate(self, rows: list[MarksImportRow]) -> None:
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            cells_text = ", ".join(str(c.marks_obtained) for c in row.cells) if row.cells else ""
            errors = "; ".join(row.errors) if row.errors else "OK"
            values = [
                str(row.line),
                row.admission_no,
                row.student_name or "(unknown)",
                cells_text,
                errors,
            ]
            for c, txt in enumerate(values):
                item = QTableWidgetItem(txt)
                if not row.is_valid:
                    item.setBackground(_ERROR_BG)
                if c == 0:
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                self.table.setItem(r, c, item)

    # ------------------------------------------------------------------
    def _on_commit(self) -> None:
        valid = [r for r in self._rows if r.is_valid]
        if not valid:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm import",
            f"Import marks for {len(valid)} student(s)? The save runs in a single transaction.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.import_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.pick_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.summary_label.setText("Importing...")

        worker = MarksImportCommitWorker(self._exam_id, self._rows, parent=self)
        worker.error.connect(self._on_commit_error)
        worker.progress.connect(self._on_progress)
        worker.finished_with_count.connect(self._on_commit_done)
        worker.finished.connect(self._cleanup)
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
        QMessageBox.information(self, "Import complete", f"Saved {count} mark(s).")
        self.accept()

    def _cleanup(self) -> None:
        for slot in ("_validate_worker", "_commit_worker"):
            worker = getattr(self, slot)
            if worker is not None and not worker.isRunning():
                worker.deleteLater()
                setattr(self, slot, None)

    def closeEvent(self, event) -> None:
        for w in (self._validate_worker, self._commit_worker):
            if w is not None and w.isRunning():
                w.cancel()
                w.wait(3000)
        super().closeEvent(event)
