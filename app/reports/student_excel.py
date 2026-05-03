"""Student Excel template + export.

Both helpers use ``openpyxl`` directly. Field names match
``ImportRow`` keys consumed by ``app.services.student_service``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.models.people import Student

log = logging.getLogger(__name__)

# (column_key, human_header, sample_value, recommended_width)
TEMPLATE_COLUMNS: tuple[tuple[str, str, str, int], ...] = (
    ("admission_no", "Admission No *", "ADM/2025/001", 18),
    ("roll_no", "Roll No", "1", 8),
    ("first_name", "First Name *", "Aarav", 14),
    ("last_name", "Last Name", "Sharma", 14),
    ("dob", "DOB (YYYY-MM-DD)", "2014-08-15", 14),
    ("gender", "Gender (M/F/O)", "M", 8),
    ("blood_group", "Blood Group", "O+", 10),
    ("admission_date", "Admission Date * (YYYY-MM-DD)", "2025-04-01", 18),
    ("status", "Status", "active", 12),
    ("father_name", "Father's Name", "Rajeev Sharma", 18),
    ("father_phone", "Father's Phone", "9876543210", 14),
    ("mother_name", "Mother's Name", "Priya Sharma", 18),
    ("mother_phone", "Mother's Phone", "9876500000", 14),
    ("address", "Address", "12 Civil Lines", 22),
    ("city", "City", "Lucknow", 14),
    ("state", "State", "Uttar Pradesh", 14),
    ("pincode", "Pincode", "226001", 10),
    ("aadhaar", "Aadhaar (12 digits)", "123412341234", 16),
    ("prev_school", "Previous School", "St. Mary's", 18),
    ("category", "Category", "General", 12),
    ("religion", "Religion", "Hindu", 12),
)

_HEADER_FILL = PatternFill("solid", fgColor="1F3864")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)


def write_template(target: str | Path) -> Path:
    """Write a blank import template to ``target`` (xlsx). Returns the path."""
    target = Path(target)
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"

    # Header row
    for col_idx, (_, header, _sample, width) in enumerate(TEMPLATE_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _HEADER_ALIGN
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Sample row (commented in italics by leaving the values plain — easy to delete)
    for col_idx, (_, _, sample, _w) in enumerate(TEMPLATE_COLUMNS, start=1):
        ws.cell(row=2, column=col_idx, value=sample).font = Font(italic=True, color="888888")

    # Notes sheet
    notes = wb.create_sheet("Notes")
    notes["A1"] = "How to use this template"
    notes["A1"].font = Font(bold=True, size=14)
    note_lines = [
        "1. Replace the sample row on the 'Students' sheet with real data.",
        "2. Required columns are marked with *.",
        "3. Dates must be in YYYY-MM-DD format (e.g. 2025-04-01).",
        "4. Gender is M, F, or O. Status defaults to 'active' if blank.",
        "5. Aadhaar is 12 digits, Pincode is 6 digits.",
        "6. The class assignment is done from the Students screen after import.",
    ]
    for i, line in enumerate(note_lines, start=3):
        notes.cell(row=i, column=1, value=line)
    notes.column_dimensions["A"].width = 90

    ws.freeze_panes = "A2"
    wb.save(target)
    log.info("Wrote student import template to %s", target)
    return target


def write_export(target: str | Path, students: Iterable[Student]) -> Path:
    """Write the supplied students to ``target`` (xlsx)."""
    target = Path(target)
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"

    for col_idx, (_, header, _, width) in enumerate(TEMPLATE_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _HEADER_ALIGN
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    for r, student in enumerate(students, start=2):
        for c, (key, *_rest) in enumerate(TEMPLATE_COLUMNS, start=1):
            ws.cell(row=r, column=c, value=getattr(student, key))

    ws.freeze_panes = "A2"
    wb.save(target)
    log.info("Wrote %d students to %s", ws.max_row - 1, target)
    return target


def read_rows(source: str | Path) -> list[dict[str, object]]:
    """Read an import file. Returns one dict per data row, keyed by column key.

    The first sheet is read; the first row is treated as the header. Empty
    rows are skipped. Dates that come back as Python ``datetime`` objects are
    converted to ISO date strings.
    """
    from datetime import date, datetime

    from openpyxl import load_workbook

    wb = load_workbook(source, data_only=True)
    ws = wb.worksheets[0]

    expected_keys = [k for k, *_ in TEMPLATE_COLUMNS]
    header_to_key = {header.lower(): key for key, header, *_ in TEMPLATE_COLUMNS}

    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    column_keys: list[str | None] = []
    for cell in header_row:
        if cell is None:
            column_keys.append(None)
            continue
        key = header_to_key.get(str(cell).strip().lower())
        column_keys.append(key)

    rows: list[dict[str, object]] = []
    for raw in ws.iter_rows(min_row=2, values_only=True):
        if all(cell is None or (isinstance(cell, str) and not cell.strip()) for cell in raw):
            continue
        record: dict[str, object] = {k: None for k in expected_keys}
        for value, key in zip(raw, column_keys, strict=False):
            if key is None:
                continue
            if isinstance(value, datetime):
                value = value.date().isoformat()
            elif isinstance(value, date):
                value = value.isoformat()
            elif isinstance(value, float) and value.is_integer():
                value = int(value)
            record[key] = value
        rows.append(record)
    return rows
