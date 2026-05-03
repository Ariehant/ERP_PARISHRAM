"""Staff add/edit form."""

from __future__ import annotations

import sqlite3

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

from app.models.people import Staff
from app.services import staff_service
from app.utils.errors import ValidationError


class StaffFormDialog(QDialog):
    """Add or edit a staff member. ``saved_id`` is set on accept."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        staff: Staff | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._staff = staff
        self.saved_id: int | None = None

        self.setWindowTitle("Edit staff" if staff else "Add staff")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.emp_code = QLineEdit()
        self.emp_code.setPlaceholderText("EMP/2025/001")
        self.name = QLineEdit()
        self.role = QComboBox()
        self.role.addItems(staff_service.VALID_ROLES)
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.joining_date = QDateEdit()
        self.joining_date.setCalendarPopup(True)
        self.joining_date.setDisplayFormat("yyyy-MM-dd")
        self.joining_date.setDate(QDate.currentDate())
        self.joining_date.setSpecialValueText(" ")  # treat min-date as "unset"
        self.qualification = QLineEdit()
        self.is_active = QCheckBox("Active")
        self.is_active.setChecked(True)

        form.addRow("Employee code *", self.emp_code)
        form.addRow("Name *", self.name)
        form.addRow("Role *", self.role)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Joining date", self.joining_date)
        form.addRow("Qualification", self.qualification)
        form.addRow("", self.is_active)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if staff is not None:
            self._load_from(staff)

    def _load_from(self, s: Staff) -> None:
        self.emp_code.setText(s.emp_code)
        self.name.setText(s.name)
        self.role.setCurrentText(s.role)
        self.phone.setText(s.phone or "")
        self.email.setText(s.email or "")
        if s.joining_date:
            self.joining_date.setDate(QDate.fromString(s.joining_date, "yyyy-MM-dd"))
        self.qualification.setText(s.qualification or "")
        self.is_active.setChecked(s.is_active)

    def _gather(self) -> Staff:
        return Staff(
            id=self._staff.id if self._staff else None,
            emp_code=self.emp_code.text(),
            name=self.name.text(),
            role=self.role.currentText(),
            phone=self.phone.text() or None,
            email=self.email.text() or None,
            joining_date=self.joining_date.date().toString("yyyy-MM-dd"),
            qualification=self.qualification.text() or None,
            is_active=self.is_active.isChecked(),
        )

    def _on_save(self) -> None:
        staff = self._gather()
        try:
            if staff.id is None:
                self.saved_id = staff_service.create_staff(self._conn, staff)
            else:
                staff_service.update_staff(self._conn, staff)
                self.saved_id = staff.id
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.accept()
