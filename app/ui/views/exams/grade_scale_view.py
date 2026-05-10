"""Editor for the grade scale (replace-all save)."""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.grade_scale import GradeBand
from app.repositories import grade_scale_repo
from app.services import grade_scale_service
from app.utils.errors import ValidationError


class GradeScaleView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._build_ui()
        self._reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(
            QLabel(
                "Edit grade boundaries below. Bands cannot overlap. % = "
                "marks_obtained / max_marks * 100."
            )
        )

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Grade *", "Min %", "Max %", "Remarks"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.add_btn = QPushButton("Add band")
        self.add_btn.clicked.connect(lambda: self._add_row(GradeBand(None, "", 0.0, 0.0)))
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

    def refresh(self) -> None:
        self._reload()

    def _reload(self) -> None:
        self.table.setRowCount(0)
        for band in grade_scale_repo.list_all(self._conn):
            self._add_row(band)

    def _add_row(self, band: GradeBand) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        grade_edit = QLineEdit(band.grade)
        grade_edit.setMaxLength(8)
        min_spin = QDoubleSpinBox()
        min_spin.setRange(0.0, 100.0)
        min_spin.setDecimals(2)
        min_spin.setValue(band.min_percent)
        max_spin = QDoubleSpinBox()
        max_spin.setRange(0.0, 100.0)
        max_spin.setDecimals(2)
        max_spin.setValue(band.max_percent)
        remarks_edit = QLineEdit(band.remarks or "")
        self.table.setCellWidget(row, 0, grade_edit)
        self.table.setCellWidget(row, 1, min_spin)
        self.table.setCellWidget(row, 2, max_spin)
        self.table.setCellWidget(row, 3, remarks_edit)

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _gather(self) -> list[GradeBand]:
        out: list[GradeBand] = []
        for row in range(self.table.rowCount()):
            grade_edit: QLineEdit = self.table.cellWidget(row, 0)  # type: ignore[assignment]
            min_spin: QDoubleSpinBox = self.table.cellWidget(row, 1)  # type: ignore[assignment]
            max_spin: QDoubleSpinBox = self.table.cellWidget(row, 2)  # type: ignore[assignment]
            remarks_edit: QLineEdit = self.table.cellWidget(row, 3)  # type: ignore[assignment]
            out.append(
                GradeBand(
                    id=None,
                    grade=grade_edit.text(),
                    min_percent=min_spin.value(),
                    max_percent=max_spin.value(),
                    remarks=remarks_edit.text() or None,
                )
            )
        return out

    def _save(self) -> None:
        try:
            grade_scale_service.save_all(self._conn, self._gather())
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        QMessageBox.information(self, "Saved", "Grade scale saved.")
        self._reload()
