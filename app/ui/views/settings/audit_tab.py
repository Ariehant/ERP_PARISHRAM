"""Audit-log viewer with filters."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import DEFAULT_PAGE_SIZE
from app.repositories import audit_log_repo
from app.ui.widgets.paged_table import Column, PagedTableModel, PagedTableView


class AuditLogTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._build_ui()
        self._refresh_filters()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(self._build_toolbar())

        columns = [
            Column("ID", lambda r: r["id"]),
            Column("When", lambda r: (r["timestamp"] or "")[:19]),
            Column("User", lambda r: r["username"]),
            Column("Action", lambda r: r["action"]),
            Column("Entity", lambda r: r["entity"]),
            Column("Entity ID", lambda r: r["entity_id"] if r["entity_id"] is not None else ""),
            Column("Details", lambda r: r["details"] or ""),
        ]
        self._model = PagedTableModel(
            columns=columns,
            fetcher=self._fetch,
            counter=self._count,
            page_size=DEFAULT_PAGE_SIZE,
            parent=self,
        )
        self._table = PagedTableView(self._model, parent=self)
        layout.addWidget(self._table, 1)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Action:"))
        self.action_combo = QComboBox()
        self.action_combo.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.action_combo)

        layout.addWidget(QLabel("Entity:"))
        self.entity_combo = QComboBox()
        self.entity_combo.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.entity_combo)

        layout.addWidget(QLabel("From:"))
        self.from_date = QDateEdit(QDate.currentDate().addDays(-30))
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        self.from_date.dateChanged.connect(self.refresh)
        layout.addWidget(self.from_date)

        layout.addWidget(QLabel("To:"))
        self.to_date = QDateEdit(QDate.currentDate())
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        self.to_date.dateChanged.connect(self.refresh)
        layout.addWidget(self.to_date)

        layout.addStretch(1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_filters_then_reload)
        layout.addWidget(self.refresh_btn)
        return bar

    def _refresh_filters(self) -> None:
        prev_action = self.action_combo.currentData() if hasattr(self, "action_combo") else None
        prev_entity = self.entity_combo.currentData() if hasattr(self, "entity_combo") else None

        self.action_combo.blockSignals(True)
        self.action_combo.clear()
        self.action_combo.addItem("All actions", None)
        for a in audit_log_repo.distinct_actions(self._conn):
            self.action_combo.addItem(a, a)
        if prev_action is not None:
            i = self.action_combo.findData(prev_action)
            if i >= 0:
                self.action_combo.setCurrentIndex(i)
        self.action_combo.blockSignals(False)

        self.entity_combo.blockSignals(True)
        self.entity_combo.clear()
        self.entity_combo.addItem("All entities", None)
        for e in audit_log_repo.distinct_entities(self._conn):
            self.entity_combo.addItem(e, e)
        if prev_entity is not None:
            i = self.entity_combo.findData(prev_entity)
            if i >= 0:
                self.entity_combo.setCurrentIndex(i)
        self.entity_combo.blockSignals(False)

    def _refresh_filters_then_reload(self) -> None:
        self._refresh_filters()
        self.refresh()

    def _filters(self) -> dict:
        return {
            "action": self.action_combo.currentData(),
            "entity": self.entity_combo.currentData(),
            "date_from": self.from_date.date().toString("yyyy-MM-dd"),
            "date_to": self.to_date.date().toString("yyyy-MM-dd"),
        }

    def _fetch(self, limit: int, offset: int) -> list:
        return audit_log_repo.list_page(self._conn, limit=limit, offset=offset, **self._filters())

    def _count(self) -> int:
        return audit_log_repo.count(self._conn, **self._filters())

    def refresh(self) -> None:
        self._model.set_page(1)
        self._model.refresh()
