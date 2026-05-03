from __future__ import annotations

import sqlite3

import pytest

from app.models.people import Student
from app.repositories import student_repo
from app.services import student_service
from app.services.student_service import ImportRow
from app.utils.errors import ValidationError


def _kwargs(**overrides):
    base = dict(
        id=None,
        admission_no="ADM/1",
        first_name="Aarav",
        last_name="Sharma",
        admission_date="2025-04-01",
        gender="m",
        father_phone="98 765-43210",
        pincode="226001",
        aadhaar="1234 5678 9012",
    )
    base.update(overrides)
    return base


def test_create_normalises_inputs(conn: sqlite3.Connection) -> None:
    sid = student_service.create_student(conn, Student(**_kwargs()))
    fetched = student_repo.get(conn, sid)
    assert fetched is not None
    assert fetched.gender == "M"
    # Internal whitespace is stripped from phone numbers; "98 765-43210" → "98765-43210".
    assert fetched.father_phone == "98765-43210"
    assert fetched.aadhaar == "123456789012"  # whitespace stripped


def test_create_rejects_blank_first_name(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        student_service.create_student(conn, Student(**_kwargs(first_name="  ")))
    assert exc.value.field == "first_name"


def test_create_rejects_bad_admission_no(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        student_service.create_student(conn, Student(**_kwargs(admission_no="adm 1!")))
    assert exc.value.field == "admission_no"


def test_create_rejects_bad_dates(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        student_service.create_student(conn, Student(**_kwargs(admission_date="01-04-2025")))
    assert exc.value.field == "admission_date"


def test_create_rejects_duplicate_admission_no(conn: sqlite3.Connection) -> None:
    student_service.create_student(conn, Student(**_kwargs(admission_no="DUP/1")))
    with pytest.raises(ValidationError) as exc:
        student_service.create_student(conn, Student(**_kwargs(admission_no="DUP/1")))
    assert exc.value.field == "admission_no"


def test_create_rejects_bad_pincode(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        student_service.create_student(conn, Student(**_kwargs(pincode="12")))
    assert exc.value.field == "pincode"


def test_create_rejects_bad_aadhaar(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError) as exc:
        student_service.create_student(conn, Student(**_kwargs(aadhaar="abc")))
    assert exc.value.field == "aadhaar"


def test_update_allows_keeping_admission_no(conn: sqlite3.Connection) -> None:
    sid = student_service.create_student(conn, Student(**_kwargs(admission_no="UPD/1")))
    fetched = student_repo.get(conn, sid)
    assert fetched is not None
    from dataclasses import replace

    student_service.update_student(conn, replace(fetched, first_name="Updated"))
    again = student_repo.get(conn, sid)
    assert again is not None
    assert again.first_name == "Updated"


def test_update_blocks_clash_with_other(conn: sqlite3.Connection) -> None:
    a = student_service.create_student(conn, Student(**_kwargs(admission_no="A/1")))
    student_service.create_student(conn, Student(**_kwargs(admission_no="B/1")))
    fetched = student_repo.get(conn, a)
    assert fetched is not None
    from dataclasses import replace

    with pytest.raises(ValidationError):
        student_service.update_student(conn, replace(fetched, admission_no="B/1"))


# ---------------------------------------------------------------------------
# Import rows
# ---------------------------------------------------------------------------
def test_validate_import_row_happy(conn: sqlite3.Connection) -> None:
    seen: set[str] = set()
    row = student_service.validate_import_row(
        conn,
        line=1,
        raw={
            "admission_no": "IMP/1",
            "first_name": "Riya",
            "last_name": "Singh",
            "admission_date": "2025-04-01",
            "gender": "F",
        },
        seen_admission_nos=seen,
    )
    assert row.is_valid
    assert row.student is not None
    assert row.student.admission_no == "IMP/1"
    assert "IMP/1" in seen


def test_validate_import_row_duplicate_within_file(conn: sqlite3.Connection) -> None:
    seen = {"IMP/1"}
    row = student_service.validate_import_row(
        conn,
        line=2,
        raw={"admission_no": "IMP/1", "first_name": "X", "admission_date": "2025-04-01"},
        seen_admission_nos=seen,
    )
    assert not row.is_valid
    assert any("Duplicate" in e for e in row.errors)


def test_validate_import_row_duplicate_in_db(conn: sqlite3.Connection) -> None:
    student_service.create_student(conn, Student(**_kwargs(admission_no="EXIST/1")))
    seen: set[str] = set()
    row = student_service.validate_import_row(
        conn,
        line=1,
        raw={"admission_no": "EXIST/1", "first_name": "X", "admission_date": "2025-04-01"},
        seen_admission_nos=seen,
    )
    assert not row.is_valid
    assert any("already exists" in e for e in row.errors)


def test_commit_import_runs_in_one_transaction(conn: sqlite3.Connection) -> None:
    seen: set[str] = set()
    rows = [
        student_service.validate_import_row(
            conn,
            line=i,
            raw={
                "admission_no": f"BATCH/{i}",
                "first_name": f"Name{i}",
                "admission_date": "2025-04-01",
            },
            seen_admission_nos=seen,
        )
        for i in range(1, 4)
    ]
    inserted = student_service.commit_import(conn, rows)
    assert inserted == 3
    assert student_repo.count(conn) == 3


def test_commit_import_skips_invalid_rows(conn: sqlite3.Connection) -> None:
    seen: set[str] = set()
    rows = [
        ImportRow(line=1, student=None, errors=("bad",), raw={}),
        student_service.validate_import_row(
            conn,
            line=2,
            raw={
                "admission_no": "GOOD/1",
                "first_name": "OK",
                "admission_date": "2025-04-01",
            },
            seen_admission_nos=seen,
        ),
    ]
    inserted = student_service.commit_import(conn, rows)
    assert inserted == 1
    assert student_repo.count(conn) == 1
