# School ERP

Single-user, fully offline desktop School ERP for small Indian schools
(200-300 students). Built with **Python 3.11 + PySide6 + SQLite (stdlib)**.
Targets a basic Intel i3 / 4 GB RAM Windows 10/11 PC.

> **Status:** all eight phases complete. The app supports student
> management, attendance, exams + auto-graded marks, fees + receipts,
> a reports hub, and a Settings screen with backup / restore / audit
> log.

---

## Quick start (end-user)

If you received a packaged `dist\SchoolERP\` folder:

1. Copy the entire `SchoolERP` folder onto the Windows PC (e.g. to
   `C:\SchoolERP\`).
2. Double-click `SchoolERP.exe` inside that folder.
3. On first launch the **Setup Wizard** asks for the school name, the
   academic year, and the first administrator account.
4. On subsequent launches the **Login** dialog appears; sign in with
   the admin you created.
5. All data is stored under `data\` next to the executable
   (`data\school.db` plus photo / document / backup folders).

---

## Run from source (developers)

```bash
git clone <repo-url> erp_parishram
cd erp_parishram

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"

python -m app.main
```

Add `--debug` for DEBUG-level logs:

```bash
python -m app.main --debug
```

`SCHOOL_ERP_DATA=<path>` redirects the runtime data dir (useful for
PyInstaller deployment or for keeping a parallel test database).

## Run tests

```bash
QT_QPA_PLATFORM=offscreen pytest
```

226 tests cover repos, services (validation + transactional behaviour),
PDF generators (magic-bytes), Excel I/O, and pytest-qt UI smoke for
every module.

## Lint / format

```bash
ruff check .
ruff format .
```

## Build a Windows executable

From a Windows machine with the dev extras installed:

```cmd
build.bat
```

This runs `pyinstaller --clean SchoolERP.spec` and produces
`dist\SchoolERP\SchoolERP.exe` plus a folder of supporting DLLs and
data files (single-folder mode). Copy the entire `dist\SchoolERP\`
folder to the target PC. The folder is self-contained -- no Python
install required on the target.

The spec file bundles:
- the SQL migrations under `app/db/migrations/`,
- the static resources directory,
- every reportlab font-encoding submodule that PyInstaller's
  static analysis misses.

## Backup, restore, and data layout

Runtime layout under `data/`:

```
data/
├── school.db                  SQLite database (WAL mode)
├── logs/app.log               rotating log (5 MB x 3)
├── backups/                   auto-backups (kept = last 14)
├── photos/                    student photos (UUID filenames)
└── documents/                 student documents (UUID filenames)
```

**Auto-backup:** every clean shutdown writes
`data/backups/auto_YYYYMMDD_HHMMSS.db` using SQLite's online backup
API. Older auto-backups beyond the most recent 14 are removed.

**Manual backup:** open the app -> sidebar -> **Settings** ->
**Backup && restore** tab -> "Save manual backup..." -> pick a path.

**Restore:** same tab. Either pick a row in the auto-backup list and
click "Restore from selected...", or use "Restore from file..." to
pick any `.db`. The current DB is renamed to
`school.db.replaced.<timestamp>` first so nothing is lost; you'll
need to close and reopen the app afterwards.

**Audit log:** every login and every fee-payment collection is
recorded with timestamp + user. View it from **Settings** ->
**Audit log** with action / entity / date filters.

## Project layout

```
app/
├── main.py                    entry point
├── config.py                  paths + constants
├── db/
│   ├── connection.py          PRAGMAs + transaction context manager
│   ├── migrator.py            SQL migrations runner
│   └── migrations/            001..003 .sql files
├── models/                    frozen-slot dataclasses
├── repositories/              all SQL lives here
├── services/                  business logic + validation
├── reports/                   PDF + Excel generators (reportlab + openpyxl)
├── workers/                   QThread workers (import / export / PDF / backup)
├── ui/
│   ├── main_window.py
│   ├── widgets/               reusable (PagedTableView etc.)
│   └── views/                 one folder per module
├── utils/                     errors, logging, formatters, security, words
└── ...
```

See `PROJECT_BRIEF.md` for the full design contract and the
`PHASE_<n>_NOTES.md` files for build decisions per phase.

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| UI | PySide6 (Qt 6) |
| DB | SQLite (stdlib `sqlite3`), WAL mode |
| Excel | `openpyxl` (workers may also use `pandas`) |
| PDF | `reportlab` |
| Tests | `pytest`, `pytest-qt` |
| Lint / format | `ruff` (single tool) |
| Packaging | PyInstaller (single-folder build) |

No network calls, no telemetry, no cloud dependencies. Everything
runs on the local PC.
