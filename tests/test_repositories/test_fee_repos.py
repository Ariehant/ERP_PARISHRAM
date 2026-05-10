from __future__ import annotations

import sqlite3

from app.models.fee import FeePayment, FeePaymentItem, FeeStructure
from app.models.school import AcademicYear
from app.models.structure import Class
from app.repositories import (
    class_repo,
    fee_payment_repo,
    fee_structure_repo,
    school_repo,
)


def _seed(conn: sqlite3.Connection) -> tuple[int, int, int]:
    yid = school_repo.create_academic_year(
        conn,
        AcademicYear(
            id=None,
            label="2025-26",
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_active=True,
        ),
    )
    cid = class_repo.create_class(conn, Class(id=None, name="5", section="A", academic_year_id=yid))
    cur = conn.execute(
        "INSERT INTO students (admission_no, first_name, admission_date, class_id, status) "
        "VALUES ('ADM/1', 'A', '2025-04-01', ?, 'active')",
        (cid,),
    )
    sid = int(cur.lastrowid)
    return yid, cid, sid


def test_fee_structure_replace_for_class(conn: sqlite3.Connection) -> None:
    yid, cid, _ = _seed(conn)
    fee_structure_repo.replace_for_class(
        conn,
        cid,
        yid,
        [
            FeeStructure(None, cid, yid, "Tuition", 50000, "monthly", None),
            FeeStructure(None, cid, yid, "Transport", 30000, "monthly", None),
        ],
    )
    rows = fee_structure_repo.list_for_class(conn, cid, yid)
    assert {r.head for r in rows} == {"Tuition", "Transport"}
    tuition = next(r for r in rows if r.head == "Tuition")

    # Update one, drop one, add one.
    fee_structure_repo.replace_for_class(
        conn,
        cid,
        yid,
        [
            FeeStructure(tuition.id, cid, yid, "Tuition", 60000, "monthly", None),
            FeeStructure(None, cid, yid, "Exam", 20000, "annual", None),
        ],
    )
    rows = fee_structure_repo.list_for_class(conn, cid, yid)
    by_head = {r.head: r for r in rows}
    assert set(by_head.keys()) == {"Tuition", "Exam"}
    assert by_head["Tuition"].amount_paise == 60000


def test_payment_total_paid_helpers(conn: sqlite3.Connection) -> None:
    _, _, sid = _seed(conn)
    pid1 = fee_payment_repo.create_payment(
        conn,
        FeePayment(
            id=None,
            student_id=sid,
            receipt_no="RCP/2025-26/00001",
            payment_date="2025-04-15",
            amount_paise=80000,
            mode="cash",
        ),
    )
    fee_payment_repo.create_item(
        conn,
        FeePaymentItem(id=None, fee_payment_id=pid1, head="Tuition", amount_paise=50000),
    )
    fee_payment_repo.create_item(
        conn,
        FeePaymentItem(id=None, fee_payment_id=pid1, head="Transport", amount_paise=30000),
    )
    assert fee_payment_repo.total_paid_for_student(conn, sid) == 80000
    assert fee_payment_repo.total_paid_for_head(conn, sid, "Tuition") == 50000
    assert fee_payment_repo.total_paid_for_head(conn, sid, "Transport") == 30000


def test_list_items_for_student_joins_payment(conn: sqlite3.Connection) -> None:
    _, _, sid = _seed(conn)
    pid = fee_payment_repo.create_payment(
        conn,
        FeePayment(
            id=None,
            student_id=sid,
            receipt_no="RCP/2025-26/00002",
            payment_date="2025-05-01",
            amount_paise=10000,
            mode="upi",
        ),
    )
    fee_payment_repo.create_item(
        conn,
        FeePaymentItem(id=None, fee_payment_id=pid, head="Late fine", amount_paise=10000),
    )
    items = fee_payment_repo.list_items_for_student(conn, sid)
    assert len(items) == 1
    assert items[0]["payment_date"] == "2025-05-01"
    assert items[0]["receipt_no"] == "RCP/2025-26/00002"
    assert items[0]["mode"] == "upi"
    assert items[0]["head"] == "Late fine"
