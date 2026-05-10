"""Users tab -- list, add, edit, reset password, deactivate."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
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
from app.models.user import User
from app.repositories import user_repo
from app.utils.security import hash_password

VALID_ROLES = ("admin", "operator", "viewer")


class _UserFormDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        user: User | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self.setWindowTitle("Edit user" if user else "Add user")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit(user.username if user else "")
        self.username.setEnabled(user is None)  # don't rename existing users
        self.full_name = QLineEdit(user.full_name or "" if user else "")
        self.role = QComboBox()
        for r in VALID_ROLES:
            self.role.addItem(r)
        if user is not None:
            i = self.role.findText(user.role)
            if i >= 0:
                self.role.setCurrentIndex(i)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        if user is None:
            self.password.setPlaceholderText("Required (>= 6 chars)")
        else:
            self.password.setPlaceholderText("Leave blank to keep existing")
        self.is_active = QCheckBox("Active")
        self.is_active.setChecked(user.is_active if user else True)
        form.addRow("Username *", self.username)
        form.addRow("Full name", self.full_name)
        form.addRow("Role *", self.role)
        form.addRow("Password", self.password)
        form.addRow("", self.is_active)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        username = self.username.text().strip().lower()
        if not username or " " in username:
            QMessageBox.warning(self, "Bad username", "Username is required, no spaces.")
            return
        full_name = self.full_name.text() or None
        role = self.role.currentText()
        password = self.password.text()
        if self._user is None:
            if len(password) < 6:
                QMessageBox.warning(self, "Password too short", "At least 6 characters.")
                return
            try:
                with transaction(self._conn):
                    user_repo.create_user(
                        self._conn,
                        User(
                            id=None,
                            username=username,
                            password_hash=hash_password(password),
                            role=role,
                            full_name=full_name,
                            is_active=self.is_active.isChecked(),
                        ),
                    )
            except Exception as exc:
                QMessageBox.critical(self, "Cannot save", str(exc))
                return
        else:
            new_hash = hash_password(password) if password else self._user.password_hash
            if password and len(password) < 6:
                QMessageBox.warning(self, "Password too short", "At least 6 characters.")
                return
            from dataclasses import replace

            updated = replace(
                self._user,
                role=role,
                full_name=full_name,
                is_active=self.is_active.isChecked(),
                password_hash=new_hash,
            )
            try:
                with transaction(self._conn):
                    self._conn.execute(
                        "UPDATE users SET role = ?, full_name = ?, is_active = ?, "
                        "password_hash = ? WHERE id = ?",
                        (
                            updated.role,
                            updated.full_name,
                            1 if updated.is_active else 0,
                            updated.password_hash,
                            updated.id,
                        ),
                    )
            except Exception as exc:
                QMessageBox.critical(self, "Cannot save", str(exc))
                return
        self.accept()


class UsersTab(QWidget):
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
                "User accounts. Deactivate a user to revoke their login "
                "without deleting their audit-log history."
            )
        )

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Username", "Role", "Full name", "Active"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.add_btn = QPushButton("Add user...")
        self.add_btn.clicked.connect(self._add)
        actions.addWidget(self.add_btn)
        self.edit_btn = QPushButton("Edit selected...")
        self.edit_btn.clicked.connect(self._edit)
        actions.addWidget(self.edit_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

    def refresh(self) -> None:
        self._reload()

    def _reload(self) -> None:
        users = user_repo.list_users(self._conn)
        self.table.setRowCount(len(users))
        for r, u in enumerate(users):
            label_item = QTableWidgetItem(u.username)
            label_item.setData(0x100, u.id)
            self.table.setItem(r, 0, label_item)
            self.table.setItem(r, 1, QTableWidgetItem(u.role))
            self.table.setItem(r, 2, QTableWidgetItem(u.full_name or ""))
            self.table.setItem(r, 3, QTableWidgetItem("Yes" if u.is_active else "No"))

    def _selected_user(self) -> User | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        uid = item.data(0x100)
        if uid is None:
            return None
        return next((u for u in user_repo.list_users(self._conn) if u.id == uid), None)

    def _add(self) -> None:
        dlg = _UserFormDialog(self._conn, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._reload()

    def _edit(self) -> None:
        user = self._selected_user()
        if user is None:
            QMessageBox.information(self, "Pick first", "Select a user.")
            return
        dlg = _UserFormDialog(self._conn, user=user, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._reload()
