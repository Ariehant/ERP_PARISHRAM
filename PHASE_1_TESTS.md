# Phase 1 — Manual test checklist (run on the target i3)

> Goal: confirm the app boots, runs migrations, walks the setup wizard, logs
> in, and shows the main window shell. No modules wired up yet.

## Prerequisites
- Python 3.11 (`python --version`).
- Fresh checkout. From the repo root:
  ```bash
  python -m venv .venv
  .venv\Scripts\activate         # Windows
  pip install -e ".[dev]"
  ```

## 1. Cold-start (first run)
1. From the repo root, ensure `data/` does **not** exist (delete it if it does).
2. Run:
   ```bash
   python -m app.main
   ```
3. **Expect:**
   - The window appears in **under 3 seconds** on the i3.
   - `data/`, `data/logs/`, `data/backups/`, `data/photos/`, `data/documents/`
     are created.
   - `data/school.db` is created (a `.db-wal` and `.db-shm` may appear too —
     that is WAL mode working).
   - The **Setup Wizard** opens.

## 2. Setup wizard happy path
1. Page 1 — School details:
   - Try clicking "Next" with the school name blank. **Expect:** Next stays
     disabled.
   - Fill in school name (e.g. "Parishram Public School") + any other fields.
2. Page 2 — Academic year:
   - Defaults to the Indian April–March year for the current calendar year.
     Edit if needed.
3. Page 3 — Administrator account:
   - Type a 5-character password. Click Finish. **Expect:** "Password too
     short" warning.
   - Type a 6+ character password and a different confirm value. Click Finish.
     **Expect:** "Passwords don't match" warning.
   - Type matching 6+ character passwords. Click Finish.
4. **Expect:** Wizard closes, **Main Window** opens directly (no extra login
   on first run because the wizard already authenticated you).

## 3. Main Window (first run)
- The status bar shows **school name | user (role) | Year: <label>** on the
  left and the DB path on the right.
- The left sidebar lists Dashboard, Students, Classes & Staff, Attendance,
  Exams & Marks, Fees, Reports, Settings.
- Clicking each sidebar entry switches to the corresponding placeholder pane
  ("coming in Phase N…"). RAM stays roughly flat.
- Close the window. The app exits cleanly.

## 4. Subsequent run (login flow)
1. Run `python -m app.main` again.
2. **Expect:** the **Login** dialog appears — *not* the wizard.
3. Try wrong password → red error message under the form.
4. Type correct password → main window opens. Same status-bar info as before.

## 5. Debug logging
- Run `python -m app.main --debug`. **Expect:** more verbose lines in
  `data/logs/app.log` and the console.

## 6. Automated suite
From the repo root:
```bash
QT_QPA_PLATFORM=offscreen pytest
```
**Expect:** all green. Covers migrator, repositories, services, formatters,
password hashing, and UI smoke (main window opens, login accepts/rejects).

## 7. Lint / format
```bash
ruff check .
ruff format --check .
```
Both should be clean.

## What to look for
- ⏱️ Cold start under ~3 s on the i3.
- 🧠 Idle RAM ≪ 150 MB after main window opens.
- 🗄️ `data/school.db` is in WAL mode (sidecar files exist).
- 🔐 The app **never** stores a plaintext password anywhere (`grep` the DB
  file or the logs to confirm).
