"""PDF generators for attendance reports — daily register, monthly summary,
low-attendance list. All use ``reportlab`` only (no external converters).
"""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date as date_cls
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.repositories import class_repo, school_repo
from app.services import attendance_service
from app.utils.formatters import format_date

_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="erp_h1", parent=s["Title"], fontSize=16, spaceAfter=4))
    s.add(ParagraphStyle(name="erp_h2", parent=s["Heading2"], fontSize=12, spaceAfter=2))
    s.add(ParagraphStyle(name="erp_meta", parent=s["Normal"], fontSize=10, spaceAfter=12))
    s.add(ParagraphStyle(name="erp_footer", parent=s["Normal"], fontSize=10, spaceBefore=18))
    return s


def _header_paragraphs(conn: sqlite3.Connection, title: str, subtitle: str) -> list:
    school = school_repo.get_first_school(conn)
    s = _styles()
    out = []
    if school is not None:
        out.append(Paragraph(school.name, s["erp_h1"]))
        if school.address:
            out.append(Paragraph(school.address, s["erp_meta"]))
    out.append(Paragraph(title, s["erp_h2"]))
    out.append(Paragraph(subtitle, s["erp_meta"]))
    return out


def _signature_block() -> list:
    s = _styles()
    table = Table(
        [["Class teacher", "Principal"], ["", ""]],
        colWidths=[8 * cm, 8 * cm],
        rowHeights=[1.5 * cm, 0.6 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
            ]
        )
    )
    return [Spacer(1, 0.5 * cm), Paragraph("&nbsp;", s["erp_footer"]), table]


def _class_label(conn: sqlite3.Connection, class_id: int) -> str:
    cls = class_repo.get_class(conn, class_id)
    if cls is None:
        return f"Class #{class_id}"
    return f"Class {cls.name}-{cls.section}"


# ---------------------------------------------------------------------------
# Daily register
# ---------------------------------------------------------------------------
def write_daily_register(
    target: str | Path, conn: sqlite3.Connection, class_id: int, date_iso: str
) -> Path:
    target = Path(target)
    rows = attendance_service.daily_register(conn, class_id, date_iso)

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Daily Attendance Register",
    )
    story: list = []
    story.extend(
        _header_paragraphs(
            conn,
            "Daily Attendance Register",
            f"{_class_label(conn, class_id)} &nbsp; • &nbsp; {format_date(date_iso)} ({date_iso})",
        )
    )

    table_data = [["Roll", "Name", "Status"]]
    for r in rows:
        status = r["status"] or "—"
        table_data.append([str(r["roll_no"] or ""), r["name"], status])

    if not rows:
        table_data.append(["", "(no active students in this class)", ""])

    table = Table(
        table_data,
        colWidths=[2 * cm, 11 * cm, 4 * cm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (2, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            "P = Present, A = Absent, L = Late, H = Holiday",
            _styles()["Normal"],
        )
    )
    story.extend(_signature_block())

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# Monthly summary
# ---------------------------------------------------------------------------
def _summary_rows(summaries) -> list[list[str]]:
    table = [["Roll", "Name", "P", "A", "L", "H", "Marked", "%"]]
    for s in summaries:
        pct = f"{s.percentage:.1f}" if s.effective_total > 0 else "—"
        table.append(
            [
                str(s.roll_no or ""),
                s.display_name,
                str(s.p),
                str(s.a),
                str(s.l),
                str(s.h),
                str(s.total_marked),
                pct,
            ]
        )
    return table


def _summary_table_style() -> TableStyle:
    return TableStyle(
        [
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ]
    )


def write_monthly_summary(
    target: str | Path,
    conn: sqlite3.Connection,
    class_id: int,
    year: int,
    month: int,
) -> Path:
    target = Path(target)
    summaries = attendance_service.class_summary(conn, class_id, year, month)
    month_label = f"{_MONTH_NAMES[month - 1]} {year}"

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Monthly Attendance Summary",
    )
    story: list = []
    story.extend(
        _header_paragraphs(
            conn,
            "Monthly Attendance Summary",
            f"{_class_label(conn, class_id)} &nbsp; • &nbsp; {month_label}",
        )
    )

    table_data = _summary_rows(summaries)
    if len(table_data) == 1:
        table_data.append(["—"] * 8)

    table = Table(
        table_data,
        colWidths=[1.5 * cm, 6 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, 1.8 * cm, 1.8 * cm],
        repeatRows=1,
    )
    table.setStyle(_summary_table_style())
    story.append(table)
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            "% = (P + L) / (P + A + L) * 100. Holidays (H) excluded.",
            _styles()["Normal"],
        )
    )
    story.extend(_signature_block())

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# Low-attendance list
# ---------------------------------------------------------------------------
def write_low_attendance(
    target: str | Path,
    conn: sqlite3.Connection,
    class_id: int,
    year: int,
    month: int,
    threshold: float = attendance_service.DEFAULT_LOW_ATTENDANCE_THRESHOLD,
) -> Path:
    target = Path(target)
    summaries = attendance_service.low_attendance(conn, class_id, year, month, threshold=threshold)
    month_label = f"{_MONTH_NAMES[month - 1]} {year}"

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Low Attendance Report",
    )
    story: list = []
    story.extend(
        _header_paragraphs(
            conn,
            f"Low Attendance Report (below {threshold:.0f}%)",
            f"{_class_label(conn, class_id)} &nbsp; • &nbsp; {month_label}",
        )
    )

    table_data = _summary_rows(summaries)
    if len(table_data) == 1:
        table_data.append(["", "(no students below the threshold)", "", "", "", "", "", ""])

    table = Table(
        table_data,
        colWidths=[1.5 * cm, 6 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, 1.8 * cm, 1.8 * cm],
        repeatRows=1,
    )
    table.setStyle(_summary_table_style())
    story.append(table)
    story.extend(_signature_block())

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# Helpers used by the UI
# ---------------------------------------------------------------------------
def days_in_month(year: int, month: int) -> int:
    """Number of days in the given month (1..28/29/30/31)."""
    return calendar.monthrange(year, month)[1]


def today_iso() -> str:
    return date_cls.today().isoformat()
