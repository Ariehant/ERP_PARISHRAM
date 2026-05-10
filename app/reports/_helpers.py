"""Shared PDF helpers used by every reports module.

Keeps every generator small by centralising the school header, paragraph
styles, signature blocks, and label formatters.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.repositories import class_repo, school_repo


def styles() -> Any:
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("erp_h1", parent=s["Title"], fontSize=16, spaceAfter=2))
    s.add(ParagraphStyle("erp_h2", parent=s["Heading2"], fontSize=12, spaceAfter=4))
    s.add(ParagraphStyle("erp_h3", parent=s["Heading3"], fontSize=10, spaceAfter=2))
    s.add(ParagraphStyle("erp_meta", parent=s["Normal"], fontSize=9, spaceAfter=8))
    s.add(ParagraphStyle("erp_small", parent=s["Normal"], fontSize=8, leading=10))
    s.add(ParagraphStyle("erp_body", parent=s["Normal"], fontSize=10, leading=14))
    s.add(ParagraphStyle("erp_words", parent=s["Normal"], fontSize=9))
    return s


def school_header(
    conn: sqlite3.Connection,
    story: list,
    title: str,
    subtitle: str | None = None,
) -> None:
    """Append school name + address + report title to the story."""
    s = styles()
    school = school_repo.get_first_school(conn)
    if school is not None:
        story.append(Paragraph(school.name, s["erp_h1"]))
        if school.address:
            story.append(Paragraph(school.address, s["erp_meta"]))
    story.append(Paragraph(title, s["erp_h2"]))
    if subtitle:
        story.append(Paragraph(subtitle, s["erp_meta"]))


def class_label(conn: sqlite3.Connection, class_id: int | None) -> str:
    if class_id is None:
        return "(unassigned)"
    cls = class_repo.get_class(conn, class_id)
    if cls is None:
        return f"Class #{class_id}"
    return f"{cls.name}-{cls.section}"


def student_full_name(student) -> str:
    return " ".join(filter(None, [student.first_name, student.last_name]))


def signature_table(labels: list[str], col_width_cm: float = 7.5) -> Table:
    """Signature lines centered under role labels."""
    cols = len(labels) or 1
    table = Table(
        [[""] * cols, labels],
        colWidths=[col_width_cm * cm] * cols,
        rowHeights=[1.4 * cm, 0.6 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.black),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def hr_spacer(height_cm: float = 0.4) -> Spacer:
    return Spacer(1, height_cm * cm)


# Column header / table styles used by most reports.
DEFAULT_TABLE_STYLE = TableStyle(
    [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
    ]
)
