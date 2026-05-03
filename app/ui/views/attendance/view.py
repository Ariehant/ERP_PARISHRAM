"""Attendance tab container — Daily | Monthly | Reports."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.ui.views.attendance.daily_view import DailyAttendanceView
from app.ui.views.attendance.monthly_view import MonthlyAttendanceView
from app.ui.views.attendance.reports_view import AttendanceReportsView


class AttendanceView(QWidget):
    """Top-level attendance view with three tabs."""

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.daily_view = DailyAttendanceView(conn)
        self.monthly_view = MonthlyAttendanceView(conn)
        self.reports_view = AttendanceReportsView(conn)
        self.tabs.addTab(self.daily_view, "Daily")
        self.tabs.addTab(self.monthly_view, "Monthly")
        self.tabs.addTab(self.reports_view, "Reports")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        # Refresh the freshly-shown tab so changes from other modules
        # (added classes, edited rosters) are visible.
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
