"""Login dialog. Validates against ``auth_service`` (no SQL here)."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from app.models.user import User
from app.services.auth_service import authenticate
from app.utils.errors import AuthenticationError, ValidationError


class LoginDialog(QDialog):
    """Modal login. ``user`` is set to the authenticated User on accept."""

    def __init__(self, conn: sqlite3.Connection, school_name: str | None = None) -> None:
        super().__init__()
        self._conn = conn
        self.user: User | None = None

        self.setWindowTitle("School ERP — Sign in")
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        if school_name:
            heading = QLabel(school_name)
            font = heading.font()
            font.setPointSize(font.pointSize() + 2)
            font.setBold(True)
            heading.setFont(font)
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(heading)

        form_widget = QFormLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form_widget.addRow("Username", self.username)
        form_widget.addRow("Password", self.password)
        layout.addLayout(form_widget)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c0392b;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Sign in")
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.username.setFocus()

    def _try_login(self) -> None:
        self.error_label.setVisible(False)
        try:
            user = authenticate(self._conn, self.username.text(), self.password.text())
        except (AuthenticationError, ValidationError) as exc:
            self.error_label.setText(str(exc))
            self.error_label.setVisible(True)
            self.password.selectAll()
            self.password.setFocus()
            return
        self.user = user
        self.accept()
