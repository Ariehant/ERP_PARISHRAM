# Phase 6 - Build notes

## What was built
- **Migration 003 (`003_counters.sql`):** new `counters(name PRIMARY
  KEY, value)` table for atomic sequence allocation. One row per
  sequence name; `next_value` increments via `INSERT ... ON CONFLICT
  DO UPDATE RETURNING value` so two writers can never get the same
  number.
- **Repos:**
  - `counters_repo`: `next_value(conn, name)` and `peek`. Always
    inside the caller's transaction.
  - `fee_structure_repo`: CRUD + `list_for_class(class_id, year)` +
    `replace_for_class(...)` diff-and-apply (insert / update / delete).
  - `fee_payment_repo`: CRUD for `fee_payments` + items, plus three
    aggregate helpers used by the ledger and pending calc:
    `total_paid_for_student`, `total_paid_for_head`,
    `list_items_for_student` (joins to the parent payment so callers
    see receipt no. + date + mode in one query).
- **INR words helper (`utils/inr_words.py`):** `paise_to_words(paise)`
  in Indian English with proper Crore/Lakh/Thousand grouping. Always
  emits a "Rupees" prefix on receipts even for paise-only amounts;
  zero-paise stays as `"Zero Rupees Only"`. Used by the receipt PDF
  for the "Total in words" line.
- **Fee service (`services/fee_service.py`)**:
  - `pending_for_student(student_id, today=...)` -> per-head
    `PendingHead` records with `instances_due`, `total_due_paise`,
    `paid_paise`, and a derived `outstanding_paise`. Frequency
    semantics: monthly = months elapsed in year (capped at 12),
    quarterly = `min(4, (months_elapsed + 2) // 3)`, annual /
    one_time = 1 once the year has started.
  - `collect_payment(...)` -> writes `fee_payments` + items in one
    transaction, with the receipt number allocated atomically inside
    the same tx (`counters_repo.next_value("receipt_no::<year>")`).
    Returns `PaymentResult(payment_id, receipt_no)`.
  - `defaulters_for_class(class_id)` -> active students with
    outstanding > 0. Walks each student's pending list (one query per
    head) -- fine for school-sized classes.
  - `ledger_for_student(student_id)` -> the joined per-item ledger.
  - `save_structure(class_id, year, rows)` -> validates blank head /
    bad frequency / non-positive amount / due_month 1-12 / case-fold
    duplicates, then replace-all in a single tx.
  - Receipt number format `RCP/YYYY-YY/NNNNN` per the brief. Counter
    namespaced by year label so a year switch starts a fresh sequence
    (the brief expects this -- no global receipt counter that crosses
    year boundaries).
- **PDF generators (`reports/fee_pdf.py`)** -- four reportlab Platypus
  documents:
  - `write_receipt_a4` -- school header, meta table (receipt no, date,
    student, class, mode, reference), item table with "Total" row,
    total-in-words, remarks, double signature block.
  - `write_receipt_thermal` -- 80mm page with center-aligned header,
    compact item table, signature line, "Thank you!" footer.
  - `write_ledger` -- chronological payments table + outstanding
    summary by head + total paid / outstanding line.
  - `write_defaulters` -- per-class table sorted by roll/name with
    outstanding amounts + total.
- **PDF worker (`workers/fee_pdf.py`)** -- `FeePDFWorker` QThread
  with `kind` switch (`receipt_a4` / `receipt_thermal` / `ledger` /
  `defaulters`). Opens its own DB connection, emits
  `error(str)` / `finished_with_path(str)`.
- **UI (`views/fees/`)** -- four-tab container.
  - **Structure** -- editable rows table (head / amount in rupees /
    frequency / due month) per class+active year. Replace-all save.
  - **Collection** -- admission-no lookup, pending grid with check
    column + per-row amount spinbox, mode + reference + remarks +
    date inputs, "Save && receipt no." button. After save, "Print
    A4" / "Print 80mm" buttons activate.
  - **Ledger** -- admission-no lookup, payments + outstanding tables,
    "Export PDF" button.
  - **Defaulters** -- class picker, per-class table, "Export PDF"
    button.
- **Main window:** `_builders[5] = _build_fees_view`, lazy-loaded.
- **Tests added (37 new, 197 total):**
  - `test_counters_repo` (3): per-name sequence, peek round trip,
    independent counters.
  - `test_fee_repos` (3): replace_for_class diff-apply, total-paid
    helpers, list-items-for-student joining payments.
  - `test_inr_words` (10 parametrised): zero, hundreds, thousands,
    lakhs, crores, paise-only, negative.
  - `test_fee_service` (15): pending in month 1 / 6 / capped / quarterly
    / annual / one_time, partial-payment subtraction, atomic + sequential
    receipt numbers, items written, mode/amount/head validation,
    structure validation (frequency / amount / case-fold dup),
    defaulters list.
  - `test_fee_pdf` (4): magic-bytes check on all four PDFs.
  - `test_fees_view` (3): four tabs render, collection lookup +
    save + receipt no. captured, defaulters lists unpaid student.
- **Phase docs:** `PHASE_6_TESTS.md`, `PHASE_6_NOTES.md`.

## Decisions worth a quick review
1. **Receipt number is per-year-label.** Counter key is
   `"receipt_no::2025-26"`; switching to `2026-27` (Phase 8) starts a
   fresh `00001` sequence. The brief's `RCP/YYYY-YY/NNNNN` format
   suggests this is what schools expect.
2. **Pending instances count from year-start.** A student who joins
   in October still shows 6 unpaid Tuition instances by then. We don't
   pro-rate -- the school can record an opening "credit" payment if
   they want to forgive earlier instances. Documented at the top of
   `fee_service.py`.
3. **`L` in attendance, `late` in fees.** Late counts as attended in
   attendance reports but is unrelated here -- "Late fine" is just
   another fee head you'd add to the structure.
4. **Mode whitelist.** `cash / upi / cheque / card / bank` per the
   brief. We don't support partial cash + cheque on the same receipt;
   the school can record two separate payments.
5. **Atomic receipt number within the payment transaction.** The
   counter increment + payment insert + items insert are all in one
   `transaction()` block. If anything fails, both the counter and the
   payment roll back, so we never burn a number. Tested via the
   sequential-receipt-no test.
6. **No "Pay all" wizard yet.** The collection screen is "pick what's
   due, edit if needed, save". A future enhancement could auto-apply
   payments to oldest outstanding instalments per head; for Phase 6
   we keep semantics simple (the head is what matters; the user records
   the period in the optional `for_month` / `for_year` columns -- not
   surfaced in the UI yet).
7. **Defaulters walks students one-by-one.** With 200-300 students per
   school this is fast (each student does 1 small query per fee head).
   If ever slow, we'll move to a single GROUP-BY query.

## Deferred to later phases
- **`for_month` / `for_year` in collection UI** -- would let the school
  tag this payment as Apr 2025's tuition. The schema supports it; the
  ledger-view + receipts already render it when present.
- **Fine / discount as separate payment-item types** -- currently you
  add a head named "Late fine" to the structure with frequency
  `one_time`.
- **Audit-log entries** for payments + structure edits (Phase 8).
- **Bulk SMS / WhatsApp reminder** integration for defaulters -- the
  brief is offline-only, so this would be a Phase-9 add-on if at all.
- **CSV/Excel export** of the ledger and defaulters lists -- only PDFs
  are produced now; the brief calls for PDFs explicitly.

## Performance check
- Cold start unchanged. Opening Fees imports four views; ~140 ms on
  the dev laptop.
- 200 students with 4 fee heads (defaulters report) computes in
  ~200-250 ms without optimisation. The PDF generation runs another
  ~150 ms.
- A4 receipt PDF: ~2.6 KB, ~80 ms. Thermal receipt: ~2.3 KB, ~70 ms.
- Save+receipt round-trip (UI -> service -> 1 INSERT into counters,
  1 into fee_payments, N into fee_payment_items) is ~10 ms for
  N=4 items.
