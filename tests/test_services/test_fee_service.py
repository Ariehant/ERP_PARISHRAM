from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from app.models.fee import FeeStructure
from app.models.school import AcademicYear
from app.models.structure import Class
from app.repositories import (
    class_repo,
    fee_payment_repo,
    school_repo,
)
from app.services import fee_service
from app.utils.errors import ValidationError


def _seed(conn: sqlite3.Connection, n_students: int = 1) -> tuple[int, int, list[int]]:
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
    sids: list[int] = []
    for i in range(n_students):
        cur = conn.execute(
            "INSERT INTO students (admission_no, first_name, admission_date, class_id, status) "
            "VALUES (?, ?, ?, ?, 'active')",
            (f"ADM/{i + 1:03d}", f"Stu{i + 1:02d}", "2025-04-01", cid),
        )
        sids.append(int(cur.lastrowid))
    return yid, cid, sids


# ---------------------------------------------------------------------------
# Pending calculation
# ---------------------------------------------------------------------------
def test_pending_monthly_first_month(conn: sqlite3.Connection) -> None:
    yid, cid, sids = _seed(conn)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[
            FeeStructure(None, cid, yid, "Tuition", 50000, "monthly", None),
        ],
    )
    pending = fee_service.pending_for_student(conn, sids[0], today=date(2025, 4, 15))
    assert len(pending) == 1
    p = pending[0]
    assert p.instances_due == 1
    assert p.total_due_paise == 50000
    assert p.outstanding_paise == 50000


def test_pending_monthly_six_months_in(conn: sqlite3.Connection) -> None:
    yid, cid, sids = _seed(conn)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[FeeStructure(None, cid, yid, "Tuition", 50000, "monthly", None)],
    )
    pending = fee_service.pending_for_student(conn, sids[0], today=date(2025, 9, 15))
    # Apr, May, Jun, Jul, Aug, Sep -> 6 instances
    assert pending[0].instances_due == 6
    assert pending[0].total_due_paise == 300000


def test_pending_capped_at_year_end(conn: sqlite3.Connection) -> None:
    yid, cid, sids = _seed(conn)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[FeeStructure(None, cid, yid, "Tuition", 50000, "monthly", None)],
    )
    # Today after year end -> capped at 12 instances.
    pending = fee_service.pending_for_student(conn, sids[0], today=date(2027, 1, 1))
    assert pending[0].instances_due == 12


def test_pending_quarterly(conn: sqlite3.Connection) -> None:
    yid, cid, sids = _seed(conn)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[FeeStructure(None, cid, yid, "Activity", 100000, "quarterly", None)],
    )
    # Sep is end of quarter 2 -> 2 instances due.
    pending = fee_service.pending_for_student(conn, sids[0], today=date(2025, 9, 30))
    assert pending[0].instances_due == 2


def test_pending_annual(conn: sqlite3.Connection) -> None:
    yid, cid, sids = _seed(conn)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[
            FeeStructure(None, cid, yid, "Admission fee", 500000, "annual", None),
            FeeStructure(None, cid, yid, "Books", 200000, "one_time", None),
        ],
    )
    pending = fee_service.pending_for_student(conn, sids[0], today=date(2025, 4, 5))
    by_head = {p.head: p for p in pending}
    assert by_head["Admission fee"].instances_due == 1
    assert by_head["Books"].instances_due == 1


def test_pending_after_partial_payment(conn: sqlite3.Connection) -> None:
    yid, cid, sids = _seed(conn)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[FeeStructure(None, cid, yid, "Tuition", 50000, "monthly", None)],
    )
    fee_service.collect_payment(
        conn,
        student_id=sids[0],
        payment_date="2025-04-15",
        mode="cash",
        items=[fee_service.PaymentItemInput(head="Tuition", amount_paise=20000)],
    )
    pending = fee_service.pending_for_student(conn, sids[0], today=date(2025, 4, 20))
    p = pending[0]
    assert p.paid_paise == 20000
    assert p.outstanding_paise == 30000


# ---------------------------------------------------------------------------
# collect_payment
# ---------------------------------------------------------------------------
def test_collect_payment_atomic_receipt_no(conn: sqlite3.Connection) -> None:
    _, _, sids = _seed(conn, n_students=2)
    r1 = fee_service.collect_payment(
        conn,
        student_id=sids[0],
        payment_date="2025-04-15",
        mode="cash",
        items=[fee_service.PaymentItemInput(head="Tuition", amount_paise=50000)],
    )
    r2 = fee_service.collect_payment(
        conn,
        student_id=sids[1],
        payment_date="2025-04-15",
        mode="upi",
        items=[fee_service.PaymentItemInput(head="Tuition", amount_paise=50000)],
    )
    assert r1.receipt_no == "RCP/2025-26/00001"
    assert r2.receipt_no == "RCP/2025-26/00002"
    # Receipts should round-trip via the repo.
    assert fee_payment_repo.get_payment_by_receipt(conn, r1.receipt_no) is not None


def test_collect_payment_writes_items(conn: sqlite3.Connection) -> None:
    _, _, sids = _seed(conn)
    result = fee_service.collect_payment(
        conn,
        student_id=sids[0],
        payment_date="2025-04-15",
        mode="cash",
        items=[
            fee_service.PaymentItemInput(head="Tuition", amount_paise=50000),
            fee_service.PaymentItemInput(head="Transport", amount_paise=30000),
        ],
    )
    items = fee_payment_repo.list_items_for_payment(conn, result.payment_id)
    assert {it.head for it in items} == {"Tuition", "Transport"}
    payment = fee_payment_repo.get_payment(conn, result.payment_id)
    assert payment is not None
    assert payment.amount_paise == 80000


def test_collect_payment_rejects_bad_mode(conn: sqlite3.Connection) -> None:
    _, _, sids = _seed(conn)
    with pytest.raises(ValidationError):
        fee_service.collect_payment(
            conn,
            student_id=sids[0],
            payment_date="2025-04-15",
            mode="paytm",
            items=[fee_service.PaymentItemInput(head="x", amount_paise=100)],
        )


def test_collect_payment_rejects_zero_amount(conn: sqlite3.Connection) -> None:
    _, _, sids = _seed(conn)
    with pytest.raises(ValidationError):
        fee_service.collect_payment(
            conn,
            student_id=sids[0],
            payment_date="2025-04-15",
            mode="cash",
            items=[fee_service.PaymentItemInput(head="x", amount_paise=0)],
        )


def test_collect_payment_rejects_blank_head(conn: sqlite3.Connection) -> None:
    _, _, sids = _seed(conn)
    with pytest.raises(ValidationError):
        fee_service.collect_payment(
            conn,
            student_id=sids[0],
            payment_date="2025-04-15",
            mode="cash",
            items=[fee_service.PaymentItemInput(head="  ", amount_paise=100)],
        )


# ---------------------------------------------------------------------------
# Defaulters
# ---------------------------------------------------------------------------
def test_defaulters_list(conn: sqlite3.Connection) -> None:
    yid, cid, sids = _seed(conn, n_students=3)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[FeeStructure(None, cid, yid, "Tuition", 50000, "monthly", None)],
    )
    # Pay full for student 0 in Apr.
    fee_service.collect_payment(
        conn,
        student_id=sids[0],
        payment_date="2025-04-15",
        mode="cash",
        items=[fee_service.PaymentItemInput(head="Tuition", amount_paise=50000)],
    )
    # Student 1 pays partial.
    fee_service.collect_payment(
        conn,
        student_id=sids[1],
        payment_date="2025-04-15",
        mode="cash",
        items=[fee_service.PaymentItemInput(head="Tuition", amount_paise=20000)],
    )
    # Student 2 pays nothing.

    defaulters = fee_service.defaulters_for_class(conn, cid, today=date(2025, 4, 20))
    by_id = {d.student_id: d for d in defaulters}
    # Student 0 fully paid -> not a defaulter.
    assert sids[0] not in by_id
    assert by_id[sids[1]].outstanding_paise == 30000
    assert by_id[sids[2]].outstanding_paise == 50000


# ---------------------------------------------------------------------------
# Structure validation
# ---------------------------------------------------------------------------
def test_save_structure_rejects_bad_frequency(conn: sqlite3.Connection) -> None:
    yid, cid, _ = _seed(conn)
    with pytest.raises(ValidationError):
        fee_service.save_structure(
            conn,
            class_id=cid,
            academic_year_id=yid,
            rows=[FeeStructure(None, cid, yid, "x", 100, "weekly", None)],
        )


def test_save_structure_rejects_negative_amount(conn: sqlite3.Connection) -> None:
    yid, cid, _ = _seed(conn)
    with pytest.raises(ValidationError):
        fee_service.save_structure(
            conn,
            class_id=cid,
            academic_year_id=yid,
            rows=[FeeStructure(None, cid, yid, "x", -1, "monthly", None)],
        )


def test_save_structure_rejects_duplicate(conn: sqlite3.Connection) -> None:
    yid, cid, _ = _seed(conn)
    with pytest.raises(ValidationError):
        fee_service.save_structure(
            conn,
            class_id=cid,
            academic_year_id=yid,
            rows=[
                FeeStructure(None, cid, yid, "Tuition", 100, "monthly", None),
                FeeStructure(None, cid, yid, "tuition", 100, "monthly", None),
            ],
        )
