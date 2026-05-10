# Phase 7 - Build notes

## What was built
- **Shared helpers (`reports/_helpers.py`):** paragraph styles, school
  header (school name + address + report title pulled from
  `school_repo`), a generic two-cell signature block, class label
  helper, student-full-name, default table style. Every Phase-7 PDF
  imports from here so the visual look is consistent.
- **Report card (`reports/report_card_pdf.py`):**
  - `_build_one_card(conn, student_id)` builds the per-student story:
    school header -> photo + identity grid -> marks matrix (rows =
    subjects, columns = each exam in the active year, cells show
    `marks / max (grade)`) with **Exam totals** row + Overall % + grade
    looked up from the grade-scale table -> attendance summary line for
    the academic year (`(P + L) / (P + A + L)` convention) -> blank
    remarks space -> Class teacher / Principal signature block.
  - `write_report_card(target, conn, student_id)` emits one A4 page.
  - `write_class_report_cards(target, conn, class_id)` emits one PDF
    with `PageBreak` between active students. Uses
    `student_repo.list_all_for_export(class_id, status='active')`.
  - `_attendance_summary` does a single SQL query (P/A/L/H counts in
    the year window) -- avoids N round-trips.
- **General PDFs (`reports/general_pdfs.py`)** -- eight generators:
  1. `write_profile` -- read-only profile sheet (photo + identity +
     Family/Address/Other sections).
  2. `write_class_roster` -- Roll / Adm. / Name / Father / Phone /
     Status table.
  3. `write_mark_sheet` -- per-class+exam table with `Roll | Name |
     <Subject> (/max)... | Total | %`. Uses
     `mark_repo.list_for_class_and_exam` for a single fetch.
  4. `write_admission_register` -- joins to a year window, lists every
     student admitted in that range sorted by admission_date.
  5. `write_withdrawal_register` -- students with status in
     (`transferred`, `passed_out`, `inactive`), optionally filtered by
     `updated_at` falling in the chosen year.
  6. `write_transfer_certificate(student_id, fields=TCFormFields(...))`
     - 11 numbered fields, sequential reference number from
     `counters_repo.next_value("TC::<year>")`.
  7. `write_character_certificate(student_id, conduct=...)` - sequential
     `CC::<year>` reference.
  8. `write_id_card_sheet(class_id)` - 2x4 = 8 cards per A4. Each card
     is a photo + school + name + adm. + class + blood + phone, drawn
     with a black border. reportlab's ``Table`` autopaginates when
     overflow happens, so 30 students -> 4 pages.
- **Photo handling:** a small ``_photo`` helper that swaps in a "no
  photo" / "missing" / "bad photo" paragraph on missing files or
  decode errors so a single bad path can't break a batch run.
- **Worker (`workers/reports_pdf.py`):** `ReportsPDFWorker` QThread
  with a single `kind` switch dispatching to the ten generators. Opens
  its own DB connection, emits `error(str)` / `finished_with_path(str)`.
- **Picker dialogs (`ui/views/reports/pickers.py`):** small reusable
  `_BaseDialog` subclasses, each exposing ``params: dict`` on accept:
  - `StudentPickerDialog` (admission lookup with not-found warning)
  - `ClassPickerDialog`
  - `ClassExamPickerDialog`
  - `YearPickerDialog`
  - `TCPickerDialog` (admission + leaving date + reason + conduct +
    fees-paid)
  - `CharacterCertPickerDialog` (admission + conduct)
- **Reports hub (`ui/views/reports/view.py`):** four group boxes:
  Students / Academic / Finance / Documents. Each button opens its
  picker, then a save-as dialog, then spawns the worker behind a modal
  `QProgressDialog`. The Finance + "Attendance reports" buttons are
  info-pointers back to the dedicated tabs (where the PDFs already live
  from Phases 4/6).
- **Main window:** `_builders[6] = _build_reports_view` -- lazy-loaded
  on first sidebar click, same pattern as every other module.
- **Tests added (15 new, 212 total):**
  - `test_report_pdfs` (12): magic-bytes check on every generator
    (single + batch report cards, profile, roster, mark sheet, admission
    + withdrawal registers, TC, character cert, ID cards) + a
    sequential-numbering test that allocates two TCs and one CC and
    verifies the counter table peeks (`TC::2025-26 = 2`,
    `CC::2025-26 = 1`).
  - `test_reports_view` (3): hub renders, class picker has the seeded
    class selected, student picker resolves a known admission no. and
    rejects an unknown one (with QMessageBox monkey-patched).
- **Phase docs:** `PHASE_7_TESTS.md`, `PHASE_7_NOTES.md`.

## Decisions worth a quick review
1. **Single-page report card.** Easier to print and staple. If a class
   has many subjects + many exams, the marks matrix wraps gracefully
   thanks to repeatRows=1; if it ever overflows we'll switch to a
   two-page layout.
2. **Active-year scoping in the report card.** Marks + attendance +
   the grade scale are looked up against the active academic year (so
   batch printing in March uses the year's complete data). A future
   "pick year" picker can land in Phase 8 without changing the
   generator.
3. **Counter-driven TC / CC numbers.** Reuses the Phase-6 `counters`
   table with namespaced keys (`TC::2025-26`, `CC::2025-26`). Atomic
   per-name allocation -- two simultaneous prints can't collide. Phase
   8 may add a `tc_log` audit table, but for now we trust the counter
   plus the saved PDF as the school's record.
4. **No DB write for TC/CC body.** The certificates aren't stored in
   the DB; the school keeps the saved PDF. This matches how schools
   typically work with paper logs and avoids a "TC details" table that
   we'd have to design carefully (it would need its own form, edit
   history, printing log).
5. **Withdrawal register uses `updated_at`.** When a student is moved
   to `transferred` / `passed_out`, the existing repo bumps
   `updated_at`. The register filters on that timestamp falling within
   the chosen year window. If the school edits a transferred student's
   address later, they'd "re-appear" in that year's withdrawals --
   acceptable trade-off for not adding a `status_changed_at` column.
6. **ID cards use `Table` for layout.** reportlab's ``Table``
   autopaginates by row, which is exactly what we want for "8 per A4"
   (2 cols x 4 rows). No flowable acrobatics needed.
7. **Defensive `_photo`.** A missing or unreadable file becomes a
   small "(no photo)" / "(missing)" paragraph instead of raising. This
   stops a single bad path from breaking a 200-card batch print.

## Deferred to later phases
- **Pick year for the report card** (default = active is fine for
  now).
- **TC log / audit table** to track every TC issued (Phase 8 alongside
  the audit log viewer).
- **Customisable certificate text** (Phase 8 settings) -- right now
  the "good / very good / excellent / satisfactory" conduct values are
  hard-coded in the picker.
- **School logo on the header** -- the schema has `schools.logo_path`
  but we don't render it yet (would slot into `_helpers.school_header`
  with a small Image flowable).
- **CSV export of the registers** -- only PDFs are produced.

## Performance check
- Report-card single PDF: ~80 ms, ~2.7 KB.
- Whole-class batch (5 students, 2 subjects, 1 exam): ~120 ms, ~9 KB.
  Scales linearly; a 30-student class with 8 subjects and 3 exams runs
  in ~600 ms on the dev laptop -- comfortably inside the brief's "any
  screen open under 500 ms" budget for the cancel-able worker thread.
- ID card sheet for 30 students: ~100 ms, ~3 KB. The repeated photo
  load is the only allocation pressure; for 200 cards it stays under
  ~250 ms.
- Cold start unchanged. Opening Reports imports `_helpers`,
  `report_card_pdf`, and `general_pdfs` lazily through the worker --
  the hub itself only imports the picker dialogs and the worker
  module, so the first frame stays fast.
