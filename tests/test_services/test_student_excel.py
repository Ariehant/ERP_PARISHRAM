from __future__ import annotations

from pathlib import Path

from app.models.people import Student
from app.reports.student_excel import (
    TEMPLATE_COLUMNS,
    read_rows,
    write_export,
    write_template,
)


def test_template_round_trip(tmp_path: Path) -> None:
    template = write_template(tmp_path / "students.xlsx")
    assert template.is_file()
    rows = read_rows(template)
    # The template includes one sample row.
    assert len(rows) == 1
    sample = rows[0]
    assert sample["admission_no"] == "ADM/2025/001"
    assert sample["first_name"] == "Aarav"
    # Date came back as ISO string.
    assert sample["dob"] == "2014-08-15"
    # Sample values are written as strings in the template; users will type
    # real numbers, which come back as int (we coerce floats with is_integer).
    assert str(sample["roll_no"]) == "1"


def test_export_round_trip(tmp_path: Path) -> None:
    students = [
        Student(
            id=1,
            admission_no="ADM/1",
            first_name="Aarav",
            last_name="Sharma",
            admission_date="2025-04-01",
            dob="2014-08-15",
            gender="M",
            status="active",
        ),
        Student(
            id=2,
            admission_no="ADM/2",
            first_name="Riya",
            admission_date="2025-04-01",
            status="active",
        ),
    ]
    out = write_export(tmp_path / "out.xlsx", students)
    rows = read_rows(out)
    assert len(rows) == 2
    assert rows[0]["admission_no"] == "ADM/1"
    assert rows[1]["first_name"] == "Riya"


def test_template_columns_keys_match_student_fields() -> None:
    """All TEMPLATE_COLUMNS keys must map to fields on the Student dataclass."""
    student_fields = set(Student.__dataclass_fields__.keys())
    for key, *_ in TEMPLATE_COLUMNS:
        assert key in student_fields, f"unknown template column key: {key}"
