# Phase 8 - Manual test checklist (run on the target i3)

> Goal: confirm the Settings tabs work, auto-backup fires on shutdown,
> a manual restore is reversible, audit-log entries appear, and the
> PyInstaller build produces a runnable bundle.

## Prerequisites
- Phase 7 already passed.
- A reasonable amount of data: a few students, a class with a fee
  structure, and at least one fee payment (so audit + ledger have
  something to show).

## 1. Settings opens
1. Sign in, click **Settings** (8th sidebar entry).
2. **Expect:** view opens within ~500 ms with six tabs:
   School / Backup && restore / Academic year / Users / Grade scale /
   Audit log.

## 2. School tab
1. Open **School**. Existing school details are loaded.
2. Edit the address, click **Save** -> "School details updated."
3. Close and reopen the app -> changes persist (status bar shows the
   new school name on the next login).

## 3. Backup tab
1. Open **Backup && restore**. The "Recent auto-backups" list shows
   any past auto-backups (or "(no auto-backups yet)" if this is the
   first run).
2. Click **Save manual backup...** -> pick a path -> "Saved to: ...".
   Open the resulting `.db` with any SQLite tool to confirm it has
   the same data.
3. Cleanly close the app (window close or `Ctrl+Q`). Reopen
   **Settings** -> **Backup && restore**. **Expect:** a new
   `auto_<timestamp>.db` row at the top of the list.
4. Generate >14 dummy auto-backups by closing/opening the app
   repeatedly (or wait through several days). Verify that the list
   never exceeds 14.

## 4. Restore (round-trip)
1. Make a manual backup somewhere safe.
2. In **Settings** -> **Backup && restore**, pick the manual backup
   you just made -> "Restore from file..." -> confirm twice.
3. **Expect:** "DB restored. Old DB saved as: school.db.replaced.<ts>"
   message. Close the app and reopen -- the data should match the
   moment of backup.
4. (Optional rollback) The pre-restore DB is preserved next to
   `data/school.db` as `school.db.replaced.<timestamp>`. To roll back,
   pick that file via **Restore from file...**.

## 5. Academic year tab
1. Open **Academic year**. The current year is marked Active = Yes.
2. Click **Add year...** -> label `2026-27`, default dates -> OK.
3. Pick the new row -> **Set selected as active**. Confirm.
4. Open the **Students** sidebar -> the Class filter drops to "(no
   classes)" because 2026-27 has none yet. Switch back to the original
   year via the Settings tab to restore.

## 6. Users tab
1. Open **Users**. The admin you created in setup is listed.
2. **Add user...** -> username `cashier`, role `operator`, password
   `cashier1` -> Save.
3. Close the app, reopen -> log in as `cashier / cashier1`.
4. Reopen the app as `admin`, edit `cashier` to **Active = unchecked**,
   try to log in as `cashier` -> "This account has been disabled."

## 7. Grade scale tab
- This is the same editor from Phase 5, embedded as a tab. Verify it
  loads the eight default bands and saves edits correctly.

## 8. Audit log tab
1. Open **Audit log**. **Expect:** at least the most recent login
   event. Filter Action = `login` -> only logins.
2. Make a fee payment in **Fees** -> **Collection**. Switch back to
   **Audit log** -> click **Refresh**. **Expect:** a new
   `create / fee_payments / RCP/...` row.
3. Use the date-range filter to narrow to today; verify the count
   updates.

## 9. PyInstaller build (Windows)
1. From a Windows machine with the dev extras installed, run
   `build.bat` from the repo root.
2. **Expect:** `dist\SchoolERP\SchoolERP.exe` is produced (folder
   contains the exe + DLLs + bundled data).
3. Copy the entire `dist\SchoolERP\` folder to a clean Windows PC
   without Python installed. Double-click the `.exe`.
4. **Expect:** the Setup Wizard runs and a fresh `data\` folder is
   created next to the executable. RAM stays under 150 MB after the
   main window opens.

## 10. Automated suite
```bash
QT_QPA_PLATFORM=offscreen pytest
```
**Expect:** all 226 tests pass.

## 11. Lint / format
```bash
ruff check .
ruff format --check .
```
Both clean.
