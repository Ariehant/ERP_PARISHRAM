"""General PDFs for the reports hub.

Eight generators sharing helpers from ``_helpers.py``:

- ``write_profile``                -- per-student profile sheet
- ``write_class_roster``           -- class roster with photos optional
- ``write_mark_sheet``             -- per-class+exam mark sheet
- ``write_admission_register``     -- students who joined in a year
- ``write_withdrawal_register``    -- transferred / passed-out students
- ``write_transfer_certificate``   -- TC for a single student (form-fill)
- ``write_character_certificate``  -- character certificate
- ``write_id_card_sheet``          -- 8 cards per A4 page
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date as date_cls
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.reports import _helpers
from app.repositories import (
    class_repo,
    counters_repo,
    exam_repo,
    mark_repo,
    school_repo,
    student_repo,
)
from app.utils.formatters import format_date


def _doc(target: Path, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=title,
    )


def _photo(path: str | None, w: float, h: float):
    if not path:
        return Paragraph("(no photo)", _helpers.styles()["erp_small"])
    p = Path(path)
    if not p.is_file():
        return Paragraph("(missing)", _helpers.styles()["erp_small"])
    try:
        return Image(str(p), width=w * cm, height=h * cm, kind="proportional")
    except Exception:
        return Paragraph("(bad photo)", _helpers.styles()["erp_small"])


# ---------------------------------------------------------------------------
# 1. Student profile
# ---------------------------------------------------------------------------
def write_profile(target: str | Path, conn: sqlite3.Connection, student_id: int) -> Path:
    target = Path(target)
    s = _helpers.styles()
    student = student_repo.get(conn, student_id)
    if student is None:
        raise ValueError(f"Student {student_id} not found.")
    doc = _doc(target, "Student Profile")
    story: list = []
    _helpers.school_header(conn, story, "Student profile")

    identity = Table(
        [
            ["Name", _helpers.student_full_name(student)],
            ["Adm. No.", student.admission_no],
            ["Class", _helpers.class_label(conn, student.class_id)],
            ["Roll No.", str(student.roll_no or "-")],
            ["DOB", format_date(student.dob) if student.dob else "-"],
            ["Gender", student.gender or "-"],
            ["Status", student.status],
        ],
        colWidths=[3 * cm, 9 * cm],
    )
    identity.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                ("FONT", (1, 0), (1, -1), "Helvetica", 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    head = Table(
        [[_photo(student.photo_path, 3, 4), identity]],
        colWidths=[3.5 * cm, 13 * cm],
    )
    head.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (1, 0), (1, 0), 6)])
    )
    story.append(head)
    story.append(_helpers.hr_spacer(0.4))

    # Family / address / other in three sections.
    def _kv_block(title: str, rows: list[tuple[str, str | None]]) -> None:
        story.append(Paragraph(title, s["erp_h3"]))
        body = Table(
            [[k, (v or "-")] for k, v in rows],
            colWidths=[5 * cm, 11 * cm],
        )
        body.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                    ("FONT", (1, 0), (1, -1), "Helvetica", 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(body)
        story.append(_helpers.hr_spacer(0.2))

    _kv_block(
        "Family",
        [
            ("Father", student.father_name),
            ("Father's phone", student.father_phone),
            ("Mother", student.mother_name),
            ("Mother's phone", student.mother_phone),
            ("Guardian", student.guardian_name),
            ("Guardian's phone", student.guardian_phone),
        ],
    )
    _kv_block(
        "Address",
        [
            ("Street", student.address),
            ("City", student.city),
            ("State", student.state),
            ("Pincode", student.pincode),
        ],
    )
    _kv_block(
        "Other",
        [
            ("Aadhaar", student.aadhaar),
            ("Previous school", student.prev_school),
            ("Category", student.category),
            ("Religion", student.religion),
            (
                "Admission date",
                format_date(student.admission_date) if student.admission_date else "-",
            ),
        ],
    )

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# 2. Class roster
# ---------------------------------------------------------------------------
def write_class_roster(target: str | Path, conn: sqlite3.Connection, class_id: int) -> Path:
    target = Path(target)
    s = _helpers.styles()
    students = student_repo.list_all_for_export(conn, class_id=class_id, status="active")
    doc = _doc(target, "Class Roster")
    story: list = []
    _helpers.school_header(
        conn,
        story,
        "Class Roster",
        f"Class {_helpers.class_label(conn, class_id)} - {len(students)} active student(s)",
    )

    if not students:
        story.append(Paragraph("No active students in this class.", s["Normal"]))
    else:
        data = [["Roll", "Adm. No.", "Name", "Father / Guardian", "Phone", "Status"]]
        for st in students:
            data.append(
                [
                    str(st.roll_no or "-"),
                    st.admission_no,
                    _helpers.student_full_name(st),
                    st.father_name or st.guardian_name or "",
                    st.father_phone or st.guardian_phone or "",
                    st.status,
                ]
            )
        table = Table(
            data,
            colWidths=[1.5 * cm, 2.8 * cm, 5 * cm, 4 * cm, 2.7 * cm, 1.8 * cm],
            repeatRows=1,
        )
        table.setStyle(_helpers.DEFAULT_TABLE_STYLE)
        story.append(table)

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# 3. Mark sheet (per class + exam)
# ---------------------------------------------------------------------------
def write_mark_sheet(
    target: str | Path,
    conn: sqlite3.Connection,
    class_id: int,
    exam_id: int,
) -> Path:
    target = Path(target)
    s = _helpers.styles()
    exam = exam_repo.get(conn, exam_id)
    if exam is None:
        raise ValueError(f"Exam {exam_id} not found.")
    students = student_repo.list_all_for_export(conn, class_id=class_id, status="active")
    subjects = class_repo.list_subjects_for_class(conn, class_id)
    doc = _doc(target, "Mark Sheet")
    story: list = []
    _helpers.school_header(
        conn,
        story,
        f"Mark Sheet - {exam.name}",
        f"Class {_helpers.class_label(conn, class_id)}",
    )

    if not students or not subjects:
        story.append(Paragraph("No students or subjects for this class.", s["Normal"]))
    else:
        # Pre-fetch all marks for the class + exam.
        mark_rows = mark_repo.list_for_class_and_exam(conn, class_id, exam_id)
        cell_map: dict[tuple[int, int], dict] = {
            (r["student_id"], r["subject_id"]): r for r in mark_rows
        }

        header = (
            ["Roll", "Name"]
            + [f"{sub.name}\n(/{sub.max_marks})" for sub in subjects]
            + ["Total", "%"]
        )
        data = [header]
        for st in students:
            row: list[str] = [str(st.roll_no or "-"), _helpers.student_full_name(st)]
            obtained = 0
            max_total = 0
            for sub in subjects:
                cell = cell_map.get((st.id, sub.id)) if st.id and sub.id else None
                if cell is None or cell["marks_obtained"] is None:
                    row.append("-")
                    continue
                row.append(f"{cell['marks_obtained']:g}")
                obtained += int(cell["marks_obtained"])
                max_total += int(cell["max_marks"])
            row.append(f"{obtained}/{max_total}" if max_total else "-")
            row.append(f"{(obtained / max_total * 100):.1f}" if max_total else "-")
            data.append(row)

        col_widths = [1.4 * cm, 4 * cm] + [1.6 * cm] * len(subjects) + [2 * cm, 1.4 * cm]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(_helpers.DEFAULT_TABLE_STYLE)
        story.append(table)

    story.append(_helpers.hr_spacer(0.6))
    story.append(_helpers.signature_table(["Class teacher", "Principal"]))
    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# 4. Admission register
# ---------------------------------------------------------------------------
def _year_window(conn: sqlite3.Connection, academic_year_id: int) -> tuple[str, str]:
    cur = conn.execute(
        "SELECT start_date, end_date FROM academic_years WHERE id = ?",
        (academic_year_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"Academic year {academic_year_id} not found.")
    return row[0], row[1]


def write_admission_register(
    target: str | Path, conn: sqlite3.Connection, academic_year_id: int
) -> Path:
    target = Path(target)
    s = _helpers.styles()
    start, end = _year_window(conn, academic_year_id)
    cur = conn.execute(
        """
        SELECT s.admission_no, s.first_name, s.last_name, s.dob, s.gender,
               s.admission_date, s.father_name, s.father_phone, s.class_id
        FROM students s
        WHERE s.admission_date >= ? AND s.admission_date <= ?
        ORDER BY s.admission_date, s.id
        """,
        (start, end),
    )
    rows = cur.fetchall()

    doc = _doc(target, "Admission Register")
    story: list = []
    _helpers.school_header(
        conn,
        story,
        "Admission Register",
        f"Year window: {format_date(start)} to {format_date(end)} ({len(rows)} student(s))",
    )

    if not rows:
        story.append(Paragraph("No admissions in this window.", s["Normal"]))
    else:
        data = [["Adm. Date", "Adm. No.", "Name", "Class", "DOB", "Gender", "Father", "Phone"]]
        for r in rows:
            data.append(
                [
                    format_date(r[5]),
                    r[0],
                    " ".join(filter(None, [r[1], r[2]])),
                    _helpers.class_label(conn, r[8]),
                    format_date(r[3]) if r[3] else "-",
                    r[4] or "-",
                    r[6] or "-",
                    r[7] or "-",
                ]
            )
        table = Table(
            data,
            colWidths=[2.2 * cm, 2.5 * cm, 3.5 * cm, 1.6 * cm, 2 * cm, 1.4 * cm, 3 * cm, 2.2 * cm],
            repeatRows=1,
        )
        table.setStyle(_helpers.DEFAULT_TABLE_STYLE)
        story.append(table)

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# 5. Withdrawal register
# ---------------------------------------------------------------------------
def write_withdrawal_register(
    target: str | Path,
    conn: sqlite3.Connection,
    *,
    academic_year_id: int | None = None,
) -> Path:
    target = Path(target)
    s = _helpers.styles()
    sql = (
        "SELECT s.admission_no, s.first_name, s.last_name, s.status, "
        "       s.admission_date, s.updated_at, s.class_id "
        "FROM students s "
        "WHERE s.status IN ('transferred', 'passed_out', 'inactive')"
    )
    params: list = []
    if academic_year_id is not None:
        start, end = _year_window(conn, academic_year_id)
        sql += " AND s.updated_at >= ? AND s.updated_at <= ?"
        params.extend([f"{start} 00:00:00", f"{end} 23:59:59"])
    sql += " ORDER BY s.updated_at DESC, s.id"
    cur = conn.execute(sql, params)
    rows = cur.fetchall()

    doc = _doc(target, "Withdrawal Register")
    story: list = []
    _helpers.school_header(
        conn,
        story,
        "Withdrawal Register",
        f"{len(rows)} record(s) (status = transferred / passed_out / inactive)",
    )

    if not rows:
        story.append(Paragraph("No withdrawals to show.", s["Normal"]))
    else:
        data = [["Adm. No.", "Name", "Status", "Class", "Adm. Date", "Updated"]]
        for r in rows:
            data.append(
                [
                    r[0],
                    " ".join(filter(None, [r[1], r[2]])),
                    r[3],
                    _helpers.class_label(conn, r[6]),
                    format_date(r[4]) if r[4] else "-",
                    (r[5] or "-")[:10],
                ]
            )
        table = Table(
            data,
            colWidths=[2.5 * cm, 5 * cm, 2.5 * cm, 2 * cm, 2.5 * cm, 2.5 * cm],
            repeatRows=1,
        )
        table.setStyle(_helpers.DEFAULT_TABLE_STYLE)
        story.append(table)

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# 6. Transfer certificate
# ---------------------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class TCFormFields:
    leaving_date: str | None = None  # ISO
    reason: str | None = None
    conduct: str | None = None
    fees_paid: bool = True
    issue_date: str | None = None  # ISO


def _next_doc_no(conn: sqlite3.Connection, prefix: str, year_label: str) -> str:
    """Use the counters table to allocate a sequential certificate number."""
    seq = counters_repo.next_value(conn, f"{prefix}::{year_label}")
    return f"{prefix}/{year_label}/{seq:04d}"


def write_transfer_certificate(
    target: str | Path,
    conn: sqlite3.Connection,
    student_id: int,
    *,
    fields: TCFormFields | None = None,
) -> Path:
    target = Path(target)
    s = _helpers.styles()
    student = student_repo.get(conn, student_id)
    if student is None:
        raise ValueError(f"Student {student_id} not found.")
    active = school_repo.get_active_academic_year(conn)
    year_label = active.label if active else "0000-00"
    fields = fields or TCFormFields()
    issue_date = fields.issue_date or date_cls.today().isoformat()
    tc_no = _next_doc_no(conn, "TC", year_label)

    doc = _doc(target, f"Transfer Certificate {tc_no}")
    story: list = []
    _helpers.school_header(conn, story, "TRANSFER CERTIFICATE")

    story.append(
        Paragraph(
            f"<b>TC No.:</b> {tc_no} &nbsp;&nbsp;&nbsp; "
            f"<b>Issue date:</b> {format_date(issue_date)}",
            s["erp_meta"],
        )
    )

    rows = [
        ("1.", "Name of the student", _helpers.student_full_name(student)),
        ("2.", "Father's name", student.father_name or "-"),
        ("3.", "Mother's name", student.mother_name or "-"),
        ("4.", "Date of birth", format_date(student.dob) if student.dob else "-"),
        ("5.", "Class last attended", _helpers.class_label(conn, student.class_id)),
        (
            "6.",
            "Date of admission",
            format_date(student.admission_date) if student.admission_date else "-",
        ),
        ("7.", "Date of leaving", format_date(fields.leaving_date) if fields.leaving_date else "-"),
        ("8.", "Reason for leaving", fields.reason or "-"),
        ("9.", "Conduct", fields.conduct or "-"),
        ("10.", "Whether all fees have been paid", "Yes" if fields.fees_paid else "No"),
        ("11.", "Aadhaar / ID", student.aadhaar or "-"),
    ]
    table = Table(
        rows,
        colWidths=[1.0 * cm, 6 * cm, 11 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                ("FONT", (1, 0), (1, -1), "Helvetica-Bold", 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.grey),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 1.6 * cm))
    story.append(_helpers.signature_table(["Class teacher", "Principal"]))
    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# 7. Character certificate
# ---------------------------------------------------------------------------
def write_character_certificate(
    target: str | Path,
    conn: sqlite3.Connection,
    student_id: int,
    *,
    conduct: str = "good",
    issue_date: str | None = None,
) -> Path:
    target = Path(target)
    s = _helpers.styles()
    student = student_repo.get(conn, student_id)
    if student is None:
        raise ValueError(f"Student {student_id} not found.")
    active = school_repo.get_active_academic_year(conn)
    year_label = active.label if active else "0000-00"
    issue_date = issue_date or date_cls.today().isoformat()
    cc_no = _next_doc_no(conn, "CC", year_label)

    doc = _doc(target, f"Character Certificate {cc_no}")
    story: list = []
    _helpers.school_header(conn, story, "CHARACTER CERTIFICATE")
    story.append(
        Paragraph(
            f"<b>Ref.:</b> {cc_no} &nbsp;&nbsp;&nbsp; <b>Date:</b> {format_date(issue_date)}",
            s["erp_meta"],
        )
    )
    body = (
        f"This is to certify that <b>{_helpers.student_full_name(student)}</b>, "
        f"son/daughter of {student.father_name or '___'}, bearing admission "
        f"number <b>{student.admission_no}</b>, has been a student of this "
        f"school in class <b>{_helpers.class_label(conn, student.class_id)}</b> "
        f"from {format_date(student.admission_date) if student.admission_date else '___'} "
        f"till date.<br/><br/>"
        f"His/her conduct during this period has been <b>{conduct}</b>.<br/><br/>"
        f"We wish him/her the very best for the future."
    )
    story.append(Paragraph(body, s["erp_body"]))
    story.append(Spacer(1, 2 * cm))
    story.append(_helpers.signature_table(["Class teacher", "Principal"]))
    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# 8. ID card sheet -- 8 cards per A4
# ---------------------------------------------------------------------------
_CARD_WIDTH = 8.5 * cm
_CARD_HEIGHT = 5.4 * cm


def _id_card(conn: sqlite3.Connection, student) -> Table:
    s = _helpers.styles()
    school = school_repo.get_first_school(conn)
    school_name = school.name if school is not None else "School"
    inner = Table(
        [
            [
                _photo(student.photo_path, 2, 2.5),
                Table(
                    [
                        [Paragraph(f"<b>{school_name}</b>", s["erp_small"])],
                        [
                            Paragraph(
                                f"<b>{_helpers.student_full_name(student)}</b>",
                                s["erp_small"],
                            )
                        ],
                        [Paragraph(f"Adm.: {student.admission_no}", s["erp_small"])],
                        [
                            Paragraph(
                                f"Class: {_helpers.class_label(conn, student.class_id)}",
                                s["erp_small"],
                            )
                        ],
                        [Paragraph(f"Blood: {student.blood_group or '-'}", s["erp_small"])],
                        [
                            Paragraph(
                                f"Phone: {student.father_phone or student.guardian_phone or '-'}",
                                s["erp_small"],
                            )
                        ],
                    ],
                    colWidths=[5.5 * cm],
                ),
            ]
        ],
        colWidths=[2.2 * cm, 5.8 * cm],
        rowHeights=[_CARD_HEIGHT - 0.2 * cm],
    )
    inner.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return inner


def write_id_card_sheet(target: str | Path, conn: sqlite3.Connection, class_id: int) -> Path:
    target = Path(target)
    s = _helpers.styles()
    students = student_repo.list_all_for_export(conn, class_id=class_id, status="active")
    doc = _doc(target, "ID Cards")
    story: list = []
    _helpers.school_header(
        conn,
        story,
        "ID Cards",
        f"Class {_helpers.class_label(conn, class_id)} - {len(students)} card(s)",
    )

    if not students:
        story.append(Paragraph("No active students in this class.", s["Normal"]))
    else:
        # Two columns x four rows = 8 per page; reportlab paginates the
        # table automatically when it overflows.
        cells: list = [_id_card(conn, st) for st in students]
        # Pad to a multiple of 2 so the last row is balanced.
        if len(cells) % 2 == 1:
            cells.append(Paragraph("&nbsp;", s["erp_small"]))
        rows: list[list] = [[cells[i], cells[i + 1]] for i in range(0, len(cells), 2)]
        sheet = Table(
            rows,
            colWidths=[_CARD_WIDTH, _CARD_WIDTH],
            rowHeights=[_CARD_HEIGHT] * len(rows),
            repeatRows=0,
        )
        sheet.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(sheet)

    doc.build(story)
    return target
