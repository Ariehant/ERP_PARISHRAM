"""Attendance reports — generate the three PDFs off-thread."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.repositories import class_repo, school_repo
from app.workers.attendance_pdf import AttendancePDFWorker

log = logging.getLogger(__name__)

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


class AttendanceReportsView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._worker: AttendancePDFWorker | None = None
        self._progress: QProgressDialog | None = None

        self._build_ui()
        self._populate_class_combo()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Class picker (shared by all reports)
        top = QHBoxLayout()
        top.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        top.addWidget(self.class_combo)
        top.addStretch(1)
        layout.addLayout(top)

        layout.addWidget(self._daily_box())
        layout.addWidget(self._monthly_box())
        layout.addWidget(self._low_box())
        layout.addStretch(1)

    def _daily_box(self) -> QGroupBox:
        box = QGroupBox("Daily attendance register")
        grid = QGridLayout(box)
        grid.addWidget(QLabel("Date:"), 0, 0)
        self.daily_date = QDateEdit(QDate.currentDate())
        self.daily_date.setCalendarPopup(True)
        self.daily_date.setDisplayFormat("yyyy-MM-dd")
        grid.addWidget(self.daily_date, 0, 1)
        btn = QPushButton("Generate PDF…")
        btn.clicked.connect(self._on_daily)
        grid.addWidget(btn, 0, 2, alignment=Qt.AlignmentFlag.AlignRight)
        grid.setColumnStretch(1, 1)
        return box

    def _monthly_box(self) -> QGroupBox:
        box = QGroupBox("Monthly attendance summary")
        grid = QGridLayout(box)
        today = date.today()
        grid.addWidget(QLabel("Month:"), 0, 0)
        self.monthly_month = QComboBox()
        for name in _MONTHS:
            self.monthly_month.addItem(name)
        self.monthly_month.setCurrentIndex(today.month - 1)
        grid.addWidget(self.monthly_month, 0, 1)
        grid.addWidget(QLabel("Year:"), 0, 2)
        self.monthly_year = QSpinBox()
        self.monthly_year.setRange(2000, 2100)
        self.monthly_year.setValue(today.year)
        grid.addWidget(self.monthly_year, 0, 3)
        btn = QPushButton("Generate PDF…")
        btn.clicked.connect(self._on_monthly)
        grid.addWidget(btn, 0, 4, alignment=Qt.AlignmentFlag.AlignRight)
        grid.setColumnStretch(1, 1)
        return box

    def _low_box(self) -> QGroupBox:
        box = QGroupBox("Low attendance list")
        grid = QGridLayout(box)
        today = date.today()
        grid.addWidget(QLabel("Month:"), 0, 0)
        self.low_month = QComboBox()
        for name in _MONTHS:
            self.low_month.addItem(name)
        self.low_month.setCurrentIndex(today.month - 1)
        grid.addWidget(self.low_month, 0, 1)
        grid.addWidget(QLabel("Year:"), 0, 2)
        self.low_year = QSpinBox()
        self.low_year.setRange(2000, 2100)
        self.low_year.setValue(today.year)
        grid.addWidget(self.low_year, 0, 3)
        grid.addWidget(QLabel("Threshold %:"), 0, 4)
        self.low_threshold = QDoubleSpinBox()
        self.low_threshold.setRange(1.0, 100.0)
        self.low_threshold.setValue(75.0)
        self.low_threshold.setDecimals(1)
        grid.addWidget(self.low_threshold, 0, 5)
        btn = QPushButton("Generate PDF…")
        btn.clicked.connect(self._on_low)
        grid.addWidget(btn, 0, 6, alignment=Qt.AlignmentFlag.AlignRight)
        grid.setColumnStretch(1, 1)
        return box

    # ------------------------------------------------------------------
    def _populate_class_combo(self) -> None:
        previous = self.class_combo.currentData()
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        active = school_repo.get_active_academic_year(self._conn)
        if active is not None and active.id is not None:
            for cls in class_repo.list_for_year(self._conn, active.id):
                self.class_combo.addItem(f"{cls.name}-{cls.section}", cls.id)
        if self.class_combo.count() == 0:
            self.class_combo.addItem("(no classes)", None)
        if previous is not None:
            idx = self.class_combo.findData(previous)
            if idx >= 0:
                self.class_combo.setCurrentIndex(idx)
        self.class_combo.blockSignals(False)

    def refresh(self) -> None:
        self._populate_class_combo()

    # ------------------------------------------------------------------
    def _ensure_class(self) -> int | None:
        cid = self.class_combo.currentData()
        if cid is None:
            QMessageBox.warning(self, "Pick a class", "Please pick a class first.")
            return None
        return cid

    def _ask_save_path(self, default_name: str) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF",
            default_name,
            "PDF files (*.pdf)",
        )
        return Path(path) if path else None

    def _on_daily(self) -> None:
        cid = self._ensure_class()
        if cid is None:
            return
        date_iso = self.daily_date.date().toString("yyyy-MM-dd")
        path = self._ask_save_path(f"daily_attendance_{date_iso}.pdf")
        if path is None:
            return
        self._spawn_worker(path, "daily", {"class_id": cid, "date_iso": date_iso})

    def _on_monthly(self) -> None:
        cid = self._ensure_class()
        if cid is None:
            return
        month = self.monthly_month.currentIndex() + 1
        year = self.monthly_year.value()
        path = self._ask_save_path(f"monthly_attendance_{year:04d}-{month:02d}.pdf")
        if path is None:
            return
        self._spawn_worker(path, "monthly", {"class_id": cid, "year": year, "month": month})

    def _on_low(self) -> None:
        cid = self._ensure_class()
        if cid is None:
            return
        month = self.low_month.currentIndex() + 1
        year = self.low_year.value()
        threshold = float(self.low_threshold.value())
        path = self._ask_save_path(
            f"low_attendance_{year:04d}-{month:02d}_below_{int(threshold)}.pdf"
        )
        if path is None:
            return
        self._spawn_worker(
            path,
            "low",
            {"class_id": cid, "year": year, "month": month, "threshold": threshold},
        )

    # ------------------------------------------------------------------
    def _spawn_worker(self, target: Path, kind: str, params: dict) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Busy",
                "A PDF is already being generated. Please wait.",
            )
            return
        progress = QProgressDialog("Generating PDF…", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        self._progress = progress

        worker = AttendancePDFWorker(target, kind, params, parent=self)
        worker.error.connect(self._on_worker_error)
        worker.finished_with_path.connect(self._on_worker_done)
        worker.finished.connect(self._cleanup_worker)
        self._worker = worker
        worker.start()

    def _on_worker_error(self, message: str) -> None:
        if self._progress is not None:
            self._progress.cancel()
        QMessageBox.critical(self, "PDF failed", message)

    def _on_worker_done(self, path: str) -> None:
        if self._progress is not None:
            self._progress.cancel()
        QMessageBox.information(self, "PDF saved", f"Saved to:\n{path}")

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self._progress = None
