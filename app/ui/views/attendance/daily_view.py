"""Daily attendance entry — class + date picker, P/A/L/H radio grid.

Each student row gets one ``QButtonGroup`` so the four radios are mutually
exclusive within the row but independent across rows. Save commits in a
single transaction via the service.
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories import attendance_repo, class_repo, school_repo
from app.services import attendance_service
from app.utils.errors import ValidationError

log = logging.getLogger(__name__)

_STATUSES = ("P", "A", "L", "H")
_HEADERS = ("Roll", "Name", "P", "A", "L", "H")


class DailyAttendanceView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        # Per-row radio bookkeeping — index aligns with the table rows.
        self._row_groups: list[QButtonGroup] = []
        self._row_radios: list[dict[str, QRadioButton]] = []
        self._student_ids: list[int] = []

        self._build_ui()
        self._populate_class_combo()
        self._reload()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_toolbar())

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(2, len(_HEADERS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        actions = QHBoxLayout()
        self.mark_all_btn = QPushButton("Mark all present")
        self.mark_all_btn.clicked.connect(self._mark_all_present)
        actions.addWidget(self.mark_all_btn)
        actions.addStretch(1)
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

        layout.addWidget(QLabel("Date:"))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.dateChanged.connect(self._reload)
        layout.addWidget(self.date_edit)

        layout.addStretch(1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._reload)
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

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """External entry point — refresh class list (after masters edits)."""
        previous = self.class_combo.currentData()
        self._populate_class_combo()
        if previous is not None:
            idx = self.class_combo.findData(previous)
            if idx >= 0:
                self.class_combo.setCurrentIndex(idx)
        self._reload()

    def _reload(self) -> None:
        class_id = self.class_combo.currentData()
        date_iso = self.date_edit.date().toString("yyyy-MM-dd")

        self.table.setRowCount(0)
        self._row_groups = []
        self._row_radios = []
        self._student_ids = []

        if class_id is None:
            self.summary_label.setText("Pick a class to begin.")
            return

        rows = attendance_repo.list_for_class_and_date(self._conn, class_id, date_iso)
        self._populate_table(rows)
        marked = sum(1 for r in rows if r[4] is not None)
        self.summary_label.setText(
            f"{len(rows)} active student(s) in this class. {marked} already marked for {date_iso}."
        )

    def _populate_table(
        self,
        rows: list[tuple[int, int | None, str, str | None, str | None]],
    ) -> None:
        self.table.setRowCount(len(rows))
        for row_idx, (student_id, roll, first, last, status) in enumerate(rows):
            self._student_ids.append(student_id)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(roll) if roll else ""))
            full_name = " ".join(filter(None, [first, last]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(full_name))

            group = QButtonGroup(self.table)
            group.setExclusive(True)
            radios: dict[str, QRadioButton] = {}
            for col_offset, code in enumerate(_STATUSES):
                radio = QRadioButton()
                if status == code:
                    radio.setChecked(True)
                cell = QWidget()
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.addWidget(radio)
                cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setCellWidget(row_idx, 2 + col_offset, cell)
                group.addButton(radio)
                radios[code] = radio
            self._row_groups.append(group)
            self._row_radios.append(radios)

    # ------------------------------------------------------------------
    def _gather_marks(self) -> dict[int, str]:
        marks: dict[int, str] = {}
        for row_idx, sid in enumerate(self._student_ids):
            for code, radio in self._row_radios[row_idx].items():
                if radio.isChecked():
                    marks[sid] = code
                    break
        return marks

    def _mark_all_present(self) -> None:
        for radios in self._row_radios:
            radios["P"].setChecked(True)

    def _save(self) -> None:
        class_id = self.class_combo.currentData()
        date_iso = self.date_edit.date().toString("yyyy-MM-dd")
        marks = self._gather_marks()
        if not marks:
            QMessageBox.information(
                self,
                "Nothing to save",
                "No students are marked yet. Use 'Mark all present' or pick a "
                "status for at least one student.",
            )
            return
        try:
            count = attendance_service.save_class_attendance(
                self._conn,
                class_id=class_id,
                date_iso=date_iso,
                marks=marks,
                marked_by=None,
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.summary_label.setText(f"Saved {count} mark(s) for {date_iso}.")
