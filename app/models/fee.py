from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class FeeStructure:
    id: int | None
    class_id: int
    academic_year_id: int
    head: str
    amount_paise: int
    frequency: str  # monthly/quarterly/annual/one_time
    due_month: int | None = None


@dataclass(slots=True, frozen=True)
class FeePayment:
    id: int | None
    student_id: int
    receipt_no: str
    payment_date: str
    amount_paise: int
    mode: str  # cash/upi/cheque/card/bank
    reference_no: str | None = None
    remarks: str | None = None
    collected_by: int | None = None
    created_at: str | None = None


@dataclass(slots=True, frozen=True)
class FeePaymentItem:
    id: int | None
    fee_payment_id: int
    head: str
    amount_paise: int
    fee_structure_id: int | None = None
    for_month: int | None = None
    for_year: int | None = None
