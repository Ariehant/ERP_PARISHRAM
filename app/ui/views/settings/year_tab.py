"""Academic-year tab -- list, add, set active."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.connection import transaction
from app.models.school import AcademicYear
from app.repositories import school_repo


class _AddYearDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add academic year")
        self.params: AcademicYear | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.label = QLineEdit()
        self.label.setPlaceholderText("e.g. 2026-27")
        today = QDate.currentDate()
        self.start = QDateEdit(QDate(today.year(), 4, 1))
        self.start.setCalendarPopup(True)
        self.start.setDisplayFormat("yyyy-MM-dd")
        self.end = QDateEdit(QDate(today.year() + 1, 3, 31))
        self.end.setCalendarPopup(True)
        self.end.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Label *", self.label)
        form.addRow("Start date *", self.start)
        form.addRow("End date *", self.end)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        label = self.label.text().strip()
        if not label:
            QMessageBox.warning(self, "Missing", "Enter a label.")
            return
        start = self.start.date().toString("yyyy-MM-dd")
        end = self.end.date().toString("yyyy-MM-dd")
        if start >= end:
            QMessageBox.warning(self, "Bad dates", "Start must be before end.")
            return
        self.params = AcademicYear(
            id=None, label=label, start_date=start, end_date=end, is_active=False
        )
        self.accept()


class YearTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._build_ui()
        self._reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(
            QLabel(
                "Set the active academic year. Other modules use the active "
                "year to scope their data (classes, exams, fees, attendance)."
            )
        )

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Label", "Start", "End", "Active"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.add_btn = QPushButton("Add year...")
        self.add_btn.clicked.connect(self._add)
        actions.addWidget(self.add_btn)
        actions.addStretch(1)
        self.activate_btn = QPushButton("Set selected as active")
        self.activate_btn.clicked.connect(self._activate)
        actions.addWidget(self.activate_btn)
        layout.addLayout(actions)

    def refresh(self) -> None:
        self._reload()

    def _reload(self) -> None:
        years = school_repo.list_academic_years(self._conn)
        self.table.setRowCount(len(years))
        for r, y in enumerate(years):
            label_item = QTableWidgetItem(y.label)
            label_item.setData(0x100, y.id)  # Qt.UserRole
            self.table.setItem(r, 0, label_item)
            self.table.setItem(r, 1, QTableWidgetItem(y.start_date))
            self.table.setItem(r, 2, QTableWidgetItem(y.end_date))
            self.table.setItem(r, 3, QTableWidgetItem("Yes" if y.is_active else "No"))

    def _selected_year_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(0x100) if item else None

    def _add(self) -> None:
        dlg = _AddYearDialog(parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted or dlg.params is None:
            return
        try:
            with transaction(self._conn):
                school_repo.create_academic_year(self._conn, dlg.params)
        except Exception as exc:
            QMessageBox.critical(self, "Cannot add", str(exc))
            return
        self._reload()

    def _activate(self) -> None:
        yid = self._selected_year_id()
        if yid is None:
            QMessageBox.information(self, "Select first", "Pick a year in the table.")
            return
        try:
            with transaction(self._conn):
                school_repo.set_active_academic_year(self._conn, yid)
        except Exception as exc:
            QMessageBox.critical(self, "Cannot activate", str(exc))
            return
        QMessageBox.information(
            self,
            "Active year switched",
            "Open each module's tab to refresh the year-scoped data.",
        )
        self._reload()
