"""Staff list view — search, role filter, active filter, CRUD buttons."""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import DEFAULT_PAGE_SIZE
from app.models.people import Staff
from app.repositories import staff_repo
from app.services import staff_service
from app.ui.views.masters.staff_form import StaffFormDialog
from app.ui.widgets.paged_table import Column, PagedTableModel, PagedTableView
from app.utils.errors import ValidationError

log = logging.getLogger(__name__)


_ROLE_FILTERS: tuple[tuple[str, str | None], ...] = (
    ("All roles", None),
    ("Teacher", "teacher"),
    ("Admin", "admin"),
    ("Accountant", "accountant"),
    ("Principal", "principal"),
)
_ACTIVE_FILTERS: tuple[tuple[str, bool | None], ...] = (
    ("All", None),
    ("Active", True),
    ("Inactive", False),
)


class StaffListView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_toolbar())

        columns = [
            Column("Emp. code", lambda s: s.emp_code),
            Column("Name", lambda s: s.name),
            Column("Role", lambda s: s.role),
            Column("Phone", lambda s: s.phone or ""),
            Column("Email", lambda s: s.email or ""),
            Column("Joining", lambda s: s.joining_date or ""),
            Column("Active", lambda s: "Yes" if s.is_active else "No"),
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

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name, code, role")
        self.search_edit.returnPressed.connect(self._on_filter_changed)
        layout.addWidget(QLabel("Search:"))
        layout.addWidget(self.search_edit, 1)

        self.role_combo = QComboBox()
        for label, value in _ROLE_FILTERS:
            self.role_combo.addItem(label, value)
        self.role_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(QLabel("Role:"))
        layout.addWidget(self.role_combo)

        self.active_combo = QComboBox()
        for label, value in _ACTIVE_FILTERS:
            self.active_combo.addItem(label, value)
        self.active_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.active_combo)

        layout.addSpacing(12)

        self.add_btn = QPushButton("Add")
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
    def _filters(self) -> dict[str, object | None]:
        return {
            "search": self.search_edit.text().strip() or None,
            "role": self.role_combo.currentData(),
            "is_active": self.active_combo.currentData(),
        }

    def _fetch(self, limit: int, offset: int) -> list[Staff]:
        return staff_repo.list_page(
            self._conn,
            limit=limit,
            offset=offset,
            **self._filters(),  # type: ignore[arg-type]
        )

    def _count(self) -> int:
        return staff_repo.count(self._conn, **self._filters())  # type: ignore[arg-type]

    def refresh(self) -> None:
        self._model.refresh()

    # ------------------------------------------------------------------
    def _on_filter_changed(self) -> None:
        self._model.set_page(1)
        self._model.refresh()

    def _on_selection_changed(self, row: object | None) -> None:
        has = row is not None
        self.edit_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _selected(self) -> Staff | None:
        row = self._table.selected_row()
        return row if isinstance(row, Staff) else None

    def _open_new(self) -> None:
        dlg = StaffFormDialog(self._conn, parent=self)
        if dlg.exec():
            self.refresh()

    def _open_edit_selected(self) -> None:
        s = self._selected()
        if s is None:
            return
        self._open_edit(s)

    def _open_edit(self, row: object) -> None:
        if not isinstance(row, Staff):
            return
        dlg = StaffFormDialog(self._conn, staff=row, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete_selected(self) -> None:
        s = self._selected()
        if s is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete staff",
            f"Delete {s.name} ({s.emp_code})?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            staff_service.delete_staff(self._conn, s.id)  # type: ignore[arg-type]
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot delete", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Delete failed", str(exc))
            return
        self.refresh()
