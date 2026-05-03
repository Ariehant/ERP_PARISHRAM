# School ERP — Master Build Brief for Claude Code

You are building a **single-user desktop School ERP** for a small Indian school (200–300 students). The app must run smoothly on a **basic Intel i3, 4 GB RAM, Windows 10/11**, fully offline, with no server.

Read this entire document before writing any code. Then build the project in the **phases** defined at the bottom, **stopping at the end of each phase** for me to test before continuing.

---

## 1. Non-negotiable constraints

- **Target hardware:** Intel i3, 4 GB RAM, Windows 10/11, HDD (assume slow disk).
- **Idle RAM budget:** under 150 MB. **Cold start:** under 3 seconds. **Any screen open:** under 500 ms.
- **Single user, single PC, fully offline.** No network calls anywhere. No telemetry.
- **All long operations** (Excel import/export, PDF generation, backup) run on a `QThread` worker with a progress bar and a Cancel button. **Never block the UI thread.**
- **Never load full tables into memory or into a widget.** Use `QAbstractTableModel` with paged/keyset loading. Default page size: 50 rows.
- **No heavy ORM.** Use stdlib `sqlite3` with a thin repository layer. Dataclasses for models. SQLAlchemy is forbidden.
- **No Electron, no web frontend, no FastAPI, no Flask.** Native Qt only.
- **Excel via `openpyxl`** for read/write. **`pandas` only inside import workers**, never imported in UI modules.
- **PDF via `reportlab`** for receipts/certificates (precise layout) and **`weasyprint` is forbidden** (heavy deps on Windows). Report cards also use `reportlab`.
- **Charts:** `pyqtgraph` only. No matplotlib.
- **Python 3.11.** PySide6 (not PyQt). All deps must have Windows wheels on PyPI.

## 2. Stack (locked)

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| UI | PySide6 (Qt 6) |
| DB | SQLite (stdlib `sqlite3`), WAL mode |
| Excel | `openpyxl` (core), `pandas` (workers only) |
| PDF | `reportlab` |
| Charts | `pyqtgraph` |
| Packaging | PyInstaller (single-folder build) |
| Tests | `pytest`, `pytest-qt` |
| Lint/format | `ruff` (lint + format, single tool) |

## 3. SQLite configuration (apply on every connection open)

```python
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -20000;   -- ~20 MB page cache
PRAGMA mmap_size = 134217728; -- 128 MB
```

Use **one** long-lived connection on the UI thread for reads, and **separate connections inside worker threads** for writes/imports. Never share a connection across threads.

## 4. Architecture

Strict layering. Violations should fail code review.

```
UI (views, widgets)
   ↓ calls
Services (business logic: fee calc, grade calc, promotion, validation)
   ↓ calls
Repositories (all SQL lives here, returns dataclasses)
   ↓ uses
DB connection layer
```

- **No SQL in UI files.** Ever.
- **No Qt imports in services or repositories.** Services and repos must be unit-testable without a Qt app.
- Repositories return **dataclasses**, not tuples or dicts.
- All money values stored as **integer paise** (multiply rupees by 100). Never use float for money.
- All dates stored as ISO strings (`YYYY-MM-DD`) or as `INTEGER` Julian days — pick one and document it. Default: ISO strings.

(Full brief continues — see source document for the schema, coding rules, UI rules,
backup policy, testing rules, deliverables, and the complete phase plan.)
