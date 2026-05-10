"""Fee collection screen.

Flow: pick student -> show pending heads -> select rows + edit amounts ->
enter mode + reference + date -> Save (single tx, atomic receipt no) ->
optionally print A4 or thermal receipt (worker thread).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories import student_repo
from app.services import fee_service
from app.utils.errors import ValidationError
from app.utils.formatters import format_inr, rupees_to_paise
from app.workers.fee_pdf import FeePDFWorker

log = logging.getLogger(__name__)

_HEADERS = ("Pay?", "Head", "Frequency", "Due", "Paid", "Outstanding", "This payment (Rs.)")


class FeeCollectionView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._student_id: int | None = None
        self._pending: list[fee_service.PendingHead] = []
        self._last_payment_id: int | None = None
        self._last_receipt_no: str | None = None
        self._pdf_worker: FeePDFWorker | None = None
        self._progress: QProgressDialog | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_lookup_bar())
        layout.addWidget(self._build_student_box())
        layout.addWidget(self._build_pending_box(), 1)
        layout.addWidget(self._build_meta_bar())
        layout.addWidget(self._build_actions_bar())

    # ----- top: student lookup -----
    def _build_lookup_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Admission no.:"))
        self.admission_input = QLineEdit()
        self.admission_input.setPlaceholderText("ADM/2025/001")
        self.admission_input.returnPressed.connect(self._lookup)
        layout.addWidget(self.admission_input, 1)
        self.lookup_btn = QPushButton("Look up")
        self.lookup_btn.clicked.connect(self._lookup)
        layout.addWidget(self.lookup_btn)
        return bar

    def _build_student_box(self) -> QWidget:
        self.student_label = QLabel("No student selected.")
        font = self.student_label.font()
        font.setBold(True)
        self.student_label.setFont(font)
        return self.student_label

    # ----- middle: pending grid -----
    def _build_pending_box(self) -> QWidget:
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(2, len(_HEADERS)):
            h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        return self.table

    # ----- bottom: payment metadata + actions -----
    def _build_meta_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Date:"))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_edit)

        layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        for m in fee_service.VALID_MODES:
            self.mode_combo.addItem(m.upper(), m)
        layout.addWidget(self.mode_combo)

        layout.addWidget(QLabel("Reference:"))
        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("UPI / cheque no. (optional)")
        layout.addWidget(self.reference_input, 1)

        layout.addWidget(QLabel("Remarks:"))
        self.remarks_input = QLineEdit()
        layout.addWidget(self.remarks_input, 1)
        return bar

    def _build_actions_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self.total_label = QLabel("Total: -")
        font = self.total_label.font()
        font.setBold(True)
        self.total_label.setFont(font)
        layout.addWidget(self.total_label)
        layout.addStretch(1)

        self.save_btn = QPushButton("Save && receipt no.")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn)

        self.print_a4_btn = QPushButton("Print A4 receipt...")
        self.print_a4_btn.clicked.connect(lambda: self._print_receipt("a4"))
        self.print_a4_btn.setEnabled(False)
        layout.addWidget(self.print_a4_btn)

        self.print_thermal_btn = QPushButton("Print 80mm receipt...")
        self.print_thermal_btn.clicked.connect(lambda: self._print_receipt("thermal"))
        self.print_thermal_btn.setEnabled(False)
        layout.addWidget(self.print_thermal_btn)
        return bar

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        # Re-load pending if we already have a student selected.
        if self._student_id is not None:
            self._load_pending(self._student_id)

    def _lookup(self) -> None:
        text = self.admission_input.text().strip()
        if not text:
            return
        student = student_repo.get_by_admission_no(self._conn, text)
        if student is None:
            QMessageBox.warning(self, "Not found", f"No student with admission no. {text!r}.")
            return
        self._student_id = student.id
        full_name = " ".join(filter(None, [student.first_name, student.last_name]))
        from app.repositories import class_repo

        cls_label = "(unassigned)"
        if student.class_id is not None:
            cls = class_repo.get_class(self._conn, student.class_id)
            if cls is not None:
                cls_label = f"{cls.name}-{cls.section}"
        self.student_label.setText(f"{full_name} ({student.admission_no}) - Class {cls_label}")
        self._last_payment_id = None
        self._last_receipt_no = None
        self.print_a4_btn.setEnabled(False)
        self.print_thermal_btn.setEnabled(False)
        self._load_pending(student.id)

    def _load_pending(self, student_id: int) -> None:
        try:
            self._pending = fee_service.pending_for_student(self._conn, student_id)
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot load fees", exc.message)
            return
        self.table.setRowCount(len(self._pending))
        for r, p in enumerate(self._pending):
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            check_item.setCheckState(
                Qt.CheckState.Checked if p.outstanding_paise > 0 else Qt.CheckState.Unchecked
            )
            check_item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
            self.table.setItem(r, 0, check_item)
            self.table.setItem(r, 1, QTableWidgetItem(p.head))
            self.table.setItem(r, 2, QTableWidgetItem(p.frequency))
            self.table.setItem(r, 3, QTableWidgetItem(format_inr(p.total_due_paise)))
            self.table.setItem(r, 4, QTableWidgetItem(format_inr(p.paid_paise)))
            self.table.setItem(r, 5, QTableWidgetItem(format_inr(p.outstanding_paise)))
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1_000_000.0)
            spin.setDecimals(2)
            spin.setValue(p.outstanding_paise / 100.0)
            spin.setAlignment(Qt.AlignmentFlag.AlignRight)
            spin.valueChanged.connect(self._update_total)
            self.table.setCellWidget(r, 6, spin)
        self.table.itemChanged.connect(self._on_item_changed)
        self._update_total()
        self.save_btn.setEnabled(any(p.outstanding_paise > 0 for p in self._pending))

    def _on_item_changed(self, _item) -> None:
        # Toggling a checkbox doesn't change spin values, but the total cares
        # about which rows are checked.
        self._update_total()

    def _selected_inputs(self) -> list[fee_service.PaymentItemInput]:
        out: list[fee_service.PaymentItemInput] = []
        for r, p in enumerate(self._pending):
            check_item = self.table.item(r, 0)
            if check_item is None or check_item.checkState() != Qt.CheckState.Checked:
                continue
            spin: QDoubleSpinBox = self.table.cellWidget(r, 6)  # type: ignore[assignment]
            paise = rupees_to_paise(spin.value())
            if paise <= 0:
                continue
            out.append(
                fee_service.PaymentItemInput(
                    head=p.head,
                    amount_paise=paise,
                    fee_structure_id=p.fee_structure_id,
                )
            )
        return out

    def _update_total(self) -> None:
        total = sum(it.amount_paise for it in self._selected_inputs())
        self.total_label.setText(f"Total: {format_inr(total)}")

    # ------------------------------------------------------------------
    def _save(self) -> None:
        if self._student_id is None:
            return
        items = self._selected_inputs()
        if not items:
            QMessageBox.warning(
                self, "Nothing selected", "Tick at least one head and enter an amount."
            )
            return
        try:
            result = fee_service.collect_payment(
                self._conn,
                student_id=self._student_id,
                payment_date=self.date_edit.date().toString("yyyy-MM-dd"),
                mode=self.mode_combo.currentData(),
                items=items,
                reference_no=self.reference_input.text() or None,
                remarks=self.remarks_input.text() or None,
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot save", exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        self._last_payment_id = result.payment_id
        self._last_receipt_no = result.receipt_no
        QMessageBox.information(
            self,
            "Receipt saved",
            f"Receipt no. {result.receipt_no}\nClick 'Print receipt' to save the PDF.",
        )
        self.print_a4_btn.setEnabled(True)
        self.print_thermal_btn.setEnabled(True)
        self.reference_input.clear()
        self.remarks_input.clear()
        # Re-load pending so the row counters tick up.
        self._load_pending(self._student_id)

    def _print_receipt(self, kind: str) -> None:
        if self._last_payment_id is None:
            return
        default_name = f"{(self._last_receipt_no or 'receipt').replace('/', '_')}_{kind}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save receipt PDF", default_name, "PDF files (*.pdf)"
        )
        if not path:
            return
        worker_kind = "receipt_a4" if kind == "a4" else "receipt_thermal"
        self._spawn_worker(Path(path), worker_kind, {"payment_id": self._last_payment_id})

    def _spawn_worker(self, target: Path, kind: str, params: dict) -> None:
        if self._pdf_worker is not None and self._pdf_worker.isRunning():
            QMessageBox.information(self, "Busy", "A PDF is already being generated. Please wait.")
            return
        progress = QProgressDialog("Generating PDF...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        self._progress = progress

        worker = FeePDFWorker(target, kind, params, parent=self)
        worker.error.connect(self._on_worker_error)
        worker.finished_with_path.connect(self._on_worker_done)
        worker.finished.connect(self._cleanup_worker)
        self._pdf_worker = worker
        worker.start()

    def _on_worker_error(self, message: str) -> None:
        if self._progress is not None:
            self._progress.cancel()
        QMessageBox.critical(self, "PDF failed", message)

    def _on_worker_done(self, path: str) -> None:
        if self._progress is not None:
            self._progress.cancel()
        QMessageBox.information(self, "PDF saved", f"Saved to:\n{path}")

    def _cleanup_worker(self) -> None:
        if self._pdf_worker is not None:
            self._pdf_worker.deleteLater()
            self._pdf_worker = None
        self._progress = None
