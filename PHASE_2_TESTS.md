# Phase 2 — Manual test checklist (run on the target i3)

> Goal: verify the full students module — list, add, edit, view, delete,
> Excel template / import / export — works end-to-end without blocking the UI.

## Prerequisites
- Phase 1 already passed.
- App run from source (`pip install -e ".[dev]"`, then `python -m app.main`)
  with the existing `data/school.db`, or a fresh wipe.

## 1. Open the Students view
1. Launch the app, sign in.
2. Click **Students** in the sidebar.
3. **Expect:** the list view opens within ~500 ms. Empty grid + "No rows."
   in the footer if you have no students yet. Toolbar shows search box,
   Status / Class filters, and Add / Edit / View / Delete / Import / Export
   buttons. (Class filter is disabled — populated in Phase 3.)

## 2. Add a student
1. Click **Add** (or `Ctrl+N`).
2. **Personal tab:**
   - Try saving with admission no. blank → red "Admission no. is required"
     warning.
   - Try admission no. with a space, e.g. `ADM 1` → format warning.
   - Try a valid admission no. (e.g. `ADM/2025/001`), first name, leave
     other fields default. Click **Save**.
3. **Expect:** dialog closes; new row appears in the list.
4. Re-open Add and pick a **photo** (`.jpg`/`.png`/`.webp`):
   - Pick a small image (< 5 MB) → preview thumbnail appears.
   - Pick a `.pdf` → "Unsupported photo type" warning.
   - Save. **Expect:** a file lands under `data/photos/<uuid>.jpg` (the
     filename is randomised).

## 3. Search & filter
1. Add a few students (3–4 with different names).
2. Type part of a name in the search box → press Enter. **Expect:**
   list filters in real time, footer shows "Showing 1-N of N rows."
3. Change Status filter to "Inactive" → list shows nothing (no inactive
   students yet). Switch back to "All".

## 4. Pagination (with > 50 students, e.g. via Import in §6)
- Make sure the table never holds more than 50 rows in memory.
- Footer shows `Page X of Y`. Prev / Next buttons enable / disable correctly.
- Memory in Task Manager stays under ~150 MB while clicking through pages.

## 5. Edit, View, Delete
1. Select a row → buttons enable.
2. **Edit** → changes save → list refreshes.
3. **View** (or double-click) → read-only profile dialog with photo. Close.
4. **Delete** → confirmation prompt warns that attendance/marks/fees rows
   will cascade. Confirm → row disappears. Cancel on a real student to
   verify cancellation works.

## 6. Excel template + import
1. Click **Import…** to open the import dialog.
2. Click **Save template…** → choose any folder. **Expect:** an `.xlsx`
   with a "Students" sheet (header + sample row in italics) and a "Notes"
   sheet.
3. Open the template in Excel/LibreOffice. Add 3-5 real rows. Include at
   least:
   - one row with a duplicate admission no. of an existing student,
   - one row with a bad date (e.g. `01/04/2025`),
   - one row that's perfectly valid.
   Save as `students.xlsx`.
4. Back in the import dialog, **Pick file…** → select your file.
5. **Expect:** progress bar fills, then the preview table appears. Invalid
   rows are highlighted in light red, with errors in the last column. The
   summary shows `Validated N row(s): X valid, Y with errors.`
6. Click **Import valid rows** → confirm. **Expect:** "Imported N student(s)"
   and the list refreshes with the new rows.
7. Re-open the import dialog and import the same file again. **Expect:**
   every row should now be flagged as duplicate (existing in DB).

## 7. Export
1. Apply a search filter (e.g. only "active").
2. Click **Export…** → choose a path.
3. **Expect:** A modal "Exporting…" dialog (with Cancel) appears very
   briefly, then a "Saved to: …" confirmation. The file matches the
   filtered list.

## 8. UI responsiveness
- During Import and Export, the main window must stay interactive — try
  scrolling the list or resizing the window. There must be **no spinning
  beachball** on the UI thread.

## 9. Automated suite
```bash
QT_QPA_PLATFORM=offscreen pytest
```
**Expect:** all 75 tests pass.

## 10. Lint / format
```bash
ruff check .
ruff format --check .
```
Both clean.
