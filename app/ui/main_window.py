"""Main window shell: left sidebar + QStackedWidget content area + status bar.

Module views are lazy-loaded the first time the user opens them — none of the
view modules are imported at app start, so PySide6 / repository / service
imports stay minimal until needed.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION, DB_PATH
from app.models.school import AcademicYear, School
from app.models.user import User
from app.repositories import school_repo


@dataclass(frozen=True, slots=True)
class _Module:
    key: str
    label: str
    phase: int


_MODULES: tuple[_Module, ...] = (
    _Module("dashboard", "Dashboard", 1),
    _Module("students", "Students", 2),
    _Module("masters", "Classes & Staff", 3),
    _Module("attendance", "Attendance", 4),
    _Module("exams", "Exams & Marks", 5),
    _Module("fees", "Fees", 6),
    _Module("reports", "Reports", 7),
    _Module("settings", "Settings", 8),
)


def _build_students_view(conn: sqlite3.Connection) -> QWidget:
    # Imported lazily so the students module (and pyqtgraph etc. in later
    # phases) only load when the user opens the view.
    from app.ui.views.students.list_view import StudentsListView

    return StudentsListView(conn)


def _build_masters_view(conn: sqlite3.Connection) -> QWidget:
    from app.ui.views.masters.view import MastersView

    return MastersView(conn)


def _placeholder(text: str) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    font = label.font()
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    label.setStyleSheet("color: #666;")
    layout.addWidget(label)
    return page


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection, user: User) -> None:
        super().__init__()
        self._conn = conn
        self._user = user

        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.resize(1024, 680)

        self._build_central()
        self._build_status_bar()
        self._install_shortcuts()

    # ------------------------------------------------------------------
    def _build_central(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet(
            "QListWidget#sidebar { background: #f4f4f4; border: none; }"
            "QListWidget#sidebar::item { padding: 12px 16px; }"
            "QListWidget#sidebar::item:selected { background: #1976d2; color: white; }"
        )
        for module in _MODULES:
            item = QListWidgetItem(module.label)
            item.setData(Qt.ItemDataRole.UserRole, module.key)
            self.sidebar.addItem(item)
        layout.addWidget(self.sidebar)

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Content stack — populated lazily.
        self.stack = QStackedWidget()
        self._loaded: dict[int, QWidget] = {}
        # Each module gets a placeholder *now*; the real view is built the
        # first time the sidebar entry is selected. Keeps cold start fast.
        self._builders: dict[int, Callable[[sqlite3.Connection], QWidget]] = {
            1: _build_students_view,
            2: _build_masters_view,
        }
        for i, module in enumerate(_MODULES):
            if module.phase == 1:
                page = _placeholder(
                    f"Welcome, {self._user.full_name or self._user.username}.\n\n"
                    "Use the sidebar to open a module."
                )
                self._loaded[i] = page
            else:
                page = _placeholder(f"{module.label} — coming in Phase {module.phase}.")
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        self.sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        self.sidebar.setCurrentRow(0)

    # ------------------------------------------------------------------
    def _on_sidebar_changed(self, index: int) -> None:
        if index < 0:
            return
        # Lazy-instantiate on first visit.
        if index not in self._loaded and index in self._builders:
            real_page = self._builders[index](self._conn)
            placeholder = self.stack.widget(index)
            self.stack.removeWidget(placeholder)
            placeholder.deleteLater()
            self.stack.insertWidget(index, real_page)
            self._loaded[index] = real_page
        self.stack.setCurrentIndex(index)

    # ------------------------------------------------------------------
    def _build_status_bar(self) -> None:
        status = QStatusBar()
        self.setStatusBar(status)

        active_year = school_repo.get_active_academic_year(self._conn)
        school = school_repo.get_first_school(self._conn)
        status.addWidget(QLabel(self._school_label(school)))
        status.addWidget(QLabel(" | "))
        status.addWidget(QLabel(f"User: {self._user.username} ({self._user.role})"))
        status.addWidget(QLabel(" | "))
        status.addWidget(QLabel(self._year_label(active_year)))

        # Right-aligned: DB path
        status.addPermanentWidget(QLabel(f"DB: {DB_PATH}"))

    @staticmethod
    def _school_label(school: School | None) -> str:
        return school.name if school else "(no school configured)"

    @staticmethod
    def _year_label(year: AcademicYear | None) -> str:
        return f"Year: {year.label}" if year else "Year: —"

    # ------------------------------------------------------------------
    def _install_shortcuts(self) -> None:
        # Esc closes top-level dialogs only — wired here to be discoverable.
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)
