"""Students list view — search, filter, paginate, and route to add/edit/import.

UI does no SQL. It calls the repository for paged reads and the service for
writes; long-running work (import, export) hops to a worker thread.
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import DEFAULT_PAGE_SIZE
from app.models.people import Student
from app.repositories import student_repo
from app.ui.views.students.detail_view import StudentDetailDialog
from app.ui.views.students.form_dialog import StudentFormDialog
from app.ui.views.students.import_dialog import StudentImportDialog
from app.ui.widgets.paged_table import Column, PagedTableModel, PagedTableView
from app.workers.student_import import StudentExportWorker

log = logging.getLogger(__name__)


_STATUS_FILTERS = (
    ("All", None),
    ("Active", "active"),
    ("Transferred", "transferred"),
    ("Passed out", "passed_out"),
    ("Inactive", "inactive"),
)


def _full_name(s: Student) -> str:
    return " ".join(filter(None, [s.first_name, s.last_name]))


class StudentsListView(QWidget):
    """Top-level Students view, plugged into the main-window stack."""

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._export_worker: StudentExportWorker | None = None
        self._export_progress: QProgressDialog | None = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_toolbar())

        columns = [
            Column("Adm. No.", lambda s: s.admission_no),
            Column("Roll", lambda s: s.roll_no or ""),
            Column("Name", _full_name),
            Column("Gender", lambda s: s.gender or ""),
            Column("DOB", lambda s: s.dob or ""),
            Column("Father / Guardian", lambda s: s.father_name or s.guardian_name or ""),
            Column("Phone", lambda s: s.father_phone or s.guardian_phone or ""),
            Column("Status", lambda s: s.status),
        ]
        self._model = PagedTableModel(
            columns=columns,
            fetcher=self._fetch,
            counter=self._count,
            page_size=DEFAULT_PAGE_SIZE,
            parent=self,
        )
        self._table = PagedTableView(self._model, parent=self)
        self._table.rowActivated.connect(self._open_detail)
        self._table.rowSelected.connect(self._on_selection_changed)
        layout.addWidget(self._table, 1)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._open_new_form)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name or admission no.")
        self.search_edit.returnPressed.connect(self._on_filter_changed)
        layout.addWidget(QLabel("Search:"))
        layout.addWidget(self.search_edit, 1)

        self.status_combo = QComboBox()
        for label, value in _STATUS_FILTERS:
            self.status_combo.addItem(label, value)
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.status_combo)

        # Phase 3 will populate the class filter; keep a placeholder so layout is stable.
        self.class_combo = QComboBox()
        self.class_combo.addItem("All classes", None)
        self.class_combo.setEnabled(False)
        layout.addWidget(QLabel("Class:"))
        layout.addWidget(self.class_combo)

        layout.addSpacing(12)

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._open_new_form)
        layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._open_edit_form)
        self.edit_btn.setEnabled(False)
        layout.addWidget(self.edit_btn)

        self.view_btn = QPushButton("View")
        self.view_btn.clicked.connect(self._view_selected)
        self.view_btn.setEnabled(False)
        layout.addWidget(self.view_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setEnabled(False)
        layout.addWidget(self.delete_btn)

        self.import_btn = QPushButton("Import…")
        self.import_btn.clicked.connect(self._open_import)
        layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export…")
        self.export_btn.clicked.connect(self._export_filtered)
        layout.addWidget(self.export_btn)

        return bar

    # ------------------------------------------------------------------
    # Repo access
    # ------------------------------------------------------------------
    def _filters(self) -> dict[str, object | None]:
        return {
            "search": self.search_edit.text().strip() or None,
            "class_id": self.class_combo.currentData(),
            "status": self.status_combo.currentData(),
        }

    def _fetch(self, limit: int, offset: int) -> list[Student]:
        return student_repo.list_page(
            self._conn,
            limit=limit,
            offset=offset,
            **self._filters(),  # type: ignore[arg-type]
        )

    def _count(self) -> int:
        return student_repo.count(
            self._conn,
            **self._filters(),  # type: ignore[arg-type]
        )

    def refresh(self) -> None:
        self._model.refresh()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _on_filter_changed(self) -> None:
        self._model.set_page(1)
        self._model.refresh()

    def _on_selection_changed(self, row: object | None) -> None:
        has_row = row is not None
        self.edit_btn.setEnabled(has_row)
        self.view_btn.setEnabled(has_row)
        self.delete_btn.setEnabled(has_row)

    def _selected_student(self) -> Student | None:
        row = self._table.selected_row()
        return row if isinstance(row, Student) else None

    def _open_new_form(self) -> None:
        dlg = StudentFormDialog(self._conn, parent=self)
        if dlg.exec():
            self.refresh()

    def _open_edit_form(self) -> None:
        s = self._selected_student()
        if s is None:
            return
        dlg = StudentFormDialog(self._conn, student=s, parent=self)
        if dlg.exec():
            self.refresh()

    def _open_detail(self, row: object) -> None:
        if not isinstance(row, Student):
            return
        # Re-fetch the full record in case anything changed since the last list load.
        if row.id is not None:
            fresh = student_repo.get(self._conn, row.id)
            if fresh is not None:
                row = fresh
        StudentDetailDialog(row, parent=self).exec()

    def _view_selected(self) -> None:
        s = self._selected_student()
        if s is not None:
            self._open_detail(s)

    def _delete_selected(self) -> None:
        s = self._selected_student()
        if s is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete student",
            f"Permanently delete {_full_name(s)} ({s.admission_no})?\n\n"
            "Their attendance, marks, and fee records will also be deleted.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            student_repo.delete(self._conn, s.id)  # type: ignore[arg-type]
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Delete failed", str(exc))
            return
        self.refresh()

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def _open_import(self) -> None:
        dlg = StudentImportDialog(self._conn, parent=self)
        if dlg.exec() and dlg.imported_count:
            self.refresh()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_filtered(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export students", "students.xlsx", "Excel files (*.xlsx)"
        )
        if not path:
            return

        progress = QProgressDialog("Exporting…", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        self._export_progress = progress

        worker = StudentExportWorker(
            path,
            parent=self,
            **self._filters(),  # type: ignore[arg-type]
        )
        worker.error.connect(self._on_export_error)
        worker.finished_with_path.connect(self._on_export_done)
        worker.finished.connect(self._cleanup_export_worker)
        progress.canceled.connect(worker.cancel)
        self._export_worker = worker
        worker.start()

    def _on_export_error(self, message: str) -> None:
        if self._export_progress is not None:
            self._export_progress.cancel()
        QMessageBox.critical(self, "Export", message)

    def _on_export_done(self, path: str) -> None:
        if self._export_progress is not None:
            self._export_progress.cancel()
        QMessageBox.information(self, "Export", f"Saved to:\n{path}")

    def _cleanup_export_worker(self) -> None:
        if self._export_worker is not None:
            self._export_worker.deleteLater()
            self._export_worker = None
        if self._export_progress is not None:
            self._export_progress = None
