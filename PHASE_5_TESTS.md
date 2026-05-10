# Phase 5 - Manual test checklist (run on the target i3)

> Goal: create exams, enter subject-wise marks for a class+exam with
> auto-graded results, and round-trip via the Excel template.

## Prerequisites
- Phase 4 already passed.
- Migration 002 has run automatically -- verify by opening the **Grade
  scale** tab; you should see the default 8 bands (A+ ... F).

## 1. Open the Exams view
1. Sign in, click **Exams & Marks** in the sidebar.
2. **Expect:** the view opens within ~500 ms with three tabs: **Exams**,
   **Marks entry**, **Grade scale**.

## 2. Add an exam
1. In the **Exams** tab, click **Add exam**.
2. Try saving with the name blank -> "Exam name is required."
3. Set name **Mid-term I**, type **midterm**, start **2025-09-01**, end
   **2025-09-08**, weightage **100**. Save.
4. **Expect:** a row appears with "Marks recorded: 0".

## 3. Enter marks
1. Switch to the **Marks entry** tab.
2. Pick the class (e.g. `5-A` from Phase 3) and the exam **Mid-term I**.
3. **Expect:** a grid with one row per active student, columns
   `Roll | Name | <Subject1>\n(max=N) | <Subject2>\n(max=N) | ...`.
   Empty cells display "-".
4. Enter marks for a few students. Try entering 200 in a max=100 column
   -> the spinbox clamps to 100 (range enforcement).
5. Click **Save marks**. Footer says "Saved N mark(s)".
6. Re-pick the same class+exam. **Expect:** the previously saved values
   are restored.

## 4. Auto-grade verification
- Pick scores that span grade bands and confirm:
  - 95 / 100 -> **A+**
  - 72 / 100 -> **B+**
  - 30 / 100 -> **F**
- (You can verify by looking at the saved row in the **Marks recorded**
  count of the **Exams** tab, which should grow.)

## 5. Excel template + import
1. In **Marks entry**, click **Save template...** -> pick a folder.
2. Open the file. Verify:
   - Sheet "Marks" has columns: `Admission No`, `Roll`, `Name`, then one
     `<Subject> (max=N)` column per subject of the class.
   - Each active student has their admission no., roll and name pre-filled.
   - "Notes" sheet explains the format.
3. Fill in marks for a couple of students. Try one row with marks > max
   to provoke an error during validation.
4. Click **Import from Excel...** in **Marks entry**. Pick your file.
5. **Expect:** preview table shows rows with cells filled and any
   errors highlighted in light red. Click **Import valid rows** -> a
   confirmation dialog -> "Saved N mark(s)".
6. The grid in **Marks entry** refreshes to show the imported values.

## 6. Grade scale editor
1. Switch to the **Grade scale** tab.
2. Default 8 bands are listed.
3. Add a new band "EXC" with 99-100, save. **Expect:** "Bands overlap"
   error (overlaps A+).
4. Edit A+ to 95-100, then re-add EXC 96-100 -> still overlaps. Set EXC
   to 99-100 (overlap with A+ 95-100): error.
5. Make A+ 95-98.99 and EXC 99-100 -> save succeeds. Re-enter a 99/100
   in marks entry and verify the grade is now **EXC**.
6. Reload to verify persistence; restore the original 8 bands afterward
   (A+: 90-100, A: 80-89.99, ...).

## 7. Cross-module wiring
- Add a student in **Students** -> they appear in the marks-entry grid
  next time you re-pick the class.
- Add a subject to the class in **Classes & Staff** -> a new column
  appears in the marks-entry grid.

## 8. Automated suite
```bash
QT_QPA_PLATFORM=offscreen pytest
```
**Expect:** all 160 tests pass.

## 9. Lint / format
```bash
ruff check .
ruff format --check .
```
Both clean.
