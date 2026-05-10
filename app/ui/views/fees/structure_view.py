"""Editor for the per-class fee structure (replace-all save)."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.fee import FeeStructure
from app.repositories import class_repo, fee_structure_repo, school_repo
from app.services import fee_service
from app.utils.errors import ValidationError
from app.utils.formatters import rupees_to_paise

_FREQUENCIES = fee_service.VALID_FREQUENCIES


class FeeStructureView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._build_ui()
        self._populate_class_combo()
        self._reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_toolbar())

        layout.addWidget(
            QLabel(
                "One row per fee head. Frequency drives the pending calculation: "
                "monthly = N times, quarterly = up to 4, annual / one_time = once."
            )
        )

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Head *", "Amount (Rs.) *", "Frequency *", "Due month (1-12)"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.add_btn = QPushButton("Add row")
        self.add_btn.clicked.connect(lambda: self._add_row())
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.clicked.connect(self._remove_selected)
        actions.addWidget(self.add_btn)
        actions.addWidget(self.remove_btn)
        actions.addStretch(1)
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self._reload)
        actions.addWidget(self.reload_btn)
        self.save_btn = QPushButton("Save")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        actions.addWidget(self.save_btn)
        layout.addLayout(actions)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        self.class_combo.currentIndexChanged.connect(self._reload)
        layout.addWidget(self.class_combo)
        layout.addStretch(1)
        return bar

    # ------------------------------------------------------------------
    def _populate_class_combo(self) -> None:
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        active = school_repo.get_active_academic_year(self._conn)
        if active is not None and active.id is not None:
            for cls in class_repo.list_for_year(self._conn, active.id):
                self.class_combo.addItem(f"{cls.name}-{cls.section}", cls.id)
        if self.class_combo.count() == 0:
            self.class_combo.addItem("(no classes)", None)
            self.class_combo.setEnabled(False)
        self.class_combo.blockSignals(False)

    def refresh(self) -> None:
        previous = self.class_combo.currentData()
        self._populate_class_combo()
        if previous is not None:
            i = self.class_combo.findData(previous)
            if i >= 0:
                self.class_combo.setCurrentIndex(i)
        self._reload()

    def _reload(self) -> None:
        self.table.setRowCount(0)
        cid = self.class_combo.currentData()
        active = school_repo.get_active_academic_year(self._conn)
        if cid is None or active is None or active.id is None:
            return
        for fs in fee_structure_repo.list_for_class(self._conn, cid, active.id):
            self._add_row(fs)

    def _add_row(self, fs: FeeStructure | None = None) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        head_edit = QLineEdit(fs.head if fs else "")
        amount_spin = QDoubleSpinBox()
        amount_spin.setRange(0.0, 1_000_000.0)
        amount_spin.setDecimals(2)
        amount_spin.setSingleStep(50.0)
        amount_spin.setValue((fs.amount_paise / 100.0) if fs else 0.0)
        freq_combo = QComboBox()
        for f in _FREQUENCIES:
            freq_combo.addItem(f, f)
        if fs is not None:
            i = freq_combo.findData(fs.frequency)
            if i >= 0:
                freq_combo.setCurrentIndex(i)
        month_spin = QSpinBox()
        month_spin.setRange(0, 12)
        month_spin.setSpecialValueText("-")
        month_spin.setValue(fs.due_month or 0 if fs else 0)
        self.table.setCellWidget(row, 0, head_edit)
        self.table.setCellWidget(row, 1, amount_spin)
        self.table.setCellWidget(row, 2, freq_combo)
        self.table.setCellWidget(row, 3, month_spin)

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _gather(self) -> list[FeeStructure]:
        out: list[FeeStructure] = []
        for row in range(self.table.rowCount()):
            head_edit: QLineEdit = self.table.cellWidget(row, 0)  # type: ignore[assignment]
            amount_spin: QDoubleSpinBox = self.table.cellWidget(row, 1)  # type: ignore[assignment]
            freq_combo: QComboBox = self.table.cellWidget(row, 2)  # type: ignore[assignment]
            month_spin: QSpinBox = self.table.cellWidget(row, 3)  # type: ignore[assignment]
            month_value = month_spin.value() or None
            out.append(
                FeeStructure(
                    id=None,
                    class_id=0,
                    academic_year_id=0,
                    head=head_edit.text(),
                    amount_paise=rupees_to_paise(amount_spin.value()),
                    frequency=freq_combo.currentData(),
                    due_month=month_value,
                )
            )
        return out

    def _save(self) -> None:
        cid = self.class_combo.currentData()
        active = school_repo.get_active_academic_year(self._conn)
        if cid is None or active is None or active.id is None:
            QMessageBox.warning(self, "Pick first", "Pick a class first.")
            return
        try:
            fee_service.save_structure(
                self._conn,
                class_id=cid,
                academic_year_id=active.id,
                rows=self._gather(),
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        QMessageBox.information(self, "Saved", "Fee structure saved.")
        self._reload()
