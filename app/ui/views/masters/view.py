"""Masters tab container — Classes & Subjects | Staff."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.ui.views.masters.class_list import ClassListView
from app.ui.views.masters.staff_list import StaffListView


class MastersView(QWidget):
    """Top-level wrapper that hosts the Classes and Staff list views."""

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.classes_view = ClassListView(conn)
        self.staff_view = StaffListView(conn)
        self.tabs.addTab(self.classes_view, "Classes && Subjects")
        self.tabs.addTab(self.staff_view, "Staff")
        # Whenever the user switches back to the classes tab, refresh — the
        # teacher dropdown depends on staff edits made in the other tab.
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.classes_view:
            self.classes_view.refresh()
