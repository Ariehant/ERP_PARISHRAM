"""Editable school-details form."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.connection import transaction
from app.models.school import School
from app.repositories import school_repo


class SchoolTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._school: School | None = None
        self._build_ui()
        self._reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        form = QFormLayout()
        self.name = QLineEdit()
        self.address = QTextEdit()
        self.address.setFixedHeight(80)
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.affiliation = QLineEdit()
        form.addRow("School name *", self.name)
        form.addRow("Address", self.address)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Affiliation no.", self.affiliation)
        layout.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self._reload)
        actions.addWidget(self.reload_btn)
        self.save_btn = QPushButton("Save")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        actions.addWidget(self.save_btn)
        layout.addLayout(actions)

    def refresh(self) -> None:
        self._reload()

    def _reload(self) -> None:
        self._school = school_repo.get_first_school(self._conn)
        if self._school is None:
            return
        self.name.setText(self._school.name)
        self.address.setPlainText(self._school.address or "")
        self.phone.setText(self._school.phone or "")
        self.email.setText(self._school.email or "")
        self.affiliation.setText(self._school.affiliation_no or "")

    def _save(self) -> None:
        if self._school is None:
            QMessageBox.warning(self, "No school", "No school configured yet.")
            return
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Cannot save", "School name is required.")
            return
        from dataclasses import replace

        updated = replace(
            self._school,
            name=name,
            address=self.address.toPlainText() or None,
            phone=self.phone.text() or None,
            email=self.email.text() or None,
            affiliation_no=self.affiliation.text() or None,
        )
        try:
            with transaction(self._conn):
                school_repo.update_school(self._conn, updated)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        QMessageBox.information(self, "Saved", "School details updated.")
        self._reload()
