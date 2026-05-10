"""Smoke tests for the Phase-7 PDF generators.

We verify the magic bytes only; rendering correctness is for the manual
checklist. Each generator must accept the empty-data case without raising.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

from app.models.exam import Exam
from app.models.school import AcademicYear, School
from app.models.structure import Class, Subject
from app.repositories import class_repo, exam_repo, school_repo
from app.services import mark_service


def _seed(conn: sqlite3.Connection) -> tuple[int, int, int, int]:
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
    s1 = class_repo.create_subject(conn, Subject(id=None, name="Math", class_id=cid, max_marks=100))
    class_repo.create_subject(conn, Subject(id=None, name="English", class_id=cid, max_marks=80))
    eid = exam_repo.create(conn, Exam(id=None, name="Mid-term", academic_year_id=yid))
    cur = conn.execute(
        "INSERT INTO students (admission_no, first_name, last_name, admission_date, class_id, status, roll_no) "
        "VALUES ('ADM/1', 'Aarav', 'Sharma', '2025-04-01', ?, 'active', 1)",
        (cid,),
    )
    sid = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO students (admission_no, first_name, last_name, admission_date, class_id, status, roll_no) "
        "VALUES ('ADM/2', 'Riya', 'Singh', '2025-04-01', ?, 'active', 2)",
        (cid,),
    )
    sid2 = int(cur.lastrowid)
    # Some marks for Aarav.
    mark_service.save_class_exam_marks(
        conn,
        class_id=cid,
        exam_id=eid,
        inputs=[
            mark_service.MarkInput(student_id=sid, subject_id=s1, marks_obtained=85.0),
        ],
    )
    return cid, eid, sid, sid2, yid  # type: ignore[return-value]


def _is_pdf(path: Path) -> bool:
    return path.is_file() and path.read_bytes()[:4] == b"%PDF"


def test_report_card_single(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, _, sid, _, _ = _seed(conn)
    from app.reports.report_card_pdf import write_report_card

    out = write_report_card(tmp_path / "rc.pdf", conn, sid)
    assert _is_pdf(out)


def test_report_card_batch(tmp_path: Path, conn: sqlite3.Connection) -> None:
    cid, _, _, _, _ = _seed(conn)
    from app.reports.report_card_pdf import write_class_report_cards

    out = write_class_report_cards(tmp_path / "rcb.pdf", conn, cid)
    assert _is_pdf(out)


def test_profile(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, _, sid, _, _ = _seed(conn)
    from app.reports.general_pdfs import write_profile

    out = write_profile(tmp_path / "p.pdf", conn, sid)
    assert _is_pdf(out)


def test_class_roster(tmp_path: Path, conn: sqlite3.Connection) -> None:
    cid, _, _, _, _ = _seed(conn)
    from app.reports.general_pdfs import write_class_roster

    out = write_class_roster(tmp_path / "roster.pdf", conn, cid)
    assert _is_pdf(out)


def test_mark_sheet(tmp_path: Path, conn: sqlite3.Connection) -> None:
    cid, eid, _, _, _ = _seed(conn)
    from app.reports.general_pdfs import write_mark_sheet

    out = write_mark_sheet(tmp_path / "ms.pdf", conn, cid, eid)
    assert _is_pdf(out)


def test_admission_register(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, _, _, _, yid = _seed(conn)
    from app.reports.general_pdfs import write_admission_register

    out = write_admission_register(tmp_path / "ar.pdf", conn, yid)
    assert _is_pdf(out)


def test_withdrawal_register_empty(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, _, _, _, yid = _seed(conn)
    from app.reports.general_pdfs import write_withdrawal_register

    # No withdrawn students yet -> still produces a valid PDF.
    out = write_withdrawal_register(tmp_path / "wr.pdf", conn, academic_year_id=yid)
    assert _is_pdf(out)


def test_transfer_certificate(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, _, sid, _, _ = _seed(conn)
    from app.reports.general_pdfs import TCFormFields, write_transfer_certificate

    fields = TCFormFields(
        leaving_date="2026-03-31",
        reason="Family relocation",
        conduct="excellent",
        fees_paid=True,
    )
    out = write_transfer_certificate(tmp_path / "tc.pdf", conn, sid, fields=fields)
    assert _is_pdf(out)


def test_character_certificate(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _, _, sid, _, _ = _seed(conn)
    from app.reports.general_pdfs import write_character_certificate

    out = write_character_certificate(tmp_path / "cc.pdf", conn, sid, conduct="excellent")
    assert _is_pdf(out)


def test_id_card_sheet(tmp_path: Path, conn: sqlite3.Connection) -> None:
    cid, _, _, _, _ = _seed(conn)
    from app.reports.general_pdfs import write_id_card_sheet

    out = write_id_card_sheet(tmp_path / "id.pdf", conn, cid)
    assert _is_pdf(out)


def test_certificate_numbers_are_sequential(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """TC and CC each draw from their own counter namespace."""
    _, _, sid, sid2, _ = _seed(conn)
    from app.reports.general_pdfs import (
        TCFormFields,
        write_character_certificate,
        write_transfer_certificate,
    )
    from app.repositories import counters_repo

    write_transfer_certificate(
        tmp_path / "tc1.pdf", conn, sid, fields=TCFormFields(leaving_date="2026-03-31")
    )
    write_transfer_certificate(
        tmp_path / "tc2.pdf", conn, sid2, fields=TCFormFields(leaving_date="2026-03-31")
    )
    write_character_certificate(tmp_path / "cc1.pdf", conn, sid)

    assert counters_repo.peek(conn, "TC::2025-26") == 2
    assert counters_repo.peek(conn, "CC::2025-26") == 1
