"""Backup + restore tab."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import BACKUP_DIR, DB_PATH
from app.services import backup_service

log = logging.getLogger(__name__)


class BackupTab(QWidget):
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
                "An auto-backup is taken on every clean shutdown. The most "
                "recent 14 are kept under data/backups/. You can also "
                "save a manual backup or restore one below."
            )
        )

        layout.addWidget(QLabel(f"<b>Active database:</b> {DB_PATH}"))
        layout.addWidget(QLabel(f"<b>Backup folder:</b> {BACKUP_DIR}"))

        layout.addWidget(QLabel("Recent auto-backups:"))
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.list, 1)

        actions = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh list")
        self.refresh_btn.clicked.connect(self._reload)
        actions.addWidget(self.refresh_btn)
        actions.addStretch(1)
        self.manual_btn = QPushButton("Save manual backup...")
        self.manual_btn.clicked.connect(self._on_manual)
        actions.addWidget(self.manual_btn)
        self.restore_btn = QPushButton("Restore from selected...")
        self.restore_btn.clicked.connect(self._on_restore_selected)
        actions.addWidget(self.restore_btn)
        self.restore_file_btn = QPushButton("Restore from file...")
        self.restore_file_btn.clicked.connect(self._on_restore_file)
        actions.addWidget(self.restore_file_btn)
        layout.addLayout(actions)

    def refresh(self) -> None:
        self._reload()

    def _reload(self) -> None:
        self.list.clear()
        for path in backup_service.list_auto_backups():
            item = QListWidgetItem(f"{path.name}  ({path.stat().st_size // 1024} KB)")
            item.setData(0, str(path))
            self.list.addItem(item)
        if self.list.count() == 0:
            self.list.addItem(QListWidgetItem("(no auto-backups yet)"))

    # ------------------------------------------------------------------
    def _on_manual(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save manual backup",
            "school_backup.db",
            "SQLite databases (*.db)",
        )
        if not path:
            return
        try:
            backup_service.manual_backup(self._conn, path)
        except Exception as exc:
            QMessageBox.critical(self, "Backup failed", str(exc))
            return
        QMessageBox.information(self, "Backup saved", f"Saved to:\n{path}")

    # ------------------------------------------------------------------
    def _on_restore_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        path = item.data(0)
        if not path or not Path(path).is_file():
            return
        self._do_restore(Path(path))

    def _on_restore_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick backup file",
            "",
            "SQLite databases (*.db)",
        )
        if not path:
            return
        self._do_restore(Path(path))

    def _do_restore(self, source: Path) -> None:
        confirm = QMessageBox.question(
            self,
            "Confirm restore",
            f"Restore database from\n{source}\n\nThe current database will "
            "be renamed to .replaced.<timestamp>. After restore, the app "
            "must be restarted.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        confirm2 = QMessageBox.question(
            self,
            "Final confirmation",
            "This is irreversible without the renamed copy. Proceed?",
        )
        if confirm2 != QMessageBox.StandardButton.Yes:
            return
        try:
            replaced = backup_service.restore_backup(source)
        except Exception as exc:
            QMessageBox.critical(self, "Restore failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Restore complete",
            f"DB restored. Old DB saved as:\n{replaced}\n\nPlease close and re-open the app.",
        )
