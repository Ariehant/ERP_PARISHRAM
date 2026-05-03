# Phase 4 - Manual test checklist (run on the target i3)

> Goal: take attendance, view a monthly matrix, and generate the three PDFs.
> Verify the UI never blocks during PDF generation.

## Prerequisites
- Phase 3 already passed.
- At least one class with 5+ active students assigned.

## 1. Open the Attendance view
1. Sign in, click **Attendance** in the sidebar.
2. **Expect:** the view opens within ~500 ms with three tabs: **Daily**,
   **Monthly**, **Reports**. Default tab is Daily.

## 2. Daily entry
1. Pick a class. The roster loads automatically. Today's date is
   pre-selected.
2. **Expect:** one row per active student, with empty radio cells in
   columns P / A / L / H. Footer shows "N active student(s) ... 0 already
   marked for YYYY-MM-DD."
3. Click **Mark all present**. Every row should now have **P** selected.
4. Change a couple of rows to A and L manually.
5. Click **Save**. Footer changes to "Saved N mark(s) for YYYY-MM-DD."
6. Switch to a different date, then back. **Expect:** the saved
   selections are restored. Footer says "N already marked for ...".
7. Try **Save** with no rows selected (after picking a date with no marks):
   **Expect** "No students are marked yet" message (no DB write).

## 3. Monthly matrix
1. Switch to **Monthly**. Pick the same class and the month you marked
   above.
2. **Expect:** a wide grid with one row per active student, one column
   per day of the month, plus Roll / Name on the left and **%** on the
   right.
3. Cells with a saved status show the letter (P/A/L/H), colour-coded:
   green = P, red = A, yellow = L, grey = H. Other cells are empty.
4. The **%** column matches the convention in the notes: late counts
   as attended, holidays excluded.

## 4. Reports
1. Switch to **Reports**. Pick a class.
2. **Daily attendance register**: pick a date, click "Generate PDF".
   - **Expect:** a modal "Generating PDF" briefly shows, then a
     "Saved to: ..." confirmation. Open the file: school header, class
     name, date, table of Roll/Name/Status, signature block.
3. **Monthly attendance summary**: pick month + year, generate.
   - **Expect:** a table per student with P/A/L/H counts, total marked,
     and percentage. Footer note explains the formula.
4. **Low attendance list**: month + year + threshold (default 75%),
   generate.
   - **Expect:** only students below the threshold (with at least one
     marked session) appear. Title shows the chosen threshold.
   - Edit a student's marks so they cross the threshold; regenerate
     the PDF to confirm the list updates.

## 5. Cross-module wiring
- Add a new class in **Classes & Staff**. Switch back to Attendance
  (any tab) - the class combo should refresh and include the new class
  next time you switch tabs (the tab refresh fires on tab change).

## 6. UI responsiveness
- During each PDF generation the main window must remain responsive.
  Try resizing or scrolling the daily grid in another tab while a PDF
  is being built.

## 7. Automated suite
```bash
QT_QPA_PLATFORM=offscreen pytest
```
**Expect:** all 129 tests pass.

## 8. Lint / format
```bash
ruff check .
ruff format --check .
```
Both clean.
