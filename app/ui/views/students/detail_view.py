"""Read-only profile sheet. Shows everything the student form captures.

Academic data (attendance, marks, fees) lands in later phases.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.models.people import Student
from app.utils.formatters import format_date


def _value(text: str | None) -> QLabel:
    label = QLabel(text or "—")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _form_pair(rows: list[tuple[str, str | None]]) -> QGroupBox:
    """Helper for a labelled key/value group."""
    box = QGroupBox()
    grid = QGridLayout(box)
    grid.setColumnStretch(1, 1)
    for r, (k, v) in enumerate(rows):
        key = QLabel(f"<b>{k}</b>")
        grid.addWidget(key, r, 0, alignment=Qt.AlignmentFlag.AlignTop)
        grid.addWidget(_value(v), r, 1)
    return box


class StudentDetailDialog(QDialog):
    """Read-only profile dialog for a single student."""

    def __init__(self, student: Student, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        full_name = " ".join(filter(None, [student.first_name, student.last_name]))
        self.setWindowTitle(f"Profile — {full_name}  ({student.admission_no})")
        self.setMinimumSize(640, 540)

        layout = QVBoxLayout(self)

        # Header: photo + basic identity
        header = QHBoxLayout()
        photo = QLabel()
        photo.setFixedSize(120, 150)
        photo.setStyleSheet("QLabel { border: 1px solid #aaa; background: #fafafa; }")
        photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if student.photo_path:
            pix = QPixmap(student.photo_path)
            if not pix.isNull():
                photo.setPixmap(
                    pix.scaled(
                        photo.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                photo.setText("(missing)")
        else:
            photo.setText("No photo")
        header.addWidget(photo)

        ident = QFormLayout()
        ident.addRow("Admission no.", _value(student.admission_no))
        ident.addRow("Roll no.", _value(str(student.roll_no) if student.roll_no else None))
        ident.addRow("Status", _value(student.status))
        ident.addRow(
            "Date of birth",
            _value(format_date(student.dob) if student.dob else None),
        )
        ident.addRow("Gender", _value(student.gender))
        ident.addRow("Blood group", _value(student.blood_group))
        ident.addRow(
            "Admission date",
            _value(format_date(student.admission_date) if student.admission_date else None),
        )
        header.addLayout(ident, 1)
        layout.addLayout(header)

        # Family
        family = _form_pair(
            [
                ("Father", student.father_name),
                ("Father's phone", student.father_phone),
                ("Father's occupation", student.father_occupation),
                ("Mother", student.mother_name),
                ("Mother's phone", student.mother_phone),
                ("Mother's occupation", student.mother_occupation),
                ("Guardian", student.guardian_name),
                ("Guardian's phone", student.guardian_phone),
            ]
        )
        family.setTitle("Family")
        layout.addWidget(family)

        # Address
        address = _form_pair(
            [
                ("Street", student.address),
                ("City", student.city),
                ("State", student.state),
                ("Pincode", student.pincode),
            ]
        )
        address.setTitle("Address")
        layout.addWidget(address)

        # Other
        other = _form_pair(
            [
                ("Aadhaar", student.aadhaar),
                ("Previous school", student.prev_school),
                ("Category", student.category),
                ("Religion", student.religion),
            ]
        )
        other.setTitle("Other")
        layout.addWidget(other)

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
