"""Exam list scoped to the active year."""

from __future__ import annotations

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
from app.models.exam import Exam
from app.repositories import exam_repo, school_repo
from app.services import exam_service
from app.ui.views.exams.exam_form import ExamFormDialog
from app.ui.widgets.paged_table import Column, PagedTableModel, PagedTableView
from app.utils.errors import ValidationError


class ExamListView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._build_ui()
        self._populate_year_combo()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_toolbar())

        cols = [
            Column("Name", lambda e: e.name),
            Column("Type", lambda e: e.exam_type or ""),
            Column("Start", lambda e: e.start_date or ""),
            Column("End", lambda e: e.end_date or ""),
            Column("Weight", lambda e: e.weightage),
            Column("Marks recorded", self._marks_count),
        ]
        self._model = PagedTableModel(
            columns=cols,
            fetcher=self._fetch,
            counter=self._count,
            page_size=DEFAULT_PAGE_SIZE,
            parent=self,
        )
        self._table = PagedTableView(self._model, parent=self)
        self._table.rowSelected.connect(self._on_select)
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

        self.add_btn = QPushButton("Add exam")
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

    def _selected_year_id(self) -> int | None:
        return self.year_combo.currentData()

    def _fetch(self, limit: int, offset: int) -> list[Exam]:
        yid = self._selected_year_id()
        if yid is None:
            return []
        return exam_repo.list_for_year(self._conn, yid)[offset : offset + limit]

    def _count(self) -> int:
        yid = self._selected_year_id()
        if yid is None:
            return 0
        return len(exam_repo.list_for_year(self._conn, yid))

    def _marks_count(self, e: Exam) -> int:
        if e.id is None:
            return 0
        return exam_repo.count_marks_for_exam(self._conn, e.id)

    def refresh(self) -> None:
        self._model.refresh()

    def _on_filter_changed(self) -> None:
        self._model.set_page(1)
        self._model.refresh()

    def _on_select(self, row: object | None) -> None:
        has = row is not None
        self.edit_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _selected(self) -> Exam | None:
        row = self._table.selected_row()
        return row if isinstance(row, Exam) else None

    def _open_new(self) -> None:
        dlg = ExamFormDialog(self._conn, parent=self)
        if dlg.exec():
            self.refresh()

    def _open_edit(self, row: object) -> None:
        if not isinstance(row, Exam):
            return
        dlg = ExamFormDialog(self._conn, exam=row, parent=self)
        if dlg.exec():
            self.refresh()

    def _open_edit_selected(self) -> None:
        e = self._selected()
        if e is not None:
            self._open_edit(e)

    def _delete_selected(self) -> None:
        e = self._selected()
        if e is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete exam",
            f"Delete exam {e.name!r}? Marks recorded for this exam will also be removed.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            exam_service.delete_exam(self._conn, e.id)  # type: ignore[arg-type]
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot delete", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Delete failed", str(exc))
            return
        self.refresh()
