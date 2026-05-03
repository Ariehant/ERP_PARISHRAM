# Phase 4 - Build notes

## What was built
- **Repo (`app/repositories/attendance_repo.py`):**
  - `list_for_class_and_date` -- LEFT JOINs the roster against the
    `attendance` table for the date so the daily grid sees every active
    student, marked or not.
  - `upsert_marks` -- one `INSERT ... ON CONFLICT(student_id, date) DO
    UPDATE` per row. SQLite supports this since 3.24, and Python 3.11's
    bundled sqlite is well past that. Also rejects unknown statuses.
  - `monthly_summary_for_class` -- single GROUP BY query returning per-
    student P/A/L/H counts; uses LEFT JOIN so students with zero rows
    still appear.
  - `list_monthly_for_class` -- raw `(student_id, date, status)` tuples
    used to populate the monthly matrix view.
  - `clear_for_class_and_date` -- delete helper, currently unused by the
    UI but tested.
  - `_month_bounds(year, month)` -- centralised half-open ISO range
    helper, reused throughout the module.
- **Service (`app/services/attendance_service.py`):**
  - `save_class_attendance` -- validates date format, status values,
    and that every student is still in the named class (catches stale
    rosters cached in the UI), then upserts in **one transaction**.
  - `class_summary` / `low_attendance` / `daily_register` -- thin
    helpers that turn repo rows into `StudentMonthlySummary` dataclasses
    or list-of-dicts for the PDF generators.
  - `StudentMonthlySummary` is a frozen-slots dataclass with derived
    properties: `total_marked`, `effective_total` (P+A+L), `percentage`
    ((P+L) / effective_total * 100, 0 when no sessions are marked), and
    `display_name`.
- **PDF generators (`app/reports/attendance_pdf.py`):** three
  reportlab Platypus documents - daily register, monthly summary,
  low-attendance list. Each shares a school-header helper and a
  signature block (Class teacher / Principal). Empty-class fallbacks
  produce valid PDFs with a placeholder row, tested.
- **PDF worker (`app/workers/attendance_pdf.py`):** single QThread
  that opens its own connection, dispatches on `kind` (`daily` /
  `monthly` / `low`), emits `error(str)` on failure and
  `finished_with_path(str)` on success.
- **UI:**
  - `daily_view.py` -- class combo + date picker + roster table
    (`QTableWidget`) with one `QButtonGroup` per row driving four
    `QRadioButton`s (P/A/L/H). "Mark all present" button + Save button.
    Auto-reloads when class or date changes.
  - `monthly_view.py` -- read-only matrix; columns are Roll, Name,
    day1..dayN, %. Cells colour-coded by status.
  - `reports_view.py` -- three group boxes (daily, monthly, low) with
    their own pickers and "Generate PDF" buttons; spawns the worker
    with a modal "Generating PDF" `QProgressDialog`.
  - `view.py` -- `QTabWidget` container; refreshes the freshly-shown
    tab on switch so changes from the masters module land.
- **Main window:** `_builders[3] = _build_attendance_view`; same lazy
  pattern as Phases 2/3.
- **Tests added (22 new, 129 total):** repo (upsert + update, invalid
  status, monthly counts, month boundary, clear, inactive students
  excluded); service (date / status / empty / wrong-class validation,
  percentage with all four statuses, low-attendance threshold, holiday
  exclusion); PDF generators (magic-bytes check on all three reports,
  empty-class case); pytest-qt UI (tabs render, mark-all + save round
  trip, save-with-nothing-marked guard).
- **Phase docs:** `PHASE_4_TESTS.md` and `PHASE_4_NOTES.md`.

## Decisions worth a quick review
1. **Percentage formula.** `(P + L) / (P + A + L) * 100`. Late counts
   as attended (typical Indian-school convention); holidays excluded
   from the denominator entirely. Documented at the top of
   `attendance_service.py`. If you want a stricter "L counts as half
   present" or a configurable scheme, this is the single place to
   change it.
2. **`marked_by` is NULL for now.** The schema's `attendance.marked_by`
   references `staff(id)`, but the logged-in entity is a `User`. We
   write NULL until Phase 8 wires up a "current user -> staff" mapping
   and an audit trail. The UI does not surface a "Marked by" picker -
   we'll add one along with the audit-log work.
3. **Inactive students excluded.** Both the daily roster and the
   monthly summary filter on `students.status = 'active'`. Transferred
   / passed-out students do not show up. If we ever need historical
   matrices that include them, that will be a flag on the queries.
4. **Cooperative cancel.** `AttendancePDFWorker` doesn't expose a
   `cancel()` because reportlab's `doc.build()` is atomic; we'd have
   to delete the half-written file. The `QProgressDialog` "Cancel"
   button currently just closes the dialog (the worker still finishes,
   silently). For a 200-student school this finishes in well under a
   second, so a real cancel is overkill. Revisit if class sizes blow up.
5. **Two daily-grid implementations considered.** A custom widget with
   a `QVBoxLayout` of rows would make per-row layout slightly cleaner,
   but `QTableWidget` is well-tested for hundreds of rows and gives us
   selection / scrolling / keyboard nav for free. Worth keeping as we
   move to bigger rosters.
6. **No "clear/uncheck" in the daily grid.** Once a status is selected
   the row stays in one of P/A/L/H. To revert a mark, switch to a
   different status. A future "Unmark" action would call
   `attendance_repo.clear_for_class_and_date` (already implemented).

## Deferred to later phases
- Per-day class-wide holiday button ("Mark all H").
- Real `marked_by` recording + an attendance audit pane (Phase 8).
- Excel export of the monthly matrix (Phase 7 reports hub).
- Configurable percentage formula in Settings (Phase 8).

## Performance check
- Cold start unchanged. Opening Attendance imports the three views and
  reportlab transitively; ~150 ms on a developer laptop. Reportlab is
  ~40 MB resident which would push a fresh-cold start over the 150 MB
  budget if everyone opened the Attendance tab right away on the i3.
  Lazy loading keeps the rest of the app under budget; we'll re-measure
  on the i3 when you do the Phase 4 manual checklist.
- 30-student daily save: ~10 ms (single transaction, 30 upserts).
- Monthly matrix for a 30-student class with 22 marked days: rendering
  in ~30 ms on the dev machine.
- Daily register PDF: 6-8 KB, generated in ~100 ms. Monthly summary:
  ~2-3 KB, ~80 ms. Well within the 500 ms "any screen open" budget,
  but they still run on a worker thread per the brief.
