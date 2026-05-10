"""Add/edit an exam."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.exam import Exam
from app.repositories import school_repo
from app.services import exam_service
from app.utils.errors import ValidationError


class ExamFormDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        exam: Exam | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._exam = exam
        self.saved_id: int | None = None

        self.setWindowTitle("Edit exam" if exam else "Add exam")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Mid-term I")
        self.exam_type = QComboBox()
        self.exam_type.addItem("(unspecified)", None)
        for t in exam_service.VALID_EXAM_TYPES:
            self.exam_type.addItem(t, t)
        self.year_combo = QComboBox()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate())
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        self.weightage = QSpinBox()
        self.weightage.setRange(1, 1000)
        self.weightage.setValue(100)

        form.addRow("Name *", self.name)
        form.addRow("Type", self.exam_type)
        form.addRow("Academic year *", self.year_combo)
        form.addRow("Start date", self.start_date)
        form.addRow("End date", self.end_date)
        form.addRow("Weightage", self.weightage)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_years()
        if exam is not None:
            self._load_from(exam)

    def _populate_years(self) -> None:
        years = school_repo.list_academic_years(self._conn)
        active = school_repo.get_active_academic_year(self._conn)
        for y in years:
            label = f"{y.label}{' (active)' if y.is_active else ''}"
            self.year_combo.addItem(label, y.id)
        if active is not None:
            idx = self.year_combo.findData(active.id)
            if idx >= 0:
                self.year_combo.setCurrentIndex(idx)

    def _load_from(self, e: Exam) -> None:
        self.name.setText(e.name)
        if e.exam_type:
            idx = self.exam_type.findData(e.exam_type)
            if idx >= 0:
                self.exam_type.setCurrentIndex(idx)
        idx = self.year_combo.findData(e.academic_year_id)
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        if e.start_date:
            self.start_date.setDate(QDate.fromString(e.start_date, "yyyy-MM-dd"))
        if e.end_date:
            self.end_date.setDate(QDate.fromString(e.end_date, "yyyy-MM-dd"))
        self.weightage.setValue(e.weightage or 100)

    def _gather(self) -> Exam:
        return Exam(
            id=self._exam.id if self._exam else None,
            name=self.name.text(),
            academic_year_id=self.year_combo.currentData() or 0,
            exam_type=self.exam_type.currentData(),
            start_date=self.start_date.date().toString("yyyy-MM-dd"),
            end_date=self.end_date.date().toString("yyyy-MM-dd"),
            weightage=self.weightage.value(),
        )

    def _on_save(self) -> None:
        exam = self._gather()
        try:
            if exam.id is None:
                self.saved_id = exam_service.create_exam(self._conn, exam)
            else:
                exam_service.update_exam(self._conn, exam)
                self.saved_id = exam.id
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.accept()
