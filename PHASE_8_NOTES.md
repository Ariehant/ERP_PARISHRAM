# Phase 8 - Build notes

## What was built
- **Audit log:**
  - `app/repositories/audit_log_repo.py` -- `record(...)` insert plus
    filtered list/count and helpers for distinct actions/entities (used
    to populate the filter combos).
  - `app/services/audit_service.py` -- thin wrapper. Audit failures log
    a warning but never break the calling transaction.
  - Wired into two key paths: successful login
    (`auth_service.authenticate`) and fee-payment collection
    (`fee_service.collect_payment`). The brief asks for a viewer, not
    a comprehensive audit; the same wiring pattern can be applied to
    other writes in future phases.
- **Backup / restore (`app/services/backup_service.py`):**
  - `auto_backup(conn)` -- uses ``conn.backup()`` (SQLite's online
    backup API, safe under WAL) to write
    ``data/backups/auto_YYYYMMDD_HHMMSS.db``, then trims the most
    recent 14.
  - `manual_backup(conn, target)` -- same online backup to a
    user-chosen path.
  - `restore_backup(source)` -- renames the live DB to
    ``school.db.replaced.<timestamp>``, deletes any leftover
    `-wal`/`-shm` sidecars, copies the source in. Returns the renamed
    path so the UI can mention it in the success dialog. Caller is
    expected to prompt the user to restart -- the open connection is
    invalid afterwards.
  - `auto_backup` is wired to `QApplication.aboutToQuit` in
    `app/main.py`, so a clean exit always rolls a new backup.
- **Settings module (`app/ui/views/settings/`):**
  - `view.py` -- six-tab container.
  - `school_tab.py` -- editable school details with reload + save.
  - `backup_tab.py` -- list of auto-backups + manual backup + restore
    from list / restore from file (both gated by a two-step confirm).
  - `year_tab.py` -- list academic years, add new, set active.
  - `users_tab.py` -- list users, add (with password), edit (rename
    blocked, password optional, role + active toggle, in-place reset).
  - Embeds the existing `GradeScaleView` from Phase 5 unchanged as the
    "Grade scale" tab.
  - `audit_tab.py` -- reuses `PagedTableView` (Phase 2) with action /
    entity / from / to filters; refreshes the filter dropdowns when
    explicitly asked, so newly-introduced action names show up after
    a page hit.
- **Main window:** ``_builders[7] = _build_settings_view`` -- same
  lazy-load pattern as every other module, so Settings doesn't pay
  any boot cost until the user clicks it.
- **Packaging:**
  - `SchoolERP.spec` -- single-folder PyInstaller build. Bundles
    `app/db/migrations/*.sql` + `resources/`. Pulls in every
    reportlab font-encoding submodule that PyInstaller's static
    analysis misses (`reportlab.pdfbase._fontdata_*`). Excludes
    `tkinter`, `matplotlib`, `numpy.distutils`, and pytest collateral
    to keep the bundle small. GUI mode (`console=False`).
  - `build.bat` -- run from a Windows venv. Cleans `build/` and
    `dist/`, runs `pyinstaller --clean SchoolERP.spec`, points the
    user at `dist\SchoolERP\SchoolERP.exe`.
- **README rewrite:** end-user quick-start (drop the dist folder on a
  PC, click the .exe) + dev quick-start + how to build + backup /
  restore docs + project layout + locked stack table.
- **Tests added (14 new, 226 total):**
  - `test_audit_log_repo` (3): record + list ordering, filters,
    distinct helpers.
  - `test_backup_service` (4): auto-backup writes under BACKUP_DIR,
    trim keeps <= 14, manual backup produces a valid SQLite file,
    restore renames the old DB and the new live DB has the original
    contents.
  - `test_audit_wiring` (3): login records an event, failed login
    does not, payment collection records a `create` /
    `fee_payments` row tagged with the receipt no.
  - `test_settings_view` (4): six tabs render; School tab save round
    trip; Audit log tab lists records; Backup tab lists existing
    auto-backups under the redirected data dir.
- **Phase docs:** `PHASE_8_TESTS.md`, `PHASE_8_NOTES.md`.

## Decisions worth a quick review
1. **Audit is opt-in per write site.** We didn't try to retrofit every
   service write because the brief asks for "a viewer", not full
   coverage. The two highest-value events (logins + payments) are
   wired; a future enhancement adds class / staff / student CRUD with
   the same one-line `audit_service.record_event(...)` call.
2. **Audit failures swallow.** A failed audit insert logs a warning
   and returns. We don't want a hot path (login, payment) to fail
   because the audit table is, e.g., briefly locked.
3. **Restore preserves the old DB.** Renaming to
   ``.replaced.<timestamp>`` is the brief's recommended pattern --
   a "rollback" is just another restore from that file.
4. **Auto-backup runs even when the app crashed mid-session?** No.
   `aboutToQuit` only fires on a clean shutdown. If the OS kills the
   process, the most recent auto-backup is from the last successful
   shutdown. That's the brief's design -- WAL mode keeps the live DB
   consistent at any moment, and the next manual backup picks up
   today's changes.
5. **Settings tabs are flat (not nested wizard).** Quicker for the
   single-PC user. Each tab is independent; refreshing a tab on
   `currentChanged` keeps cross-tab edits visible.
6. **PyInstaller hidden imports.** reportlab dynamically loads font
   encodings; PyInstaller misses these without explicit
   `hiddenimports`. The list in the spec covers the standard 14
   PostScript fonts which is what our PDFs use.
7. **Year switcher refreshes only when each module's tab is opened.**
   Lighter than wiring a global "year changed" signal across modules.
   The Settings tab tells the user to "open each module's tab to
   refresh the year-scoped data" after activation.

## Deferred to a v2
- **Wider audit coverage** (student / class / staff / mark CRUD).
  Cheap to add now -- one `audit_service.record_event(...)` call per
  service write site.
- **Two-factor / per-action authorisation** (e.g. "only admin can
  delete a fee payment"). Currently roles are stored but not enforced
  at every action.
- **Year-rollover wizard** that copies classes, students (with class
  re-assignment), and fee structure from the previous year.
- **Data export bundle** (a ZIP of `data/` for off-site safekeeping).
- **Auto-update mechanism** -- the brief is offline-only, so this
  remains a manual swap of the `dist\SchoolERP\` folder.

## Performance check
- Cold start unchanged. Opening Settings imports the six tabs (each
  ~50-150 lines); ~120 ms on the dev laptop.
- Auto-backup of a 200-row test DB: ~30 ms. Manual backup is
  identical.
- Restore: pure file copy + sidecar cleanup. ~20 ms for a small DB.
- Audit log viewer paginates at 50 rows / page -- the same pattern
  used everywhere else in the app, so memory stays bounded.
- PyInstaller bundle (no PDF deps stripped): ~80 MB on disk. Fine on
  modern Windows but we may revisit if we need to fit on slow USB
  sticks.
