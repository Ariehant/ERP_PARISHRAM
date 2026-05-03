"""Class form with inline subjects.

The top half edits the class itself (name, section, year, class teacher).
The bottom half is an editable subjects table with Add/Remove buttons. On
Save the service runs class + subjects in a single transaction.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.structure import Class, Subject
from app.repositories import class_repo, school_repo, staff_repo
from app.services import class_service
from app.utils.errors import ValidationError


class ClassFormDialog(QDialog):
    """Add or edit a class. ``saved_id`` is set on accept."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        cls: Class | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._cls = cls
        self.saved_id: int | None = None

        self.setWindowTitle("Edit class" if cls else "Add class")
        self.setMinimumSize(620, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_class_box())
        layout.addWidget(self._build_subjects_box(), 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_year_combo()
        self._populate_teacher_combo()
        if cls is not None:
            self._load_from(cls)

    # ------------------------------------------------------------------
    def _build_class_box(self) -> QWidget:
        box = QGroupBox("Class details")
        form = QFormLayout(box)

        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. 5")
        self.section = QLineEdit()
        self.section.setPlaceholderText("e.g. A")

        self.year_combo = QComboBox()
        self.teacher_combo = QComboBox()
        self.teacher_combo.addItem("(unassigned)", None)

        form.addRow("Class name *", self.name)
        form.addRow("Section *", self.section)
        form.addRow("Academic year *", self.year_combo)
        form.addRow("Class teacher", self.teacher_combo)
        return box

    def _build_subjects_box(self) -> QWidget:
        box = QGroupBox("Subjects")
        layout = QVBoxLayout(box)

        self.subjects_table = QTableWidget(0, 4)
        self.subjects_table.setHorizontalHeaderLabels(["Name *", "Code", "Max marks", "Optional"])
        self.subjects_table.verticalHeader().setVisible(False)
        self.subjects_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.subjects_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        # Map row index → existing subject id (None for newly added rows).
        self._row_ids: list[int | None] = []
        layout.addWidget(self.subjects_table, 1)

        btns = QHBoxLayout()
        self.add_subject_btn = QPushButton("Add subject")
        self.add_subject_btn.clicked.connect(lambda: self._add_subject_row())
        self.remove_subject_btn = QPushButton("Remove selected")
        self.remove_subject_btn.clicked.connect(self._remove_selected_subject)
        btns.addWidget(self.add_subject_btn)
        btns.addWidget(self.remove_subject_btn)
        btns.addStretch(1)
        layout.addLayout(btns)
        return box

    # ------------------------------------------------------------------
    def _populate_year_combo(self) -> None:
        years = school_repo.list_academic_years(self._conn)
        active = school_repo.get_active_academic_year(self._conn)
        if not years:
            # Should never happen — setup wizard creates one — but be defensive.
            self.year_combo.addItem("(no years)", None)
            return
        for y in years:
            label = f"{y.label}{' (active)' if y.is_active else ''}"
            self.year_combo.addItem(label, y.id)
        if active is not None:
            idx = self.year_combo.findData(active.id)
            if idx >= 0:
                self.year_combo.setCurrentIndex(idx)

    def _populate_teacher_combo(self) -> None:
        for teacher in staff_repo.list_active_teachers(self._conn):
            self.teacher_combo.addItem(f"{teacher.name} ({teacher.emp_code})", teacher.id)

    def _load_from(self, cls: Class) -> None:
        self.name.setText(cls.name)
        self.section.setText(cls.section)
        idx = self.year_combo.findData(cls.academic_year_id)
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        if cls.class_teacher_id is not None:
            tidx = self.teacher_combo.findData(cls.class_teacher_id)
            if tidx >= 0:
                self.teacher_combo.setCurrentIndex(tidx)
        if cls.id is not None:
            for s in class_repo.list_subjects_for_class(self._conn, cls.id):
                self._add_subject_row(s)

    # ------------------------------------------------------------------
    def _add_subject_row(self, subject: Subject | None = None) -> None:
        row = self.subjects_table.rowCount()
        self.subjects_table.insertRow(row)
        self._row_ids.append(subject.id if subject is not None else None)

        name_item = QTableWidgetItem(subject.name if subject else "")
        code_item = QTableWidgetItem(subject.code or "" if subject else "")
        max_marks_spin = QSpinBox()
        max_marks_spin.setRange(1, 1000)
        max_marks_spin.setValue(subject.max_marks if subject else 100)
        optional_check = QCheckBox()
        optional_check.setChecked(subject.is_optional if subject else False)

        self.subjects_table.setItem(row, 0, name_item)
        self.subjects_table.setItem(row, 1, code_item)
        self.subjects_table.setCellWidget(row, 2, max_marks_spin)
        # Wrap the checkbox so it centers nicely in the cell.
        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.addWidget(optional_check)
        cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subjects_table.setCellWidget(row, 3, cell)

    def _remove_selected_subject(self) -> None:
        row = self.subjects_table.currentRow()
        if row < 0:
            return
        self.subjects_table.removeRow(row)
        del self._row_ids[row]

    def _gather_subjects(self) -> list[Subject]:
        out: list[Subject] = []
        for row in range(self.subjects_table.rowCount()):
            name_item = self.subjects_table.item(row, 0)
            code_item = self.subjects_table.item(row, 1)
            max_marks_spin: QSpinBox = self.subjects_table.cellWidget(row, 2)  # type: ignore[assignment]
            optional_cell: QWidget = self.subjects_table.cellWidget(row, 3)  # type: ignore[assignment]
            optional_check = optional_cell.findChild(QCheckBox)

            out.append(
                Subject(
                    id=self._row_ids[row],
                    name=(name_item.text() if name_item else ""),
                    class_id=self._cls.id if self._cls else 0,  # set in service
                    code=((code_item.text() or None) if code_item else None),
                    max_marks=max_marks_spin.value(),
                    is_optional=optional_check.isChecked() if optional_check else False,
                )
            )
        return out

    def _gather_class(self) -> Class:
        return Class(
            id=self._cls.id if self._cls else None,
            name=self.name.text(),
            section=self.section.text().upper(),
            academic_year_id=self.year_combo.currentData() or 0,
            class_teacher_id=self.teacher_combo.currentData(),
        )

    # ------------------------------------------------------------------
    def _on_save(self) -> None:
        cls = self._gather_class()
        subjects = self._gather_subjects()
        try:
            self.saved_id = class_service.save_class(self._conn, cls, subjects)
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.accept()
