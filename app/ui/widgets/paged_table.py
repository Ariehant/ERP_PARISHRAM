"""Reusable paged-table widgets.

``PagedTableModel`` holds *one page* at a time (default 50 rows). It calls
out to two callables:

- ``fetcher(limit, offset) -> list[T]``       — returns the rows for a page.
- ``counter() -> int``                        — returns the total row count
                                                under the current filter.

UI code (e.g. the StudentsListView) wires these to a repository.

``PagedTableView`` wraps a ``QTableView`` plus a pagination footer
(Prev / Page X of Y / Next + a "Showing rows…" label).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class Column:
    """Description of one displayed column.

    ``getter`` takes a row object and returns the cell value (any type that
    ``str(...)`` produces a sensible string for). ``alignment`` is a Qt flag.
    """

    title: str
    getter: Callable[[Any], Any]
    alignment: int = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


class PagedTableModel(QAbstractTableModel):
    """A table model that holds at most ``page_size`` rows in memory."""

    pageChanged = Signal(int, int)  # current_page (1-indexed), total_pages

    def __init__(
        self,
        columns: list[Column],
        fetcher: Callable[[int, int], list[Any]],
        counter: Callable[[], int],
        page_size: int = 50,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._columns = list(columns)
        self._fetcher = fetcher
        self._counter = counter
        self._page_size = max(1, int(page_size))
        self._page = 1  # 1-indexed
        self._total_rows = 0
        self._rows: list[Any] = []

    # ------------------------------------------------------------------
    # Qt model API
    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = self._columns[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            value = col.getter(row)
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return col.alignment
        if role == Qt.ItemDataRole.UserRole:
            return row
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._columns[section].title
        return section + 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def page_size(self) -> int:
        return self._page_size

    @property
    def page(self) -> int:
        return self._page

    @property
    def total_rows(self) -> int:
        return self._total_rows

    @property
    def total_pages(self) -> int:
        if self._total_rows == 0:
            return 1
        return max(1, math.ceil(self._total_rows / self._page_size))

    def row_at(self, index: QModelIndex) -> Any | None:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        return self._rows[index.row()]

    def refresh(self) -> None:
        """Re-count + re-fetch the current page. Snaps page into range."""
        self._total_rows = int(self._counter())
        if self._page > self.total_pages:
            self._page = self.total_pages
        offset = (self._page - 1) * self._page_size

        self.beginResetModel()
        self._rows = list(self._fetcher(self._page_size, offset))
        self.endResetModel()
        self.pageChanged.emit(self._page, self.total_pages)

    def set_page(self, page: int) -> None:
        page = max(1, min(int(page), self.total_pages))
        if page == self._page:
            return
        self._page = page
        self.refresh()

    def next_page(self) -> None:
        self.set_page(self._page + 1)

    def prev_page(self) -> None:
        self.set_page(self._page - 1)


class PagedTableView(QWidget):
    """``QTableView`` + pagination footer wired to a ``PagedTableModel``."""

    rowActivated = Signal(object)  # double-clicked row payload (any)
    rowSelected = Signal(object)  # currently selected row payload, or None

    def __init__(self, model: PagedTableModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.table = QTableView()
        self.table.setModel(model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.selectionModel().currentRowChanged.connect(self._on_current_changed)
        layout.addWidget(self.table, 1)

        # Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        self.summary_label = QLabel("")
        font = self.summary_label.font()
        font.setPointSize(font.pointSize() - 1)
        font.setItalic(True)
        self.summary_label.setFont(font)

        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(model.prev_page)
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(model.next_page)
        self.page_label = QLabel("Page 1 of 1")
        page_font = QFont(self.page_label.font())
        page_font.setBold(True)
        self.page_label.setFont(page_font)

        footer.addWidget(self.summary_label, 1)
        footer.addWidget(self.prev_btn)
        footer.addWidget(self.page_label)
        footer.addWidget(self.next_btn)
        layout.addLayout(footer)

        model.pageChanged.connect(self._on_page_changed)

    # ------------------------------------------------------------------
    @property
    def model(self) -> PagedTableModel:  # type: ignore[override]
        return self._model

    def refresh(self) -> None:
        self._model.refresh()

    def selected_row(self) -> Any | None:
        idx = self.table.currentIndex()
        return self._model.row_at(idx) if idx.isValid() else None

    # ------------------------------------------------------------------
    def _on_page_changed(self, page: int, total: int) -> None:
        self.page_label.setText(f"Page {page} of {total}")
        self.prev_btn.setEnabled(page > 1)
        self.next_btn.setEnabled(page < total)
        size = self._model.page_size
        total_rows = self._model.total_rows
        if total_rows == 0:
            self.summary_label.setText("No rows.")
        else:
            start = (page - 1) * size + 1
            end = min(page * size, total_rows)
            self.summary_label.setText(f"Showing {start}-{end} of {total_rows} rows.")

    def _on_double_clicked(self, index: QModelIndex) -> None:
        row = self._model.row_at(index)
        if row is not None:
            self.rowActivated.emit(row)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        self.rowSelected.emit(self._model.row_at(current))
