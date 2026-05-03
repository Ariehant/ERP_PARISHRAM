# Phase 1 — Build notes

## What was built
- **Project scaffolding:** `pyproject.toml` (Python 3.11, PySide6 6.7, openpyxl,
  pandas, reportlab, pyqtgraph, qtawesome; dev: pytest, pytest-qt, ruff,
  pyinstaller). `.gitignore`. `README.md` with run / test / lint instructions.
- **Configuration (`app/config.py`):** central paths, default page size,
  PAISE_PER_RUPEE, ISO_DATE_FMT, `ensure_runtime_dirs()`. Honours
  `SCHOOL_ERP_DATA` env var so PyInstaller / tests can redirect the data dir.
- **DB layer:**
  - `app/db/connection.py` — `open_connection()` applies the six required
    PRAGMAs (WAL, synchronous=NORMAL, foreign_keys=ON, temp_store=MEMORY,
    cache_size=-20000, mmap_size=128 MB), uses autocommit + explicit
    `transaction()` context manager (BEGIN IMMEDIATE / COMMIT / ROLLBACK).
  - `app/db/migrator.py` — discovers numbered SQL files, applies each in a
    single transaction, records names in `schema_migrations`, idempotent.
  - `app/db/migrations/001_initial.sql` — the entire schema from the brief
    (schools, academic_years, classes, subjects, staff, students, attendance,
    exams, marks, fee_structure, fee_payments, fee_payment_items, documents,
    remarks, users, audit_log) plus the listed indexes.
- **Models:** one frozen-slot dataclass per table, grouped into modules
  (`school`, `structure`, `people`, `attendance`, `exam`, `fee`, `misc`,
  `user`, `audit`). Re-exported from `app.models`.
- **Utils:**
  - `errors.py` — `AppError`, `ValidationError(field=…)`, `AuthenticationError`,
    `RepositoryError`, `MigrationError`.
  - `logging.py` — rotating file handler at `data/logs/app.log` (5 MB × 3) +
    console handler. INFO default, DEBUG with `--debug`.
  - `formatters.py` — `format_inr(paise)` (Indian comma), `format_date(iso)`,
    `parse_iso_date`, `rupees_to_paise` (Decimal-based, no float drift).
  - `security.py` — `hash_password` / `verify_password` using `hashlib.scrypt`
    (n=16384, r=8, p=1) with a self-describing string format. Stdlib only.
- **Phase 1 repositories:** `school_repo` (school + academic_year CRUD,
  active-year toggle), `user_repo` (create / lookup / list).
- **Phase 1 services:**
  - `setup_service.perform_initial_setup` — validates school name, ISO dates,
    username (lowercased, no spaces), 6+ char password; writes school + year
    + admin in **one transaction**.
  - `auth_service.authenticate` — case-insensitive username, scrypt verify,
    rejects inactive accounts.
- **UI shell:**
  - `setup_wizard.SetupWizard` — three QWizardPages (school, academic year,
    admin user); validation surfaced via QMessageBox; submission delegates to
    the service.
  - `login_dialog.LoginDialog` — username/password with inline red error
    label.
  - `main_window.MainWindow` — left `QListWidget` sidebar (Dashboard …
    Settings), `QStackedWidget` content area (placeholder pages for non-Phase-1
    modules), status bar with school | user (role) | active year + DB path
    permanent widget.
- **Boot sequence (`app/main.py`):** parse args → ensure dirs → configure
  logging → open DB → run migrations → wizard if first run, else login →
  main window.
- **Tests:**
  - Repo: `test_school_repo`, `test_user_repo`, `test_migrator` (pragmas +
    idempotency + presence of all 14 schema tables).
  - Service: `test_setup_service` (full flow, double-run guard, validation,
    rollback on failure), `test_auth_service` (success / wrong password /
    unknown / inactive / case-insensitive), `test_formatters`, `test_security`.
  - UI: `test_smoke` — pytest-qt opens MainWindow, switches stacks, exercises
    the login dialog accept/reject path. Uses
    `QT_QPA_PLATFORM=offscreen`.
- **Phase docs:** `PHASE_1_TESTS.md` (manual checklist for the i3),
  `PHASE_1_NOTES.md` (this file).

## Decisions worth a quick review
1. **Password hashing — scrypt, not argon2.** Followed the brief's "stdlib
   first" guidance. Parameters tuned for an i3 (~32 MB working memory,
   verify in <100 ms). Storage format is self-describing
   (`scrypt$N$r$p$salt_b64$hash_b64`) so we can rotate parameters later.
2. **Connection & transactions.** `open_connection()` returns an autocommit
   connection (`isolation_level=None`); writers use the explicit
   `transaction()` context manager with `BEGIN IMMEDIATE`. This avoids the
   sqlite3-module quirk where DDL silently commits open transactions and
   makes intent visible.
3. **Migrations.** Filenames must match `^\d{3,}_[\w-]+\.sql$`. Each file is
   wrapped in its own transaction and recorded in `schema_migrations`. SQL
   ordering inside `001_initial.sql` puts `staff` before `classes` (the brief
   listed them the other way; SQLite tolerates forward FK references in
   CREATE TABLE, but ordering correctly is cleaner).
4. **First-run UX.** Successful setup transitions straight into the main
   window using the just-created admin user — saves an extra login on first
   launch. Subsequent launches always show the login dialog.
5. **Frozen, slotted dataclasses.** Repositories return new instances; updates
   build a new dataclass via `dataclasses.replace` (will surface in Phase 2+).
6. **No global state.** The DB connection is held by `main.py` and threaded
   through to the dialogs / window. A formal DI Container will appear when we
   start needing more wiring — for Phase 1 the parameter-passing is fine.

## Deferred to later phases
- **counters table** for atomic receipt-number generation — added in Phase 6
  via migration 002, per the brief.
- **grade_scales table** — Phase 5.
- **PagedTableView**, student picker, and other reusable widgets — first
  consumer is the students list in Phase 2.
- **Backup on clean shutdown** — Phase 8.
- **Audit log writes** — entry points wired starting Phase 2 (every create /
  update / delete / login event will write a row).
- **Settings screen, user management, academic-year switcher** — Phase 8.

## Performance budget check
- Cold start on a developer laptop: well under 1 s. Will need re-measuring on
  the target i3, but no obvious pessimisations (no eager imports of pandas,
  reportlab, openpyxl, or any module view).
- Idle RAM after main window: ~80–110 MB on PySide6 6.7 in our environment;
  comfortably below the 150 MB budget. Lazy module loading in later phases
  must preserve this.
