from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Staff:
    id: int | None
    emp_code: str
    name: str
    role: str
    phone: str | None = None
    email: str | None = None
    joining_date: str | None = None
    qualification: str | None = None
    is_active: bool = True


@dataclass(slots=True, frozen=True)
class Student:
    id: int | None
    admission_no: str
    first_name: str
    admission_date: str
    last_name: str | None = None
    roll_no: int | None = None
    dob: str | None = None
    gender: str | None = None
    blood_group: str | None = None
    photo_path: str | None = None
    class_id: int | None = None
    status: str = "active"
    father_name: str | None = None
    father_phone: str | None = None
    father_occupation: str | None = None
    mother_name: str | None = None
    mother_phone: str | None = None
    mother_occupation: str | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    aadhaar: str | None = None
    prev_school: str | None = None
    category: str | None = None
    religion: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
