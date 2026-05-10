from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

from app.models.fee import FeeStructure
from app.models.school import AcademicYear, School
from app.models.structure import Class
from app.repositories import class_repo, school_repo
from app.services import fee_service


def _seed(conn: sqlite3.Connection) -> tuple[int, int]:
    school_repo.create_school(conn, School(id=None, name="Demo School", address="Lucknow"))
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
        "INSERT INTO students (admission_no, first_name, last_name, admission_date, class_id, status) "
        "VALUES ('ADM/1', 'Aarav', 'Sharma', '2025-04-01', ?, 'active')",
        (cid,),
    )
    sid = int(cur.lastrowid)
    fee_service.save_structure(
        conn,
        class_id=cid,
        academic_year_id=yid,
        rows=[
            FeeStructure(None, cid, yid, "Tuition", 50000, "monthly", None),
            FeeStructure(None, cid, yid, "Transport", 30000, "monthly", None),
        ],
    )
    fee_service.collect_payment(
        conn,
        student_id=sid,
        payment_date="2025-04-15",
        mode="cash",
        items=[
            fee_service.PaymentItemInput(head="Tuition", amount_paise=50000),
            fee_service.PaymentItemInput(head="Transport", amount_paise=30000),
        ],
    )
    return cid, sid


def _is_pdf(path: Path) -> bool:
    return path.is_file() and path.read_bytes()[:4] == b"%PDF"


def test_a4_receipt(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, sid = _seed(conn)
    from app.reports.fee_pdf import write_receipt_a4
    from app.repositories import fee_payment_repo

    payment = fee_payment_repo.list_payments_for_student(conn, sid)[0]
    out = write_receipt_a4(tmp_path / "rcp.pdf", conn, payment.id)  # type: ignore[arg-type]
    assert _is_pdf(out)


def test_thermal_receipt(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, sid = _seed(conn)
    from app.reports.fee_pdf import write_receipt_thermal
    from app.repositories import fee_payment_repo

    payment = fee_payment_repo.list_payments_for_student(conn, sid)[0]
    out = write_receipt_thermal(tmp_path / "rcp_t.pdf", conn, payment.id)  # type: ignore[arg-type]
    assert _is_pdf(out)


def test_ledger(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, sid = _seed(conn)
    from app.reports.fee_pdf import write_ledger

    out = write_ledger(tmp_path / "ledger.pdf", conn, sid)
    assert _is_pdf(out)


def test_defaulters(tmp_path: Path, conn: sqlite3.Connection) -> None:
    cid, _ = _seed(conn)
    from app.reports.fee_pdf import write_defaulters

    out = write_defaulters(tmp_path / "def.pdf", conn, cid)
    assert _is_pdf(out)
