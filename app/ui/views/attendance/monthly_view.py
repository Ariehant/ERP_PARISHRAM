"""Monthly attendance view: student-by-day matrix for a class.

Read-only. Each cell shows the saved status letter (P/A/L/H) or blank,
colour-coded for quick scanning. The right edge has a percentage column
using the same convention as the service layer.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.reports.attendance_pdf import days_in_month
from app.repositories import attendance_repo, class_repo, school_repo
from app.services import attendance_service

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_STATUS_COLORS = {
    "P": QColor("#dff0d8"),
    "A": QColor("#f8d7da"),
    "L": QColor("#fff3cd"),
    "H": QColor("#e0e0e0"),
}


class MonthlyAttendanceView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._build_ui()
        self._populate_class_combo()
        today = date.today()
        self.month_combo.setCurrentIndex(today.month - 1)
        self.year_spin.setValue(today.year)
        self._reload()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_toolbar())

        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        self.class_combo.currentIndexChanged.connect(self._reload)
        layout.addWidget(self.class_combo)

        layout.addWidget(QLabel("Month:"))
        self.month_combo = QComboBox()
        for name in _MONTHS:
            self.month_combo.addItem(name)
        self.month_combo.currentIndexChanged.connect(self._reload)
        layout.addWidget(self.month_combo)

        layout.addWidget(QLabel("Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(QDate.currentDate().year())
        self.year_spin.valueChanged.connect(self._reload)
        layout.addWidget(self.year_spin)

        layout.addStretch(1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._reload)
        layout.addWidget(self.refresh_btn)
        return bar

    # ------------------------------------------------------------------
    def _populate_class_combo(self) -> None:
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        active = school_repo.get_active_academic_year(self._conn)
        if active is not None and active.id is not None:
            for cls in class_repo.list_for_year(self._conn, active.id):
                self.class_combo.addItem(f"{cls.name}-{cls.section}", cls.id)
        if self.class_combo.count() == 0:
            self.class_combo.addItem("(no classes)", None)
            self.class_combo.setEnabled(False)
        self.class_combo.blockSignals(False)

    def refresh(self) -> None:
        previous = self.class_combo.currentData()
        self._populate_class_combo()
        if previous is not None:
            idx = self.class_combo.findData(previous)
            if idx >= 0:
                self.class_combo.setCurrentIndex(idx)
        self._reload()

    def _reload(self) -> None:
        class_id = self.class_combo.currentData()
        month = self.month_combo.currentIndex() + 1
        year = self.year_spin.value()

        if class_id is None:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.summary_label.setText("Pick a class to view the month.")
            return

        days = days_in_month(year, month)
        # Columns: Roll, Name, day1..dayN, %
        headers = ["Roll", "Name", *[str(d) for d in range(1, days + 1)], "%"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        summaries = attendance_service.class_summary(self._conn, class_id, year, month)
        rows = attendance_repo.list_monthly_for_class(self._conn, class_id, year, month)
        # Build {(student_id, day): status}
        cell_status: dict[tuple[int, int], str] = {}
        for student_id, date_iso, status in rows:
            day = int(date_iso[8:10])
            cell_status[(student_id, day)] = status

        self.table.setRowCount(len(summaries))
        for r, summary in enumerate(summaries):
            self.table.setItem(r, 0, QTableWidgetItem(str(summary.roll_no or "")))
            self.table.setItem(r, 1, QTableWidgetItem(summary.display_name))
            for d in range(1, days + 1):
                status = cell_status.get((summary.student_id, d), "")
                item = QTableWidgetItem(status)
                item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                if status in _STATUS_COLORS:
                    item.setBackground(QBrush(_STATUS_COLORS[status]))
                self.table.setItem(r, 1 + d, item)
            pct_text = f"{summary.percentage:.1f}" if summary.effective_total > 0 else "—"
            pct_item = QTableWidgetItem(pct_text)
            pct_item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
            self.table.setItem(r, len(headers) - 1, pct_item)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        for i in range(2, len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.summary_label.setText(
            f"{len(summaries)} active student(s) in {_MONTHS[month - 1]} {year}. "
            "P / A / L / H legend: green / red / yellow / grey."
        )
