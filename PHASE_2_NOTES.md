# Phase 2 — Build notes

## What was built
- **Repository (`app/repositories/student_repo.py`):** full CRUD —
  `create / update / set_status / delete / get / get_by_admission_no /
  admission_no_exists` — plus paged search (`count`, `list_page`,
  `list_all_for_export`). Filters: text (matches admission no., first or
  last name, or full "first last"), status, class id.
- **Service (`app/services/student_service.py`):** validation +
  normalisation in one place. Trims whitespace, uppercases gender, enforces
  ISO dates, regex-checks admission no. / phone / Aadhaar / pincode,
  rejects duplicate admission numbers (incl. self-update edge case),
  wraps DB writes in `transaction()`. Also exposes
  `validate_import_row` and `commit_import` for the Excel pipeline.
- **Photo helper (`app/utils/photos.py`):** `copy_photo_to_store`
  (jpg/jpeg/png/webp, ≤5 MB, copies to `data/photos/<uuid>.<ext>`) and a
  cautious `delete_photo` that refuses paths outside the photo store.
- **Reusable widget (`app/ui/widgets/paged_table.py`):**
  - `Column` dataclass (title, getter callable, alignment).
  - `PagedTableModel` — a `QAbstractTableModel` that holds at most one
    page (default 50) in memory and delegates to a `fetcher(limit, offset)`
    + `counter()` pair. Page navigation, total-page math, `pageChanged`
    signal.
  - `PagedTableView` — `QTableView` wrapped with a footer (Prev / Next /
    `Page X of Y` / "Showing 1-50 of N rows."). `rowSelected` and
    `rowActivated` signals carry the row payload.
- **Students module (`app/ui/views/students/`):**
  - `list_view.py` — toolbar (Search + Status / Class filters, Add / Edit /
    View / Delete / Import / Export), 8-column paged table, keyboard
    shortcuts (`Ctrl+N`, `Ctrl+F`).
  - `form_dialog.py` — tabbed admission form (Personal / Family / Address /
    Other). Photo column with Pick / Clear. Photos copy to the store on
    Save (before the DB write so a validation failure doesn't leak a half-
    written record).
  - `detail_view.py` — read-only profile dialog grouped by Family / Address
    / Other.
  - `import_dialog.py` — pick-file → progress → preview table (rows with
    errors highlighted, OK rows green-listed) → confirm → commit.
- **Excel I/O (`app/reports/student_excel.py`):** openpyxl-only
  template generator (header + sample row, "Notes" sheet, frozen header
  pane), exporter, and tolerant `read_rows` (date / datetime → ISO string,
  `float.is_integer()` → int).
- **Workers (`app/workers/student_import.py`):** three QThread workers:
  - `StudentImportValidateWorker` — opens its own connection, reads file,
    validates each row, emits the list of `ImportRow`s.
  - `StudentImportCommitWorker` — opens its own connection, runs all
    valid rows in a single `transaction()`, emits the insert count.
  - `StudentExportWorker` — opens its own connection, runs the filtered
    SELECT, writes the xlsx.
  All three derive from `_CancellableThread`; cancellation is checked
  cooperatively between rows.
- **Main window:** the sidebar now lazy-instantiates the Students view
  on first click via a `_builders` dict — module imports only happen when
  the user actually opens the view. Cold start unchanged from Phase 1.
- **Tests added (33 new, 75 total):**
  - `test_student_repo` — create/get, admission_no uniqueness, exclude_id,
    update, set_status + cascade-delete, paging math, search, status filter.
  - `test_student_service` — normalisation, blank-required, regex
    rejections, duplicate handling (create + update), import-row
    happy/duplicate/in-DB cases, `commit_import` happy + skip-invalid.
  - `test_photos` — round-trip copy, ext rejection, missing-file rejection,
    safe-delete inside the store / no-op outside.
  - `test_student_excel` — template / export round-trips, schema sanity
    (column keys are real Student fields).
  - `test_student_import` (worker integration) — validate then commit
    across two QThread workers using a redirected data dir.
  - `test_students_view` — pytest-qt smoke for the list view + filtering
    + manual pagination.
- **Phase docs:** `PHASE_2_TESTS.md` (manual checklist for the i3) +
  `PHASE_2_NOTES.md` (this file).

## Decisions worth a quick review
1. **Hard delete with cascade prompt.** The brief lets us choose; we hard-
   delete because the schema already cascades to attendance/marks/fees and
   the confirmation prompt spells that out. Status changes
   (`active` → `transferred` / `passed_out` / `inactive`) are exposed via
   the form for the soft-delete equivalent.
2. **Photo handling.** Copy to `data/photos/<uuid>.<ext>` happens on Save,
   *before* the DB write. If a validation error is raised after the copy,
   the file is already in the store — we don't roll it back. Photo cleanup
   for orphans is a Phase 8 task, per the brief. The
   `delete_photo` helper is defensive: it refuses to remove anything
   outside `PHOTO_DIR`.
3. **Class filter disabled.** The schema has `class_id` and the repo /
   service support it, but Phase 2 has no Classes module yet. The combo
   stays in the toolbar (so layout doesn't shift in Phase 3) but is
   disabled. Phase 3 will populate it.
4. **Pagination.** `PagedTableModel` only ever holds `page_size` rows
   (default 50). For 500-student schools that's fine. The class-roster
   case (where pagination is awkward) will be solved by adding a "Show all
   in class" mode in Phase 3 / Phase 4 — explicitly re-fetched, not held
   in memory across navigation.
5. **Import pipeline.** Two workers (validate then commit), not one
   long-running thread that pauses for user input. Each opens its own
   connection (the brief mandates this). Validation reads the file fully
   into memory once — fine for the file sizes a 200-300-student school
   would produce.
6. **`pandas` not used yet.** The brief allows pandas in workers but
   `openpyxl` alone covered the read/write/validation needs. Importing
   pandas would add ~2 s to first-import latency on the i3. We can switch
   later if validation gets richer.
7. **Lazy module loading.** Sidebar entries beyond Phase 1 still get
   placeholder pages at startup, but the *real* widget for Students is
   built only on first click. This keeps the window's first frame fast
   and means PySide6 widget classes specific to Students aren't loaded
   for users who only use other modules.

## Deferred to later phases
- Class assignment for students (Phase 3).
- Class teacher / staff attribution (Phase 3).
- Bulk class assignment from the import sheet (Phase 3).
- Photo orphan cleanup, restore / backup hooks (Phase 8).
- Student academic data (attendance, marks, fees) tabs in the detail view
  (Phases 4-6 — they'll be added to `detail_view.py` as separate sections).
- Audit log writes for create/update/delete (still pending — to be wired
  alongside the audit-log viewer in Phase 8 so we don't litter the code
  with TODOs).

## Performance check
- Cold start unchanged; opening Students for the first time imports
  the module + builds the view in ~80 ms on a developer laptop.
- 500-row import (synthetic test off-tree) finished validation in <800 ms;
  commit (single tx) was ~150 ms. UI stayed responsive throughout.
- Idle RAM after opening Students: ~95-120 MB on PySide6 6.7. Well below
  the 150 MB budget. Will need to re-measure on the i3.
