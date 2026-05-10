"""Marks entry grid for a class+exam.

Columns: Roll | Name | <Subject 1 (max=N)> | <Subject 2 (max=N)> | ... | %
Each subject column is a ``QDoubleSpinBox`` ranging 0..max_marks. Empty
cells (value left at 0 with the special-text empty trick) are left
untouched on Save.

Save flow uses the service which auto-grades based on the configured
grade scale.
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories import (
    class_repo,
    exam_repo,
    school_repo,
    student_repo,
)
from app.services import mark_service
from app.utils.errors import ValidationError

log = logging.getLogger(__name__)

# Sentinel: anything < 0 means "blank".
_BLANK = -1.0


class MarksEntryView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._student_ids: list[int] = []
        self._subject_ids: list[int] = []
        self._subject_max: list[int] = []
        self._spinboxes: dict[tuple[int, int], QDoubleSpinBox] = {}

        self._build_ui()
        self._populate_class_combo()
        self._populate_exam_combo()
        self._reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_toolbar())

        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        actions = QHBoxLayout()
        self.import_btn = QPushButton("Import from Excel...")
        self.import_btn.clicked.connect(self._open_import)
        actions.addWidget(self.import_btn)
        self.template_btn = QPushButton("Save template...")
        self.template_btn.clicked.connect(self._save_template)
        actions.addWidget(self.template_btn)
        actions.addStretch(1)
        self.save_btn = QPushButton("Save marks")
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

        layout.addWidget(QLabel("Exam:"))
        self.exam_combo = QComboBox()
        self.exam_combo.currentIndexChanged.connect(self._reload)
        layout.addWidget(self.exam_combo)

        layout.addStretch(1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_dropdowns)
        layout.addWidget(self.refresh_btn)
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

    def _populate_exam_combo(self) -> None:
        self.exam_combo.blockSignals(True)
        self.exam_combo.clear()
        active = school_repo.get_active_academic_year(self._conn)
        if active is not None and active.id is not None:
            for e in exam_repo.list_for_year(self._conn, active.id):
                label = e.name + (f" ({e.exam_type})" if e.exam_type else "")
                self.exam_combo.addItem(label, e.id)
        if self.exam_combo.count() == 0:
            self.exam_combo.addItem("(no exams)", None)
            self.exam_combo.setEnabled(False)
        self.exam_combo.blockSignals(False)

    def refresh(self) -> None:
        self._refresh_dropdowns()

    def _refresh_dropdowns(self) -> None:
        prev_class = self.class_combo.currentData()
        prev_exam = self.exam_combo.currentData()
        self._populate_class_combo()
        self._populate_exam_combo()
        if prev_class is not None:
            i = self.class_combo.findData(prev_class)
            if i >= 0:
                self.class_combo.setCurrentIndex(i)
        if prev_exam is not None:
            i = self.exam_combo.findData(prev_exam)
            if i >= 0:
                self.exam_combo.setCurrentIndex(i)
        self._reload()

    # ------------------------------------------------------------------
    def _reload(self) -> None:
        class_id = self.class_combo.currentData()
        exam_id = self.exam_combo.currentData()

        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self._student_ids = []
        self._subject_ids = []
        self._subject_max = []
        self._spinboxes = {}

        if class_id is None or exam_id is None:
            self.summary_label.setText("Pick a class and an exam to begin.")
            self.save_btn.setEnabled(False)
            return

        students = student_repo.list_all_for_export(self._conn, class_id=class_id, status="active")
        subjects = class_repo.list_subjects_for_class(self._conn, class_id)
        if not students:
            self.summary_label.setText("No active students in this class.")
            self.save_btn.setEnabled(False)
            return
        if not subjects:
            self.summary_label.setText(
                "This class has no subjects yet -- add some in Classes & Staff."
            )
            self.save_btn.setEnabled(False)
            return

        self.save_btn.setEnabled(True)
        self._student_ids = [s.id for s in students if s.id is not None]
        self._subject_ids = [s.id for s in subjects if s.id is not None]
        self._subject_max = [s.max_marks for s in subjects if s.id is not None]

        headers: list[str] = ["Roll", "Name"]
        for s in subjects:
            headers.append(f"{s.name}\n(max={s.max_marks})")

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        existing = mark_service.load_grid(self._conn, class_id, exam_id)
        self.table.setRowCount(len(students))
        for r, student in enumerate(students):
            self.table.setItem(r, 0, QTableWidgetItem(str(student.roll_no or "")))
            full_name = " ".join(filter(None, [student.first_name, student.last_name]))
            self.table.setItem(r, 1, QTableWidgetItem(full_name))
            for c_idx, sid in enumerate(self._subject_ids, start=2):
                spin = QDoubleSpinBox()
                spin.setRange(_BLANK, float(self._subject_max[c_idx - 2]))
                spin.setDecimals(2)
                spin.setSingleStep(1.0)
                spin.setSpecialValueText("-")  # shows when value == _BLANK
                spin.setValue(_BLANK)
                spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if student.id is not None:
                    cell = existing.get((student.id, sid))
                    if cell is not None and cell["marks_obtained"] is not None:
                        spin.setValue(float(cell["marks_obtained"]))
                self.table.setCellWidget(r, c_idx, spin)
                self._spinboxes[(student.id, sid)] = spin  # type: ignore[index]

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(2, len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.summary_label.setText(
            f"{len(students)} student(s), {len(subjects)} subject(s). "
            "Use '-' to leave a cell blank."
        )

    # ------------------------------------------------------------------
    def _gather_inputs(self) -> list[mark_service.MarkInput]:
        inputs: list[mark_service.MarkInput] = []
        for (student_id, subject_id), spin in self._spinboxes.items():
            value = spin.value()
            if value <= _BLANK:
                continue
            inputs.append(
                mark_service.MarkInput(
                    student_id=student_id,
                    subject_id=subject_id,
                    marks_obtained=value,
                )
            )
        return inputs

    def _save(self) -> None:
        class_id = self.class_combo.currentData()
        exam_id = self.exam_combo.currentData()
        inputs = self._gather_inputs()
        if not inputs:
            QMessageBox.information(
                self,
                "Nothing to save",
                "Enter marks for at least one student/subject first. Cells marked '-' are skipped.",
            )
            return
        try:
            count = mark_service.save_class_exam_marks(
                self._conn, class_id=class_id, exam_id=exam_id, inputs=inputs
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.summary_label.setText(f"Saved {count} mark(s).")

    # ------------------------------------------------------------------
    def _save_template(self) -> None:
        class_id = self.class_combo.currentData()
        exam_id = self.exam_combo.currentData()
        if class_id is None or exam_id is None:
            QMessageBox.warning(self, "Pick first", "Pick a class and an exam first.")
            return
        exam = exam_repo.get(self._conn, exam_id)
        if exam is None:
            QMessageBox.warning(self, "No exam", "Exam not found.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save marks template",
            f"marks_template_{exam.name.replace(' ', '_')}.xlsx",
            "Excel files (*.xlsx)",
        )
        if not path:
            return
        try:
            from app.reports.marks_excel import write_template

            written = write_template(path, self._conn, class_id=class_id, exam_name=exam.name)
        except Exception as exc:
            QMessageBox.critical(self, "Template", f"Could not write: {exc}")
            return
        QMessageBox.information(self, "Template", f"Saved to:\n{written}")

    def _open_import(self) -> None:
        class_id = self.class_combo.currentData()
        exam_id = self.exam_combo.currentData()
        if class_id is None or exam_id is None:
            QMessageBox.warning(self, "Pick first", "Pick a class and an exam first.")
            return
        from app.ui.views.exams.marks_import_dialog import MarksImportDialog

        dlg = MarksImportDialog(self._conn, class_id, exam_id, parent=self)
        if dlg.exec() and dlg.imported_count:
            self._reload()
