"""Frozen-slot dataclasses mirroring database tables.

Each module defines exactly the fields stored in its table — repositories
return these instances and never raw tuples or dicts.
"""

from __future__ import annotations

from app.models.attendance import Attendance
from app.models.audit import AuditLog
from app.models.exam import Exam, Mark
from app.models.fee import FeePayment, FeePaymentItem, FeeStructure
from app.models.misc import Document, Remark
from app.models.people import Staff, Student
from app.models.school import AcademicYear, School
from app.models.structure import Class, Subject
from app.models.user import User

__all__ = [
    "AcademicYear",
    "Attendance",
    "AuditLog",
    "Class",
    "Document",
    "Exam",
    "FeePayment",
    "FeePaymentItem",
    "FeeStructure",
    "Mark",
    "Remark",
    "School",
    "Staff",
    "Student",
    "Subject",
    "User",
]
