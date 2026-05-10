"""Fees tab container -- Structure | Collection | Ledger | Defaulters."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.ui.views.fees.collection_view import FeeCollectionView
from app.ui.views.fees.defaulters_view import FeeDefaultersView
from app.ui.views.fees.ledger_view import FeeLedgerView
from app.ui.views.fees.structure_view import FeeStructureView


class FeesView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.structure_view = FeeStructureView(conn)
        self.collection_view = FeeCollectionView(conn)
        self.ledger_view = FeeLedgerView(conn)
        self.defaulters_view = FeeDefaultersView(conn)
        self.tabs.addTab(self.structure_view, "Structure")
        self.tabs.addTab(self.collection_view, "Collection")
        self.tabs.addTab(self.ledger_view, "Ledger")
        self.tabs.addTab(self.defaulters_view, "Defaulters")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
