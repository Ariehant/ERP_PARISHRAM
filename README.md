# School ERP

Single-user, fully offline desktop School ERP for small Indian schools (200–300 students). Built with **Python 3.11 + PySide6 + SQLite (stdlib)**. Targets a basic Intel i3 / 4 GB RAM Windows 10/11 PC.

> **Status:** Phase 1 (Foundation) complete. Database schema, setup wizard, login, and main-window shell are runnable. Modules (students, attendance, exams, fees, reports) land in subsequent phases.

---

## Run from source

```bash
# Clone and enter the repo
git clone <repo-url> erp_parishram
cd erp_parishram

# Create a venv (Python 3.11)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / mac
source .venv/bin/activate

# Install runtime + dev dependencies
pip install -e ".[dev]"

# Launch
python -m app.main
```

On first launch the app:

1. Creates `data/` (and `data/logs/`, `data/backups/`, `data/photos/`, `data/documents/`).
2. Runs database migrations (creates `data/school.db` in WAL mode).
3. Shows the **Setup Wizard** if no school exists — collect school details, first academic year, and the first admin user.
4. On subsequent launches, shows the **Login** dialog and then the **Main Window**.

Add `--debug` for DEBUG-level logs:

```bash
python -m app.main --debug
```

## Run tests

```bash
pytest
```

Headless Qt tests are enabled by setting `QT_QPA_PLATFORM=offscreen`:

```bash
QT_QPA_PLATFORM=offscreen pytest
```

## Lint / format

```bash
ruff check .
ruff format .
```

## Build a Windows executable

(Phase 8 — not yet implemented.) Will use PyInstaller in single-folder mode.

---

## Project layout

```
app/
├── main.py                 # entry point
├── config.py               # paths + constants
├── db/
│   ├── connection.py       # connection factory + PRAGMAs
│   ├── migrator.py         # applies SQL migrations on startup
│   └── migrations/         # 001_initial.sql, ...
├── models/                 # frozen-slot dataclasses (one file per aggregate)
├── repositories/           # all SQL lives here
├── services/               # business logic / validation
├── ui/                     # PySide6 views, widgets, dialogs
├── workers/                # QThread workers (import/export/PDF/backup)
├── reports/                # PDF + Excel generators
└── utils/                  # errors, logging, formatters, security
```

See `PROJECT_BRIEF.md` for the full design contract.

## Backup & data

- All runtime data lives under `data/` (gitignored). The app expects to be free to write there.
- Auto-backups are written to `data/backups/auto_*.db` on clean shutdown (Phase 8).
- Photos and documents land under `data/photos/` and `data/documents/` with UUID filenames.
