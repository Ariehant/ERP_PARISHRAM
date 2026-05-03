"""First-run wizard: collect school details, academic year, and admin user.

The wizard hands collected data to ``setup_service.perform_initial_setup``;
the service does all validation and DB writes. UI just renders + relays errors.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QWizard,
    QWizardPage,
)

from app.services.setup_service import SetupRequest, perform_initial_setup
from app.utils.errors import ValidationError


class _SchoolPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("School details")
        self.setSubTitle("Tell us about your school. You can edit these later in Settings.")

        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Parishram Public School")
        self.address = QTextEdit()
        self.address.setFixedHeight(70)
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.affiliation = QLineEdit()

        layout = QFormLayout(self)
        layout.addRow("School name *", self.name)
        layout.addRow("Address", self.address)
        layout.addRow("Phone", self.phone)
        layout.addRow("Email", self.email)
        layout.addRow("Affiliation no.", self.affiliation)

        self.registerField("school_name*", self.name)

    def isComplete(self) -> bool:
        return bool(self.name.text().strip())


class _AcademicYearPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Academic year")
        self.setSubTitle("Set the current academic year. The app uses ISO dates internally.")

        today = QDate.currentDate()
        # Default Indian academic year: April-March
        default_start = QDate(today.year(), 4, 1)
        default_end = QDate(today.year() + 1, 3, 31)
        self.label = QLineEdit(f"{today.year()}-{(today.year() + 1) % 100:02d}")
        self.start = QDateEdit(default_start)
        self.start.setDisplayFormat("yyyy-MM-dd")
        self.start.setCalendarPopup(True)
        self.end = QDateEdit(default_end)
        self.end.setDisplayFormat("yyyy-MM-dd")
        self.end.setCalendarPopup(True)

        layout = QFormLayout(self)
        layout.addRow("Year label *", self.label)
        layout.addRow("Start date *", self.start)
        layout.addRow("End date *", self.end)

        self.registerField("year_label*", self.label)


class _AdminUserPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Administrator account")
        self.setSubTitle("This account can do everything. Choose a strong password.")

        self.full_name = QLineEdit()
        self.username = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)

        layout = QFormLayout(self)
        layout.addRow("Full name", self.full_name)
        layout.addRow("Username *", self.username)
        layout.addRow("Password *", self.password)
        layout.addRow("Confirm password *", self.confirm)

        self.registerField("admin_username*", self.username)
        self.registerField("admin_password*", self.password)
        self.registerField("admin_password_confirm*", self.confirm)

    def validatePage(self) -> bool:
        if self.password.text() != self.confirm.text():
            QMessageBox.warning(self, "Passwords don't match", "Re-enter the password.")
            return False
        if len(self.password.text()) < 6:
            QMessageBox.warning(self, "Password too short", "Use at least 6 characters.")
            return False
        return True


class SetupWizard(QWizard):
    """Collects setup data and writes it via ``setup_service``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self._conn = conn
        self.setWindowTitle("School ERP — First-time setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(560, 420)
        # Persist across show/hide cycles.
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

        self._school_page = _SchoolPage()
        self._year_page = _AcademicYearPage()
        self._admin_page = _AdminUserPage()
        self.addPage(self._school_page)
        self.addPage(self._year_page)
        self.addPage(self._admin_page)

        self.created_user_id: int | None = None
        self.created_username: str | None = None

    # ------------------------------------------------------------------
    def accept(self) -> None:
        try:
            req = SetupRequest(
                school_name=self._school_page.name.text(),
                address=self._school_page.address.toPlainText() or None,
                phone=self._school_page.phone.text() or None,
                email=self._school_page.email.text() or None,
                affiliation_no=self._school_page.affiliation.text() or None,
                academic_year_label=self._year_page.label.text(),
                academic_year_start=self._year_page.start.date().toString(Qt.DateFormat.ISODate),
                academic_year_end=self._year_page.end.date().toString(Qt.DateFormat.ISODate),
                admin_username=self._admin_page.username.text(),
                admin_full_name=self._admin_page.full_name.text() or None,
                admin_password=self._admin_page.password.text(),
            )
            user_id = perform_initial_setup(self._conn, req)
        except ValidationError as exc:
            QMessageBox.warning(self, "Setup error", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Setup failed", str(exc))
            return

        self.created_user_id = user_id
        self.created_username = req.admin_username.strip().lower()
        super().accept()
