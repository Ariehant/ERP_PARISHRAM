"""Settings tab container."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.ui.views.exams.grade_scale_view import GradeScaleView
from app.ui.views.settings.audit_tab import AuditLogTab
from app.ui.views.settings.backup_tab import BackupTab
from app.ui.views.settings.school_tab import SchoolTab
from app.ui.views.settings.users_tab import UsersTab
from app.ui.views.settings.year_tab import YearTab


class SettingsView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.school_tab = SchoolTab(conn)
        self.backup_tab = BackupTab(conn)
        self.year_tab = YearTab(conn)
        self.users_tab = UsersTab(conn)
        self.grade_scale_tab = GradeScaleView(conn)
        self.audit_tab = AuditLogTab(conn)
        self.tabs.addTab(self.school_tab, "School")
        self.tabs.addTab(self.backup_tab, "Backup && restore")
        self.tabs.addTab(self.year_tab, "Academic year")
        self.tabs.addTab(self.users_tab, "Users")
        self.tabs.addTab(self.grade_scale_tab, "Grade scale")
        self.tabs.addTab(self.audit_tab, "Audit log")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
