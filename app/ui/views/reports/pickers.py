"""Small picker dialogs for the reports-hub buttons.

Each dialog returns a dict of params consumable by the
``ReportsPDFWorker``.
"""

from __future__ import annotations

import sqlite3
from datetime import date as date_cls

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.repositories import class_repo, exam_repo, school_repo, student_repo


def _populate_classes(combo: QComboBox, conn: sqlite3.Connection) -> None:
    active = school_repo.get_active_academic_year(conn)
    if active is not None and active.id is not None:
        for cls in class_repo.list_for_year(conn, active.id):
            combo.addItem(f"{cls.name}-{cls.section}", cls.id)
    if combo.count() == 0:
        combo.addItem("(no classes)", None)


def _populate_exams(combo: QComboBox, conn: sqlite3.Connection) -> None:
    active = school_repo.get_active_academic_year(conn)
    if active is not None and active.id is not None:
        for e in exam_repo.list_for_year(conn, active.id):
            combo.addItem(e.name + (f" ({e.exam_type})" if e.exam_type else ""), e.id)
    if combo.count() == 0:
        combo.addItem("(no exams)", None)


def _populate_years(combo: QComboBox, conn: sqlite3.Connection) -> None:
    active = school_repo.get_active_academic_year(conn)
    for y in school_repo.list_academic_years(conn):
        label = f"{y.label}{' (active)' if y.is_active else ''}"
        combo.addItem(label, y.id)
    if active is not None:
        idx = combo.findData(active.id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    if combo.count() == 0:
        combo.addItem("(no years)", None)


class _BaseDialog(QDialog):
    """Tiny shared base: exposes ``params: dict`` on accept."""

    def __init__(self, conn: sqlite3.Connection, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self.params: dict = {}
        self.setWindowTitle(title)
        self.setMinimumWidth(360)


class StudentPickerDialog(_BaseDialog):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(conn, "Pick student", parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.adm = QLineEdit()
        self.adm.setPlaceholderText("ADM/2025/001")
        form.addRow("Admission no.", self.adm)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        text = self.adm.text().strip()
        if not text:
            QMessageBox.warning(self, "Missing", "Enter an admission no.")
            return
        student = student_repo.get_by_admission_no(self._conn, text)
        if student is None:
            QMessageBox.warning(self, "Not found", f"No student with adm. no. {text!r}.")
            return
        self.params = {"student_id": student.id}
        self.accept()


class ClassPickerDialog(_BaseDialog):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(conn, "Pick class", parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.combo = QComboBox()
        _populate_classes(self.combo, conn)
        form.addRow("Class", self.combo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        cid = self.combo.currentData()
        if cid is None:
            QMessageBox.warning(self, "Missing", "Pick a class.")
            return
        self.params = {"class_id": cid}
        self.accept()


class ClassExamPickerDialog(_BaseDialog):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(conn, "Pick class & exam", parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.cls = QComboBox()
        _populate_classes(self.cls, conn)
        self.exam = QComboBox()
        _populate_exams(self.exam, conn)
        form.addRow("Class", self.cls)
        form.addRow("Exam", self.exam)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        cid = self.cls.currentData()
        eid = self.exam.currentData()
        if cid is None or eid is None:
            QMessageBox.warning(self, "Missing", "Pick a class and an exam.")
            return
        self.params = {"class_id": cid, "exam_id": eid}
        self.accept()


class YearPickerDialog(_BaseDialog):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(conn, "Pick academic year", parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.combo = QComboBox()
        _populate_years(self.combo, conn)
        form.addRow("Year", self.combo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        yid = self.combo.currentData()
        if yid is None:
            QMessageBox.warning(self, "Missing", "Pick a year.")
            return
        self.params = {"academic_year_id": yid}
        self.accept()


class TCPickerDialog(_BaseDialog):
    """Per-student TC form -- captures leaving date, reason, conduct, fees-paid."""

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(conn, "Transfer certificate", parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.adm = QLineEdit()
        self.adm.setPlaceholderText("ADM/2025/001")
        self.leaving_date = QDateEdit(QDate.currentDate())
        self.leaving_date.setCalendarPopup(True)
        self.leaving_date.setDisplayFormat("yyyy-MM-dd")
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Family relocation / completion / transfer to ...")
        self.conduct = QComboBox()
        self.conduct.addItems(["good", "very good", "excellent", "satisfactory"])
        self.fees_paid = QCheckBox("All fees paid")
        self.fees_paid.setChecked(True)
        form.addRow("Admission no.", self.adm)
        form.addRow("Date of leaving", self.leaving_date)
        form.addRow("Reason for leaving", self.reason)
        form.addRow("Conduct", self.conduct)
        form.addRow("", self.fees_paid)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        text = self.adm.text().strip()
        if not text:
            QMessageBox.warning(self, "Missing", "Enter an admission no.")
            return
        student = student_repo.get_by_admission_no(self._conn, text)
        if student is None:
            QMessageBox.warning(self, "Not found", f"No student with adm. no. {text!r}.")
            return
        from app.reports.general_pdfs import TCFormFields

        fields = TCFormFields(
            leaving_date=self.leaving_date.date().toString("yyyy-MM-dd"),
            reason=self.reason.text() or None,
            conduct=self.conduct.currentText(),
            fees_paid=self.fees_paid.isChecked(),
            issue_date=date_cls.today().isoformat(),
        )
        self.params = {"student_id": student.id, "fields": fields}
        self.accept()


class CharacterCertPickerDialog(_BaseDialog):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(conn, "Character certificate", parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.adm = QLineEdit()
        self.conduct = QComboBox()
        self.conduct.addItems(["good", "very good", "excellent", "satisfactory"])
        form.addRow("Admission no.", self.adm)
        form.addRow("Conduct", self.conduct)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        text = self.adm.text().strip()
        if not text:
            QMessageBox.warning(self, "Missing", "Enter an admission no.")
            return
        student = student_repo.get_by_admission_no(self._conn, text)
        if student is None:
            QMessageBox.warning(self, "Not found", f"No student with adm. no. {text!r}.")
            return
        self.params = {
            "student_id": student.id,
            "conduct": self.conduct.currentText(),
        }
        self.accept()
