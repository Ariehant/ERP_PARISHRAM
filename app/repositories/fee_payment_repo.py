"""Fee payment repository (header + items)."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.models.fee import FeePayment, FeePaymentItem


def _row_to_payment(row: sqlite3.Row) -> FeePayment:
    return FeePayment(
        id=row["id"],
        student_id=row["student_id"],
        receipt_no=row["receipt_no"],
        payment_date=row["payment_date"],
        amount_paise=row["amount_paise"],
        mode=row["mode"],
        reference_no=row["reference_no"],
        remarks=row["remarks"],
        collected_by=row["collected_by"],
        created_at=row["created_at"],
    )


def _row_to_item(row: sqlite3.Row) -> FeePaymentItem:
    return FeePaymentItem(
        id=row["id"],
        fee_payment_id=row["fee_payment_id"],
        fee_structure_id=row["fee_structure_id"],
        head=row["head"],
        amount_paise=row["amount_paise"],
        for_month=row["for_month"],
        for_year=row["for_year"],
    )


_PAY_COLS = (
    "id, student_id, receipt_no, payment_date, amount_paise, mode, "
    "reference_no, remarks, collected_by, created_at"
)
_ITEM_COLS = "id, fee_payment_id, fee_structure_id, head, amount_paise, for_month, for_year"


def create_payment(conn: sqlite3.Connection, p: FeePayment) -> int:
    cur = conn.execute(
        """
        INSERT INTO fee_payments
            (student_id, receipt_no, payment_date, amount_paise, mode,
             reference_no, remarks, collected_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            p.student_id,
            p.receipt_no,
            p.payment_date,
            p.amount_paise,
            p.mode,
            p.reference_no,
            p.remarks,
            p.collected_by,
        ),
    )
    return int(cur.lastrowid)


def create_item(conn: sqlite3.Connection, item: FeePaymentItem) -> int:
    cur = conn.execute(
        """
        INSERT INTO fee_payment_items
            (fee_payment_id, fee_structure_id, head, amount_paise, for_month, for_year)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            item.fee_payment_id,
            item.fee_structure_id,
            item.head,
            item.amount_paise,
            item.for_month,
            item.for_year,
        ),
    )
    return int(cur.lastrowid)


def get_payment(conn: sqlite3.Connection, payment_id: int) -> FeePayment | None:
    cur = conn.execute(f"SELECT {_PAY_COLS} FROM fee_payments WHERE id = ?", (payment_id,))
    row = cur.fetchone()
    return _row_to_payment(row) if row else None


def get_payment_by_receipt(conn: sqlite3.Connection, receipt_no: str) -> FeePayment | None:
    cur = conn.execute(f"SELECT {_PAY_COLS} FROM fee_payments WHERE receipt_no = ?", (receipt_no,))
    row = cur.fetchone()
    return _row_to_payment(row) if row else None


def list_payments_for_student(conn: sqlite3.Connection, student_id: int) -> list[FeePayment]:
    cur = conn.execute(
        f"SELECT {_PAY_COLS} FROM fee_payments WHERE student_id = ? ORDER BY payment_date, id",
        (student_id,),
    )
    return [_row_to_payment(r) for r in cur.fetchall()]


def list_items_for_payment(conn: sqlite3.Connection, payment_id: int) -> list[FeePaymentItem]:
    cur = conn.execute(
        f"SELECT {_ITEM_COLS} FROM fee_payment_items WHERE fee_payment_id = ? ORDER BY id",
        (payment_id,),
    )
    return [_row_to_item(r) for r in cur.fetchall()]


def list_items_for_student(conn: sqlite3.Connection, student_id: int) -> list[dict[str, Any]]:
    """Items joined to their parent payment so callers see ``payment_date``."""
    cur = conn.execute(
        """
        SELECT fpi.id, fpi.fee_payment_id, fpi.fee_structure_id, fpi.head,
               fpi.amount_paise, fpi.for_month, fpi.for_year,
               fp.payment_date, fp.receipt_no, fp.mode
        FROM fee_payment_items fpi
        INNER JOIN fee_payments fp ON fp.id = fpi.fee_payment_id
        WHERE fp.student_id = ?
        ORDER BY fp.payment_date, fp.id, fpi.id
        """,
        (student_id,),
    )
    return [
        {
            "id": r[0],
            "fee_payment_id": r[1],
            "fee_structure_id": r[2],
            "head": r[3],
            "amount_paise": r[4],
            "for_month": r[5],
            "for_year": r[6],
            "payment_date": r[7],
            "receipt_no": r[8],
            "mode": r[9],
        }
        for r in cur.fetchall()
    ]


def total_paid_for_head(conn: sqlite3.Connection, student_id: int, head: str) -> int:
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(fpi.amount_paise), 0)
        FROM fee_payment_items fpi
        INNER JOIN fee_payments fp ON fp.id = fpi.fee_payment_id
        WHERE fp.student_id = ? AND fpi.head = ?
        """,
        (student_id, head),
    )
    return int(cur.fetchone()[0])


def total_paid_for_student(conn: sqlite3.Connection, student_id: int) -> int:
    cur = conn.execute(
        "SELECT COALESCE(SUM(amount_paise), 0) FROM fee_payments WHERE student_id = ?",
        (student_id,),
    )
    return int(cur.fetchone()[0])
