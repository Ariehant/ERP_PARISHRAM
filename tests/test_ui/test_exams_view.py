from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")


from app.models.exam import Exam
from app.models.school import AcademicYear
from app.models.structure import Class, Subject
from app.repositories import class_repo, exam_repo, school_repo
from app.services import mark_service


def _seed(conn: sqlite3.Connection) -> tuple[int, int, list[int]]:
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
    class_repo.create_subject(conn, Subject(id=None, name="Math", class_id=cid, max_marks=100))
    class_repo.create_subject(conn, Subject(id=None, name="English", class_id=cid, max_marks=80))
    eid = exam_repo.create(conn, Exam(id=None, name="Mid-term", academic_year_id=yid))
    sids: list[int] = []
    for i in range(3):
        cur = conn.execute(
            "INSERT INTO students (admission_no, first_name, admission_date, class_id, status, roll_no) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (f"ADM/{i + 1:03d}", f"Stu{i + 1:02d}", "2025-04-01", cid, i + 1),
        )
        sids.append(int(cur.lastrowid))
    return cid, eid, sids


def test_exams_view_renders_three_tabs(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn)
    from app.ui.views.exams.view import ExamsView

    view = ExamsView(conn)
    qtbot.addWidget(view)
    assert view.tabs.count() == 3
    # Exams tab shows the seeded exam.
    assert view.exam_list_view._model.total_rows == 1


def test_marks_entry_loads_grid(qtbot, conn: sqlite3.Connection) -> None:
    _seed(conn)
    from app.ui.views.exams.marks_entry import MarksEntryView

    view = MarksEntryView(conn)
    qtbot.addWidget(view)
    # 3 students, 2 subjects -> table has 3 rows and 4 columns (Roll, Name + 2 subjects).
    assert view.table.rowCount() == 3
    assert view.table.columnCount() == 4


def test_marks_entry_save_round_trip(qtbot, conn: sqlite3.Connection) -> None:
    cid, eid, sids = _seed(conn)
    from app.ui.views.exams.marks_entry import MarksEntryView

    view = MarksEntryView(conn)
    qtbot.addWidget(view)
    # Pick the first student/subject's spinbox and set a value safely under the
    # smallest subject max (English = 80).
    first_subject_id = view._subject_ids[0]
    spin = view._spinboxes[(sids[0], first_subject_id)]
    spin.setValue(72.0)
    view._save()

    grid = mark_service.load_grid(conn, cid, eid)
    assert grid[(sids[0], first_subject_id)]["marks_obtained"] == 72.0
    # 72/80 = 90% -> A+
    assert grid[(sids[0], first_subject_id)]["grade"] == "A+"


def test_grade_scale_view_lists_default_bands(qtbot, conn: sqlite3.Connection) -> None:
    from app.ui.views.exams.grade_scale_view import GradeScaleView

    view = GradeScaleView(conn)
    qtbot.addWidget(view)
    # The seeded scale has 8 default bands.
    assert view.table.rowCount() >= 8
