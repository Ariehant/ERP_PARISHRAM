"""Verify audit writes happen for the wired services."""

from __future__ import annotations

import sqlite3

from app.models.user import User
from app.repositories import audit_log_repo, user_repo
from app.services import auth_service
from app.utils.security import hash_password


def _seed_admin(conn: sqlite3.Connection) -> None:
    user_repo.create_user(
        conn,
        User(
            id=None,
            username="admin",
            password_hash=hash_password("hunter2x"),
            role="admin",
            full_name="Principal",
            is_active=True,
        ),
    )


def test_login_records_audit_event(conn: sqlite3.Connection) -> None:
    _seed_admin(conn)
    auth_service.authenticate(conn, "admin", "hunter2x")
    rows = audit_log_repo.list_page(conn, action="login")
    assert len(rows) == 1
    assert rows[0]["entity"] == "users"
    assert rows[0]["details"] == "admin"


def test_failed_login_does_not_record(conn: sqlite3.Connection) -> None:
    _seed_admin(conn)
    import pytest

    from app.utils.errors import AuthenticationError

    with pytest.raises(AuthenticationError):
        auth_service.authenticate(conn, "admin", "wrong")
    assert audit_log_repo.count(conn, action="login") == 0


def test_payment_records_audit_event(conn: sqlite3.Connection) -> None:
    """A successful collect_payment writes an audit row."""
    from app.models.school import AcademicYear
    from app.models.structure import Class
    from app.repositories import class_repo, school_repo
    from app.services import fee_service

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
    result = fee_service.collect_payment(
        conn,
        student_id=sid,
        payment_date="2025-05-01",
        mode="cash",
        items=[fee_service.PaymentItemInput(head="Tuition", amount_paise=50000)],
    )
    rows = audit_log_repo.list_page(conn, action="create", entity="fee_payments")
    assert len(rows) == 1
    assert rows[0]["entity_id"] == result.payment_id
    assert "RCP/2025-26/" in (rows[0]["details"] or "")
