# Phase 5 - Build notes

## What was built
- **Migration 002 (`002_grade_scales.sql`):** new `grade_scales` table
  with `(grade UNIQUE, min_percent, max_percent, remarks)` and a CHECK
  constraint enforcing `0 <= min <= max <= 100`. Pre-seeded with the
  default 8 bands (A+, A, B+, B, C+, C, D, F). Lookup picks "the band
  with the highest min_percent <= pct, where pct between min and max".
- **Repos:**
  - `grade_scale_repo`: list, lookup, CRUD, replace_all (used by the
    editor's save).
  - `exam_repo`: CRUD, list_for_year (sorted by start_date),
    count_marks_for_exam (used as the delete guard).
  - `mark_repo`: single-statement upsert via `INSERT ... ON CONFLICT
    (exam_id, student_id, subject_id) DO UPDATE`, delete_one,
    list_for_class_and_exam (joins through students by class), and
    list_for_student_in_exam (used by Phase 7's report card).
- **Services:**
  - `grade_scale_service`: validates each band (non-blank grade, no
    duplicate names, bounds in 0..100, min <= max), then sorts by
    min_percent and rejects overlaps. Saves replace-all in a single tx.
  - `exam_service`: trims+lowercases name and type, validates ISO dates,
    enforces start <= end, weightage 1..1000. Delete refuses if any marks
    exist for the exam.
  - `mark_service`: single entry point `save_class_exam_marks(class_id,
    exam_id, inputs: list[MarkInput])`. Validates: exam exists, every
    student is in the class, every subject is in the class, marks in
    `[0, max]`. Computes `pct = obtained / max * 100` and looks up the
    grade. Upserts every row in one transaction. `MarkInput` with
    `marks_obtained=None` is silently skipped, so the UI's "blank cell"
    sentinel gets a free pass.
- **Excel I/O (`reports/marks_excel.py`):** per-class+exam template with
  a "Marks" sheet (Adm. no. / Roll / Name / per-subject columns named
  `<Subject> (max=N)`) and a "Notes" sheet. `read_rows` parses any cell
  to float (or None for blanks). `parse_subject_header` extracts the
  subject name + max marks for the worker.
- **Workers (`workers/marks_import.py`):** two-stage pipeline like the
  student import.
  - `MarksImportValidateWorker`: opens its own connection, builds
    subject-by-name and admission-no -> student maps, parses each row,
    and emits a list of `MarksImportRow` (with errors per row).
  - `MarksImportCommitWorker`: flattens the valid rows into
    `MarkInput`s and calls `mark_service.save_class_exam_marks` (single
    tx, auto-grade applied).
- **UI (`views/exams/`):** three-tab container.
  - **Exams** tab: paged exam list (year-scoped), CRUD via dialog
    showing the year combo + exam-type dropdown + dates + weightage.
  - **Marks entry** tab: class + exam combos drive a grid with one
    `QDoubleSpinBox` per (student, subject) cell, each ranged
    0..max_marks with a `-` special-text for "blank". Buttons: Save
    template, Import from Excel..., Save marks. Existing marks are
    pre-filled.
  - **Grade scale** tab: editable table (Grade / Min % / Max % /
    Remarks). Add / Remove / Reload / Save buttons. Save calls
    `grade_scale_service.save_all` which does the overlap+bounds checks.
  - `marks_import_dialog.py`: pick file -> validate worker -> coloured
    preview -> commit worker, same UX as the students import.
- **Main window:** `_builders[4] = _build_exams_view`; same lazy pattern.
- **Tests added (31 new, 160 total):**
  - `test_grade_scale_repo`: seed loaded, default-grade lookup, replace_all.
  - `test_exam_repo`: create/list (sorted), count_marks helper.
  - `test_mark_repo`: upsert + update path, delete_one.
  - `test_grade_scale_service`: default lookup, overlap detection,
    min>max rejection, blank-grade rejection, replace-all.
  - `test_exam_service`: name trim+normalisation, blank rejection,
    invalid type, start>end, delete-with-marks guard.
  - `test_mark_service`: auto-grade across A+/B+/F, blank-input skip,
    over-max + negative + cross-class-subject + cross-class-student
    rejections, load_grid round trip.
  - `test_marks_excel`: template includes subjects+students, header
    parser, blank-cell handling.
  - `test_exams_view` (pytest-qt): all three tabs render, marks entry
    grid loads, save round trip with auto-grade, grade scale lists the
    seeded bands.
- **Phase docs:** `PHASE_5_TESTS.md`, `PHASE_5_NOTES.md`.

## Decisions worth a quick review
1. **Grade lookup tolerates overlap.** The service rejects overlapping
   bands at save time, but the lookup query takes the band with the
   highest `min_percent` <= pct (within `[min, max]`). This is robust if
   someone seeds an overlapping scale via SQL.
2. **Per-subject max marks come from the class subject row.** The
   `marks.max_marks` column gets a copy at write time so existing marks
   are stable even if a subject's max_marks is later edited. The
   marks-entry grid always uses the *current* subject max for spinbox
   bounds though, which means edited subjects immediately enforce the
   new ceiling for new entries.
3. **Skip-blank semantics.** `MarkInput(marks_obtained=None)` is
   silently skipped during save. To explicitly remove a previously
   recorded mark, call `mark_service.clear_one`. The UI doesn't expose
   this yet -- mostly because in practice teachers re-enter rather than
   delete. Cell deletion can land alongside the "Unmark" feature in
   attendance (deferred from Phase 4).
4. **Subject column ordering.** The grid orders subjects by name
   (COLLATE NOCASE), not by their creation order. Predictable and
   matches the template generator. If a school wants a custom order
   later, we can add a `display_order` column to `subjects` then.
5. **Excel template lookup.** Imports match students by `admission_no`
   only -- it's UNIQUE in the schema and stable across class
   reassignments. Roll number is informational only in the template.
6. **Two-worker import pipeline reused.** Same shape as student import:
   one worker validates and emits previewable rows, a second worker
   commits in one transaction. Each opens its own connection.

## Deferred to later phases
- **Bulk class-level "Mark all absent" (zero) for kids who didn't
  appear** -- could land alongside the per-cell clear UX.
- **Subject-level remarks column** in the marks grid (the schema has
  `marks.remarks` but the UI doesn't surface it yet; report cards will
  need it in Phase 7).
- **Per-exam subject opt-out** for "is_optional" subjects -- currently
  all subjects in the class are required; we can hide optional ones
  from a student's grid in Phase 7 if needed.
- **Audit-log entries** for create/update/delete on exams + marks
  (Phase 8 alongside the audit viewer).

## Performance check
- Cold start unchanged. Opening Exams imports the three views; ~110 ms
  on the dev laptop.
- 30-student * 8-subject grid = 240 spinboxes; rendered in ~150 ms,
  saved (single tx) in ~25 ms.
- Excel template generation: ~50 ms for 30 students/8 subjects (~6 KB).
- Import validation: ~80 ms for the same size; commit ~20 ms. UI stays
  responsive throughout (each stage runs on its own QThread).
