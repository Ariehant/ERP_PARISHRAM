"""Exams tab container -- Exams | Marks Entry | Grade Scale."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.ui.views.exams.exam_list import ExamListView
from app.ui.views.exams.grade_scale_view import GradeScaleView
from app.ui.views.exams.marks_entry import MarksEntryView


class ExamsView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.exam_list_view = ExamListView(conn)
        self.marks_entry_view = MarksEntryView(conn)
        self.grade_scale_view = GradeScaleView(conn)
        self.tabs.addTab(self.exam_list_view, "Exams")
        self.tabs.addTab(self.marks_entry_view, "Marks entry")
        self.tabs.addTab(self.grade_scale_view, "Grade scale")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
