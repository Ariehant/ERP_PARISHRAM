"""Fee PDF generators -- A4 receipt, 80mm thermal receipt, ledger, defaulters."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.repositories import (
    class_repo,
    fee_payment_repo,
    school_repo,
    student_repo,
)
from app.services import fee_service
from app.utils.formatters import format_date, format_inr
from app.utils.inr_words import paise_to_words


# ---------------------------------------------------------------------------
# Styles + shared helpers
# ---------------------------------------------------------------------------
def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("erp_h1", parent=s["Title"], fontSize=16, spaceAfter=2))
    s.add(ParagraphStyle("erp_h2", parent=s["Heading2"], fontSize=12, spaceAfter=4))
    s.add(ParagraphStyle("erp_meta", parent=s["Normal"], fontSize=9, spaceAfter=8))
    s.add(ParagraphStyle("erp_words", parent=s["Normal"], fontSize=9, italic=True))
    s.add(ParagraphStyle("erp_thermal", parent=s["Normal"], fontSize=8, leading=10))
    s.add(
        ParagraphStyle(
            "erp_thermal_h",
            parent=s["Normal"],
            fontSize=11,
            leading=13,
            alignment=1,  # center
        )
    )
    return s


def _student_label(student) -> str:
    return " ".join(filter(None, [student.first_name, student.last_name]))


def _class_label(conn: sqlite3.Connection, class_id: int | None) -> str:
    if class_id is None:
        return "(unassigned)"
    cls = class_repo.get_class(conn, class_id)
    if cls is None:
        return f"Class #{class_id}"
    return f"{cls.name}-{cls.section}"


# ---------------------------------------------------------------------------
# Receipt -- A4
# ---------------------------------------------------------------------------
def write_receipt_a4(target: str | Path, conn: sqlite3.Connection, payment_id: int) -> Path:
    target = Path(target)
    payment = fee_payment_repo.get_payment(conn, payment_id)
    if payment is None:
        raise ValueError(f"Payment {payment_id} not found.")
    items = fee_payment_repo.list_items_for_payment(conn, payment_id)
    student = student_repo.get(conn, payment.student_id)
    if student is None:
        raise ValueError(f"Student {payment.student_id} not found.")
    school = school_repo.get_first_school(conn)
    s = _styles()

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Fee Receipt {payment.receipt_no}",
    )
    story: list = []

    if school is not None:
        story.append(Paragraph(school.name, s["erp_h1"]))
        if school.address:
            story.append(Paragraph(school.address, s["erp_meta"]))
    story.append(Paragraph("Fee Receipt", s["erp_h2"]))

    meta_table = Table(
        [
            [
                "Receipt No.",
                payment.receipt_no,
                "Date",
                format_date(payment.payment_date),
            ],
            [
                "Admission No.",
                student.admission_no,
                "Class",
                _class_label(conn, student.class_id),
            ],
            ["Student", _student_label(student), "Mode", payment.mode.upper()],
            [
                "Father / Guardian",
                student.father_name or student.guardian_name or "",
                "Reference",
                payment.reference_no or "",
            ],
        ],
        colWidths=[3.5 * cm, 6 * cm, 2.5 * cm, 5 * cm],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
                ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.4 * cm))

    item_data = [["Head", "For", "Amount"]]
    for it in items:
        when_parts: list[str] = []
        if it.for_month is not None:
            try:
                month_label = "JanFebMarAprMayJunJulAugSepOctNovDec"[
                    (it.for_month - 1) * 3 : it.for_month * 3
                ]
                when_parts.append(month_label)
            except IndexError:
                when_parts.append(str(it.for_month))
        if it.for_year is not None:
            when_parts.append(str(it.for_year))
        item_data.append(
            [
                it.head,
                " ".join(when_parts) if when_parts else "-",
                format_inr(it.amount_paise),
            ]
        )
    item_data.append(["", "Total", format_inr(payment.amount_paise)])

    item_table = Table(
        item_data,
        colWidths=[8 * cm, 4 * cm, 5 * cm],
    )
    last_row = len(item_data) - 1
    item_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                ("FONT", (0, 1), (-1, -2), "Helvetica", 10),
                ("FONT", (0, last_row), (-1, last_row), "Helvetica-Bold", 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, last_row), (-1, last_row), colors.HexColor("#f0f0f0")),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -2), 0.4, colors.grey),
                ("LINEABOVE", (0, last_row), (-1, last_row), 0.6, colors.black),
            ]
        )
    )
    story.append(item_table)

    story.append(Spacer(1, 0.3 * cm))
    story.append(
        Paragraph(
            f"<b>Total in words:</b> {paise_to_words(payment.amount_paise)}",
            s["erp_words"],
        )
    )
    if payment.remarks:
        story.append(Paragraph(f"<b>Remarks:</b> {payment.remarks}", s["erp_meta"]))

    story.append(Spacer(1, 1.2 * cm))
    sig = Table(
        [["", ""], ["Cashier", "Authorised Signatory"]],
        colWidths=[8 * cm, 8 * cm],
        rowHeights=[1.5 * cm, 0.6 * cm],
    )
    sig.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.black),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
            ]
        )
    )
    story.append(sig)

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# Receipt -- 80mm thermal
# ---------------------------------------------------------------------------
_THERMAL_PAGE = (80 * mm, 200 * mm)


def write_receipt_thermal(target: str | Path, conn: sqlite3.Connection, payment_id: int) -> Path:
    target = Path(target)
    payment = fee_payment_repo.get_payment(conn, payment_id)
    if payment is None:
        raise ValueError(f"Payment {payment_id} not found.")
    items = fee_payment_repo.list_items_for_payment(conn, payment_id)
    student = student_repo.get(conn, payment.student_id)
    if student is None:
        raise ValueError(f"Student {payment.student_id} not found.")
    school = school_repo.get_first_school(conn)

    s = _styles()
    doc = SimpleDocTemplate(
        str(target),
        pagesize=_THERMAL_PAGE,
        leftMargin=4 * mm,
        rightMargin=4 * mm,
        topMargin=4 * mm,
        bottomMargin=4 * mm,
        title=f"Receipt {payment.receipt_no}",
    )
    story: list = []
    if school is not None:
        story.append(Paragraph(school.name, s["erp_thermal_h"]))
        if school.address:
            story.append(Paragraph(school.address, s["erp_thermal"]))
    story.append(
        Paragraph(
            f"Receipt: <b>{payment.receipt_no}</b><br/>"
            f"Date: {format_date(payment.payment_date)}<br/>"
            f"Mode: {payment.mode.upper()}",
            s["erp_thermal"],
        )
    )
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f"Student: {_student_label(student)}<br/>"
            f"Adm. No.: {student.admission_no}<br/>"
            f"Class: {_class_label(conn, student.class_id)}",
            s["erp_thermal"],
        )
    )
    story.append(Spacer(1, 2 * mm))

    item_rows = [["Head", "Amt"]]
    for it in items:
        item_rows.append([it.head, format_inr(it.amount_paise, with_symbol=False)])
    item_rows.append(["TOTAL", format_inr(payment.amount_paise, with_symbol=False)])
    last = len(item_rows) - 1
    item_table = Table(item_rows, colWidths=[44 * mm, 24 * mm])
    item_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
                ("FONT", (0, last), (-1, last), "Helvetica-Bold", 8),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (0, last), (-1, last), 0.4, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.black),
            ]
        )
    )
    story.append(item_table)
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f"<i>{paise_to_words(payment.amount_paise)}</i>",
            s["erp_thermal"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("------ Cashier signature ------", s["erp_thermal"]))
    story.append(Paragraph("Thank you!", s["erp_thermal_h"]))

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# Student fee ledger
# ---------------------------------------------------------------------------
def write_ledger(target: str | Path, conn: sqlite3.Connection, student_id: int) -> Path:
    target = Path(target)
    student = student_repo.get(conn, student_id)
    if student is None:
        raise ValueError(f"Student {student_id} not found.")
    items = fee_payment_repo.list_items_for_student(conn, student_id)
    pending = fee_service.pending_for_student(conn, student_id)
    school = school_repo.get_first_school(conn)
    s = _styles()

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Fee Ledger - {_student_label(student)}",
    )
    story: list = []
    if school is not None:
        story.append(Paragraph(school.name, s["erp_h1"]))
        if school.address:
            story.append(Paragraph(school.address, s["erp_meta"]))
    story.append(Paragraph("Student fee ledger", s["erp_h2"]))
    story.append(
        Paragraph(
            f"<b>Student:</b> {_student_label(student)} &nbsp; - &nbsp; "
            f"<b>Adm. No.:</b> {student.admission_no} &nbsp; - &nbsp; "
            f"<b>Class:</b> {_class_label(conn, student.class_id)}",
            s["erp_meta"],
        )
    )

    if not items:
        story.append(Paragraph("No payments recorded yet.", s["Normal"]))
    else:
        ledger_rows = [["Date", "Receipt", "Mode", "Head", "Amount"]]
        for it in items:
            ledger_rows.append(
                [
                    format_date(it["payment_date"]),
                    it["receipt_no"],
                    it["mode"].upper(),
                    it["head"],
                    format_inr(it["amount_paise"]),
                ]
            )
        total_paid = sum(it["amount_paise"] for it in items)
        ledger_rows.append(["", "", "", "Total paid", format_inr(total_paid)])

        last = len(ledger_rows) - 1
        ledger_table = Table(
            ledger_rows,
            colWidths=[2.5 * cm, 4 * cm, 2 * cm, 5 * cm, 3.5 * cm],
            repeatRows=1,
        )
        ledger_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                    ("FONT", (0, 1), (-1, -2), "Helvetica", 10),
                    ("FONT", (0, last), (-1, last), "Helvetica-Bold", 10),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -2), 0.4, colors.grey),
                    ("LINEABOVE", (0, last), (-1, last), 0.6, colors.black),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -2),
                        [colors.white, colors.HexColor("#f5f7fa")],
                    ),
                ]
            )
        )
        story.append(ledger_table)

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Outstanding by head", s["erp_h2"]))
    if not pending:
        story.append(Paragraph("No fee structure configured for this class.", s["Normal"]))
    else:
        outstanding_rows = [["Head", "Frequency", "Due", "Paid", "Outstanding"]]
        total_out = 0
        for p in pending:
            outstanding_rows.append(
                [
                    p.head,
                    p.frequency,
                    format_inr(p.total_due_paise),
                    format_inr(p.paid_paise),
                    format_inr(p.outstanding_paise),
                ]
            )
            total_out += p.outstanding_paise
        outstanding_rows.append(["", "", "", "Total outstanding", format_inr(total_out)])
        last = len(outstanding_rows) - 1
        out_table = Table(
            outstanding_rows,
            colWidths=[5 * cm, 2.5 * cm, 3 * cm, 3 * cm, 3.5 * cm],
            repeatRows=1,
        )
        out_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                    ("FONT", (0, 1), (-1, -2), "Helvetica", 10),
                    ("FONT", (0, last), (-1, last), "Helvetica-Bold", 10),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -2), 0.4, colors.grey),
                    ("LINEABOVE", (0, last), (-1, last), 0.6, colors.black),
                ]
            )
        )
        story.append(out_table)

    doc.build(story)
    return target


# ---------------------------------------------------------------------------
# Defaulters report
# ---------------------------------------------------------------------------
def write_defaulters(target: str | Path, conn: sqlite3.Connection, class_id: int) -> Path:
    target = Path(target)
    school = school_repo.get_first_school(conn)
    rows = fee_service.defaulters_for_class(conn, class_id)
    s = _styles()

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Fee Defaulters",
    )
    story: list = []
    if school is not None:
        story.append(Paragraph(school.name, s["erp_h1"]))
        if school.address:
            story.append(Paragraph(school.address, s["erp_meta"]))
    story.append(Paragraph("Fee Defaulters", s["erp_h2"]))
    story.append(
        Paragraph(
            f"<b>Class:</b> {_class_label(conn, class_id)} &nbsp; - &nbsp; "
            f"<b>As of:</b> {format_date(__import__('datetime').date.today().isoformat())}",
            s["erp_meta"],
        )
    )

    if not rows:
        story.append(Paragraph("No defaulters in this class.", s["Normal"]))
    else:
        table_data = [["Adm. No.", "Name", "Outstanding"]]
        total = 0
        for r in rows:
            table_data.append([r.admission_no, r.name, format_inr(r.outstanding_paise)])
            total += r.outstanding_paise
        table_data.append(["", "Total", format_inr(total)])
        last = len(table_data) - 1
        table = Table(
            table_data,
            colWidths=[3.5 * cm, 9 * cm, 4 * cm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                    ("FONT", (0, 1), (-1, -2), "Helvetica", 10),
                    ("FONT", (0, last), (-1, last), "Helvetica-Bold", 10),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -2), 0.4, colors.grey),
                    ("LINEABOVE", (0, last), (-1, last), 0.6, colors.black),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -2),
                        [colors.white, colors.HexColor("#f5f7fa")],
                    ),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    return target
