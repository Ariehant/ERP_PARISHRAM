"""Report-card PDF -- single student or whole class.

The single-student version produces a compact one-page card with a marks
matrix (rows = subjects, columns = each exam in the active year), an
overall total, attendance % for the year, grade, and signature lines. The
batch version is the same template repeated for every active student in
the chosen class, in one PDF.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.reports import _helpers
from app.repositories import (
    class_repo,
    exam_repo,
    mark_repo,
    school_repo,
    student_repo,
)
from app.services import grade_scale_service
from app.utils.formatters import format_date


def _safe_image(path: str | None, width_cm: float, height_cm: float):
    if not path:
        return Paragraph("(no photo)", _helpers.styles()["erp_small"])
    p = Path(path)
    if not p.is_file():
        return Paragraph("(missing photo)", _helpers.styles()["erp_small"])
    try:
        return Image(str(p), width=width_cm * cm, height=height_cm * cm, kind="proportional")
    except Exception:
        return Paragraph("(bad photo)", _helpers.styles()["erp_small"])


def _attendance_summary(
    conn: sqlite3.Connection, student_id: int, year_start: str, year_end: str
) -> tuple[int, int, int, int, float]:
    """Sum P/A/L/H across the academic year for one student.

    Returns ``(p, a, l, h, percent)``. The percentage uses the
    ``(P + L) / (P + A + L)`` convention shared with attendance reports.
    """
    cur = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN status='P' THEN 1 ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN status='A' THEN 1 ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN status='L' THEN 1 ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN status='H' THEN 1 ELSE 0 END), 0)
        FROM attendance
        WHERE student_id = ? AND date >= ? AND date <= ?
        """,
        (student_id, year_start, year_end),
    )
    p, a, lt, h = (int(x) for x in cur.fetchone())
    effective = p + a + lt
    pct = ((p + lt) / effective * 100.0) if effective else 0.0
    return p, a, lt, h, pct


def _build_one_card(conn: sqlite3.Connection, student_id: int) -> list:
    s = _helpers.styles()
    student = student_repo.get(conn, student_id)
    if student is None:
        return [Paragraph(f"Student #{student_id} not found.", s["Normal"])]
    active = school_repo.get_active_academic_year(conn)
    if active is None or active.id is None:
        return [Paragraph("No active academic year configured.", s["Normal"])]

    story: list = []
    _helpers.school_header(
        conn,
        story,
        "Report Card",
        f"Academic year: {active.label}",
    )

    # Student row: photo + identity table.
    photo = _safe_image(student.photo_path, 2.6, 3.4)
    identity_rows = [
        ["Name", _helpers.student_full_name(student), "Adm. No.", student.admission_no],
        [
            "Class",
            _helpers.class_label(conn, student.class_id),
            "Roll No.",
            str(student.roll_no or "-"),
        ],
        ["DOB", format_date(student.dob) if student.dob else "-", "Gender", student.gender or "-"],
        ["Father", student.father_name or "-", "Mother", student.mother_name or "-"],
    ]
    identity_table = Table(
        identity_rows,
        colWidths=[2.4 * cm, 5.5 * cm, 2.4 * cm, 4.5 * cm],
    )
    identity_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    header_row = Table(
        [[photo, identity_table]],
        colWidths=[3 * cm, 14.8 * cm],
    )
    header_row.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (1, 0), (1, 0), 6)])
    )
    story.append(header_row)
    story.append(_helpers.hr_spacer(0.3))

    # Marks matrix.
    if student.class_id is not None:
        subjects = class_repo.list_subjects_for_class(conn, student.class_id)
    else:
        subjects = []
    exams = exam_repo.list_for_year(conn, active.id)
    if not exams or not subjects:
        story.append(
            Paragraph(
                "No exams or subjects configured -- marks table omitted.",
                s["erp_meta"],
            )
        )
    else:
        # Pre-fetch every mark row for this student in this year (one query
        # per exam keeps the code simple; class is small).
        per_exam_marks: dict[int, dict[int, dict]] = {}
        for e in exams:
            if e.id is None:
                continue
            rows = mark_repo.list_for_student_in_exam(conn, student_id, e.id)
            per_exam_marks[e.id] = {r.subject_id: r for r in rows}

        # Header row: blank | <Exam 1 marks/max> | <Exam 2 marks/max> ... | Total
        header = ["Subject"]
        for e in exams:
            header.append(f"{e.name}\n(marks / grade)")
        header.append("Total")
        data: list[list[str]] = [header]

        per_exam_totals = [0] * len(exams)
        per_exam_max = [0] * len(exams)
        for sub in subjects:
            row: list[str] = [sub.name]
            student_total = 0
            student_max = 0
            for i, e in enumerate(exams):
                cell = per_exam_marks.get(e.id, {}).get(sub.id) if e.id else None
                if cell is None or cell.marks_obtained is None:
                    row.append("-")
                    continue
                row.append(
                    f"{cell.marks_obtained:g} / {cell.max_marks}"
                    + (f" ({cell.grade})" if cell.grade else "")
                )
                student_total += int(cell.marks_obtained)
                student_max += int(cell.max_marks)
                per_exam_totals[i] += int(cell.marks_obtained)
                per_exam_max[i] += int(cell.max_marks)
            row.append(f"{student_total} / {student_max}" if student_max else "-")
            data.append(row)

        # Class-aggregate row (optional).
        totals_row = ["Exam totals"]
        overall_obtained = 0
        overall_max = 0
        for got, mx in zip(per_exam_totals, per_exam_max, strict=False):
            totals_row.append(f"{got} / {mx}" if mx else "-")
            overall_obtained += got
            overall_max += mx
        totals_row.append(f"{overall_obtained} / {overall_max}" if overall_max else "-")
        data.append(totals_row)

        marks_table = Table(
            data,
            colWidths=[4 * cm, *([3 * cm] * len(exams)), 3 * cm][: 1 + len(exams) + 1],
            repeatRows=1,
        )
        last = len(data) - 1
        marks_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                    ("FONT", (0, 1), (-1, -2), "Helvetica", 9),
                    ("FONT", (0, last), (-1, last), "Helvetica-Bold", 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -2), 0.4, colors.grey),
                    ("LINEABOVE", (0, last), (-1, last), 0.6, colors.black),
                ]
            )
        )
        story.append(marks_table)

        if overall_max:
            pct = (overall_obtained / overall_max) * 100.0
            grade = grade_scale_service.grade_for_percent(conn, pct) or "-"
            story.append(_helpers.hr_spacer(0.3))
            story.append(
                Paragraph(
                    f"<b>Overall:</b> {overall_obtained} / {overall_max} "
                    f"({pct:.2f}%) &nbsp; - &nbsp; <b>Grade:</b> {grade}",
                    s["erp_body"],
                )
            )

    # Attendance line.
    p, a, lt, h, pct = _attendance_summary(conn, student_id, active.start_date, active.end_date)
    story.append(
        Paragraph(
            f"<b>Attendance:</b> P={p}  A={a}  L={lt}  H={h} &nbsp; - &nbsp; "
            f"<b>{pct:.1f}%</b> (year-to-date, holidays excluded)",
            s["erp_body"],
        )
    )

    story.append(_helpers.hr_spacer(0.4))
    story.append(Paragraph("<b>Class teacher remarks:</b>", s["erp_body"]))
    story.append(Spacer(1, 1.0 * cm))
    story.append(_helpers.signature_table(["Class teacher", "Principal"]))
    return story


def write_report_card(target: str | Path, conn: sqlite3.Connection, student_id: int) -> Path:
    target = Path(target)
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Report Card",
    )
    doc.build(_build_one_card(conn, student_id))
    return target


def write_class_report_cards(target: str | Path, conn: sqlite3.Connection, class_id: int) -> Path:
    """One PDF, one student per page."""
    target = Path(target)
    students = student_repo.list_all_for_export(conn, class_id=class_id, status="active")
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Report Cards (class batch)",
    )
    story: list = []
    if not students:
        s = _helpers.styles()
        _helpers.school_header(conn, story, "Report Cards", _helpers.class_label(conn, class_id))
        story.append(Paragraph("No active students in this class.", s["Normal"]))
    else:
        for i, student in enumerate(students):
            if student.id is None:
                continue
            story.extend(_build_one_card(conn, student.id))
            if i < len(students) - 1:
                story.append(PageBreak())
    doc.build(story)
    return target
