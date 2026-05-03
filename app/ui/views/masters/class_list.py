"""Class list view, scoped to the active academic year by default."""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import DEFAULT_PAGE_SIZE
from app.models.structure import Class
from app.repositories import class_repo, school_repo, staff_repo
from app.services import class_service
from app.ui.views.masters.class_form import ClassFormDialog
from app.ui.widgets.paged_table import Column, PagedTableModel, PagedTableView
from app.utils.errors import ValidationError

log = logging.getLogger(__name__)


class ClassListView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._teacher_names: dict[int, str] = {}
        self._build_ui()
        self._populate_year_combo()
        self._refresh_teacher_cache()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_toolbar())

        columns = [
            Column("Class", lambda c: c.name),
            Column("Section", lambda c: c.section),
            Column("Class teacher", self._teacher_label),
            Column("Subjects", self._subject_count),
            Column("Students", self._student_count),
        ]
        self._model = PagedTableModel(
            columns=columns,
            fetcher=self._fetch,
            counter=self._count,
            page_size=DEFAULT_PAGE_SIZE,
            parent=self,
        )
        self._table = PagedTableView(self._model, parent=self)
        self._table.rowSelected.connect(self._on_selection_changed)
        self._table.rowActivated.connect(self._open_edit)
        layout.addWidget(self._table, 1)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(QLabel("Academic year:"))
        layout.addWidget(self.year_combo)
        layout.addStretch(1)

        self.add_btn = QPushButton("Add class")
        self.add_btn.clicked.connect(self._open_new)
        layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._open_edit_selected)
        self.edit_btn.setEnabled(False)
        layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setEnabled(False)
        layout.addWidget(self.delete_btn)

        return bar

    # ------------------------------------------------------------------
    def _populate_year_combo(self) -> None:
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        years = school_repo.list_academic_years(self._conn)
        active = school_repo.get_active_academic_year(self._conn)
        for y in years:
            label = f"{y.label}{' (active)' if y.is_active else ''}"
            self.year_combo.addItem(label, y.id)
        if active is not None:
            idx = self.year_combo.findData(active.id)
            if idx >= 0:
                self.year_combo.setCurrentIndex(idx)
        self.year_combo.blockSignals(False)

    def _refresh_teacher_cache(self) -> None:
        self._teacher_names = {
            t.id: t.name for t in staff_repo.list_active_teachers(self._conn) if t.id is not None
        }

    def _selected_year_id(self) -> int | None:
        return self.year_combo.currentData()

    def _fetch(self, limit: int, offset: int) -> list[Class]:
        year_id = self._selected_year_id()
        if year_id is None:
            return []
        rows = class_repo.list_for_year(self._conn, year_id)
        return rows[offset : offset + limit]

    def _count(self) -> int:
        year_id = self._selected_year_id()
        if year_id is None:
            return 0
        return class_repo.count_for_year(self._conn, year_id)

    def _teacher_label(self, cls: Class) -> str:
        if cls.class_teacher_id is None:
            return "(unassigned)"
        return self._teacher_names.get(cls.class_teacher_id, "(unknown)")

    def _subject_count(self, cls: Class) -> int:
        if cls.id is None:
            return 0
        return len(class_repo.list_subjects_for_class(self._conn, cls.id))

    def _student_count(self, cls: Class) -> int:
        if cls.id is None:
            return 0
        return class_repo.count_students_in_class(self._conn, cls.id)

    def refresh(self) -> None:
        self._refresh_teacher_cache()
        self._model.refresh()

    # ------------------------------------------------------------------
    def _on_filter_changed(self) -> None:
        self._model.set_page(1)
        self._model.refresh()

    def _on_selection_changed(self, row: object | None) -> None:
        has = row is not None
        self.edit_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _selected(self) -> Class | None:
        row = self._table.selected_row()
        return row if isinstance(row, Class) else None

    def _open_new(self) -> None:
        dlg = ClassFormDialog(self._conn, parent=self)
        if dlg.exec():
            self.refresh()

    def _open_edit_selected(self) -> None:
        cls = self._selected()
        if cls is None:
            return
        self._open_edit(cls)

    def _open_edit(self, row: object) -> None:
        if not isinstance(row, Class):
            return
        dlg = ClassFormDialog(self._conn, cls=row, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete_selected(self) -> None:
        cls = self._selected()
        if cls is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete class",
            f"Delete class {cls.name}-{cls.section}?\n\n"
            "Subjects will be removed too. Students must be reassigned first.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            class_service.delete_class(self._conn, cls.id)  # type: ignore[arg-type]
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot delete", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Delete failed", str(exc))
            return
        self.refresh()
