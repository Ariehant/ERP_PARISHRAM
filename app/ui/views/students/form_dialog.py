"""Admission form (new + edit). Tabs keep the long field list manageable.

Service layer does the actual validation; this dialog just gathers values,
copies the chosen photo into the photo store, and shows error messages.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.people import Student
from app.services import student_service
from app.utils.errors import ValidationError
from app.utils.photos import PhotoError, copy_photo_to_store


def _line(initial: str | None = None, placeholder: str | None = None) -> QLineEdit:
    widget = QLineEdit(initial or "")
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


class StudentFormDialog(QDialog):
    """New / edit student. ``saved_id`` is set to the resulting row id on accept."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        student: Student | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._student = student
        # Source path of a freshly picked photo (not yet copied into the store).
        self._pending_photo_src: str | None = None
        # Already-stored photo path (when editing). Mirrors student.photo_path.
        self._existing_photo_path: str | None = student.photo_path if student else None
        self.saved_id: int | None = None

        title = "Edit student" if student else "Add student"
        self.setWindowTitle(title)
        self.setMinimumSize(640, 520)

        self._build_ui()
        if student:
            self._load_from(student)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_personal(), "Personal")
        self.tabs.addTab(self._tab_family(), "Family")
        self.tabs.addTab(self._tab_address(), "Address")
        self.tabs.addTab(self._tab_other(), "Other")
        layout.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _tab_personal(self) -> QWidget:
        page = QWidget()
        outer = QHBoxLayout(page)

        # Photo column.
        photo_col = QVBoxLayout()
        self.photo_label = QLabel("No photo")
        self.photo_label.setFixedSize(140, 170)
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setStyleSheet(
            "QLabel { border: 1px solid #aaa; background: #fafafa; color: #888; }"
        )
        photo_col.addWidget(self.photo_label)
        photo_btns = QHBoxLayout()
        pick = QPushButton("Pick…")
        pick.clicked.connect(self._on_pick_photo)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._on_clear_photo)
        photo_btns.addWidget(pick)
        photo_btns.addWidget(clear)
        photo_col.addLayout(photo_btns)
        photo_col.addStretch(1)
        outer.addLayout(photo_col)

        form = QFormLayout()
        self.admission_no = _line(placeholder="ADM/2025/001")
        self.roll_no = QSpinBox()
        self.roll_no.setRange(0, 9999)
        self.roll_no.setSpecialValueText(" ")  # treat 0 as "not set"
        self.first_name = _line()
        self.last_name = _line()
        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.dob.setDisplayFormat("yyyy-MM-dd")
        self.dob.setDate(QDate(2010, 1, 1))
        self.gender = QComboBox()
        self.gender.addItems(["", "M", "F", "O"])
        self.blood_group = QComboBox()
        self.blood_group.setEditable(True)
        self.blood_group.addItems(["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])
        self.admission_date = QDateEdit()
        self.admission_date.setCalendarPopup(True)
        self.admission_date.setDisplayFormat("yyyy-MM-dd")
        self.admission_date.setDate(QDate.currentDate())
        self.status = QComboBox()
        self.status.addItems(student_service.VALID_STATUSES)
        self.class_combo = QComboBox()
        self._populate_class_combo()

        form.addRow("Admission no. *", self.admission_no)
        form.addRow("Roll no.", self.roll_no)
        form.addRow("First name *", self.first_name)
        form.addRow("Last name", self.last_name)
        form.addRow("Date of birth", self.dob)
        form.addRow("Gender", self.gender)
        form.addRow("Blood group", self.blood_group)
        form.addRow("Admission date *", self.admission_date)
        form.addRow("Class", self.class_combo)
        form.addRow("Status", self.status)
        outer.addLayout(form, 1)
        return page

    def _tab_family(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.father_name = _line()
        self.father_phone = _line()
        self.father_occupation = _line()
        self.mother_name = _line()
        self.mother_phone = _line()
        self.mother_occupation = _line()
        self.guardian_name = _line()
        self.guardian_phone = _line()
        form.addRow("Father's name", self.father_name)
        form.addRow("Father's phone", self.father_phone)
        form.addRow("Father's occupation", self.father_occupation)
        form.addRow("Mother's name", self.mother_name)
        form.addRow("Mother's phone", self.mother_phone)
        form.addRow("Mother's occupation", self.mother_occupation)
        form.addRow("Guardian's name", self.guardian_name)
        form.addRow("Guardian's phone", self.guardian_phone)
        return page

    def _tab_address(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.address = QTextEdit()
        self.address.setFixedHeight(80)
        self.city = _line()
        self.state = _line()
        self.pincode = _line(placeholder="6 digits")
        form.addRow("Street address", self.address)
        form.addRow("City", self.city)
        form.addRow("State", self.state)
        form.addRow("Pincode", self.pincode)
        return page

    def _tab_other(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.aadhaar = _line(placeholder="12 digits")
        self.prev_school = _line()
        self.category = _line(placeholder="General / OBC / SC / ST / EWS")
        self.religion = _line()
        form.addRow("Aadhaar", self.aadhaar)
        form.addRow("Previous school", self.prev_school)
        form.addRow("Category", self.category)
        form.addRow("Religion", self.religion)
        return page

    # ------------------------------------------------------------------
    def _load_from(self, s: Student) -> None:
        self.admission_no.setText(s.admission_no)
        self.roll_no.setValue(s.roll_no or 0)
        self.first_name.setText(s.first_name)
        self.last_name.setText(s.last_name or "")
        if s.dob:
            self.dob.setDate(QDate.fromString(s.dob, "yyyy-MM-dd"))
        if s.gender:
            self.gender.setCurrentText(s.gender)
        if s.blood_group:
            self.blood_group.setCurrentText(s.blood_group)
        if s.admission_date:
            self.admission_date.setDate(QDate.fromString(s.admission_date, "yyyy-MM-dd"))
        if s.class_id is not None:
            idx = self.class_combo.findData(s.class_id)
            if idx >= 0:
                self.class_combo.setCurrentIndex(idx)
        self.status.setCurrentText(s.status or "active")
        self.father_name.setText(s.father_name or "")
        self.father_phone.setText(s.father_phone or "")
        self.father_occupation.setText(s.father_occupation or "")
        self.mother_name.setText(s.mother_name or "")
        self.mother_phone.setText(s.mother_phone or "")
        self.mother_occupation.setText(s.mother_occupation or "")
        self.guardian_name.setText(s.guardian_name or "")
        self.guardian_phone.setText(s.guardian_phone or "")
        self.address.setPlainText(s.address or "")
        self.city.setText(s.city or "")
        self.state.setText(s.state or "")
        self.pincode.setText(s.pincode or "")
        self.aadhaar.setText(s.aadhaar or "")
        self.prev_school.setText(s.prev_school or "")
        self.category.setText(s.category or "")
        self.religion.setText(s.religion or "")
        if s.photo_path:
            self._render_photo(s.photo_path)

    def _populate_class_combo(self) -> None:
        """Fill the class dropdown from classes in the active academic year."""
        from app.repositories import class_repo, school_repo

        self.class_combo.clear()
        self.class_combo.addItem("(unassigned)", None)
        active = school_repo.get_active_academic_year(self._conn)
        if active is None or active.id is None:
            return
        for cls in class_repo.list_for_year(self._conn, active.id):
            self.class_combo.addItem(f"{cls.name}-{cls.section}", cls.id)

    # ------------------------------------------------------------------
    def _on_pick_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select photo",
            "",
            "Images (*.jpg *.jpeg *.png *.webp)",
        )
        if not path:
            return
        if not Path(path).is_file():
            QMessageBox.warning(self, "Photo", "That file does not exist.")
            return
        self._pending_photo_src = path
        self._render_photo(path)

    def _on_clear_photo(self) -> None:
        self._pending_photo_src = None
        self._existing_photo_path = None
        self.photo_label.clear()
        self.photo_label.setText("No photo")

    def _render_photo(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.photo_label.setText("(can't load)")
            return
        self.photo_label.setPixmap(
            pixmap.scaled(
                self.photo_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    # ------------------------------------------------------------------
    def _gather(self) -> Student:
        roll_value: int | None = self.roll_no.value() or None
        gender_text = self.gender.currentText().strip() or None
        blood_text = self.blood_group.currentText().strip() or None
        return Student(
            id=self._student.id if self._student else None,
            admission_no=self.admission_no.text(),
            roll_no=roll_value,
            first_name=self.first_name.text(),
            last_name=self.last_name.text() or None,
            dob=self.dob.date().toString("yyyy-MM-dd"),
            gender=gender_text,
            blood_group=blood_text,
            photo_path=self._existing_photo_path,
            class_id=self.class_combo.currentData(),
            admission_date=self.admission_date.date().toString("yyyy-MM-dd"),
            status=self.status.currentText() or "active",
            father_name=self.father_name.text() or None,
            father_phone=self.father_phone.text() or None,
            father_occupation=self.father_occupation.text() or None,
            mother_name=self.mother_name.text() or None,
            mother_phone=self.mother_phone.text() or None,
            mother_occupation=self.mother_occupation.text() or None,
            guardian_name=self.guardian_name.text() or None,
            guardian_phone=self.guardian_phone.text() or None,
            address=self.address.toPlainText() or None,
            city=self.city.text() or None,
            state=self.state.text() or None,
            pincode=self.pincode.text() or None,
            aadhaar=self.aadhaar.text() or None,
            prev_school=self.prev_school.text() or None,
            category=self.category.text() or None,
            religion=self.religion.text() or None,
        )

    def _on_save(self) -> None:
        # 1. Copy any newly-picked photo into the store first. Easier to clean
        #    up on validation failure than to roll back a DB write.
        if self._pending_photo_src:
            try:
                self._existing_photo_path = copy_photo_to_store(self._pending_photo_src)
                self._pending_photo_src = None
            except PhotoError as exc:
                QMessageBox.warning(self, "Photo", str(exc))
                return

        student = self._gather()
        try:
            if student.id is None:
                self.saved_id = student_service.create_student(self._conn, student)
            else:
                student_service.update_student(self._conn, student)
                self.saved_id = student.id
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.accept()
