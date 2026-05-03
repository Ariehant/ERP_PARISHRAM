# Phase 3 — Manual test checklist (run on the target i3)

> Goal: build a usable masters set — classes (with subjects inline) and
> staff — and verify they wire into the students module.

## Prerequisites
- Phase 2 already passed.
- `python -m app.main` works.

## 1. Open the Masters view
1. Sign in, click **Classes & Staff** in the sidebar.
2. **Expect:** the view opens within ~500 ms with two tabs:
   `Classes & Subjects` and `Staff`.

## 2. Add staff
1. Switch to the **Staff** tab. Click **Add**.
2. Try saving with employee code blank → "Employee code is required."
3. Pick role **teacher**, name **Asha Mehta**, code **EMP/2025/001**,
   phone `9876543210`, joining date today. Save.
4. Add another staff: emp code **EMP/2025/002**, name **R. K. Singh**,
   role **principal**.
5. Add an **inactive** teacher: code **EMP/2025/003**, name **Old Teacher**,
   uncheck *Active*, save.
6. **Expect:** all three appear in the list. Filter Role = Teacher → 2 rows.
   Filter Status = Inactive → 1 row.
7. Try **Delete** on the principal → confirms then deletes (no FK refs).
8. Try **Delete** on Asha Mehta. (We'll come back to this in §3.)

## 3. Add a class with subjects
1. Switch to the **Classes & Subjects** tab. Active year is preselected.
2. Click **Add class**.
3. **Class details:** Name `5`, Section `A`, Class teacher = **Asha
   Mehta** (the dropdown only lists *active teachers*).
4. **Subjects:**
   - Click **Add subject**. Type `Math`, code `MAT`, max marks 100.
   - Click **Add subject**. Type `English`, max marks 80.
   - Click **Add subject**. Leave name blank → on Save you should see
     "Subject name is required." Remove it (select row, **Remove
     selected**).
   - Try two rows both named `Math` (different cases) → "Subject 'math'
     appears more than once." Fix.
5. Save. **Expect:** dialog closes, the row shows `5 / A / Asha Mehta /
   2 subjects / 0 students`.
6. Try saving a second class `5` / `A` for the same year → "Class 5-A
   already exists for this academic year."
7. **Edit** the class. Change Section to `B`, drop English, add
   `Science` (max 100). Save. **Expect:** subject count updates to 2
   without losing Math (and its `MAT` code).
8. Now go back to the Staff tab and try **Delete** Asha Mehta →
   "Cannot delete: this staff member is the class teacher of 1 class(es).
   Reassign first." Edit the class → set Class teacher = `(unassigned)`
   → Save → Delete Asha. Re-add a teacher for the next steps.

## 4. Class scoping by year
- The class list defaults to the *active* year. Add a new (inactive) year
  later in Phase 8; classes for that year shouldn't appear here. (Skip
  if you don't have a second year yet.)

## 5. Wire-up in Students
1. Open the **Students** sidebar entry.
2. **Expect:** the **Class:** filter is now enabled and lists `5-A` (or
   whatever you saved).
3. Open **Add** student → in the Personal tab, the **Class** dropdown
   shows `(unassigned)` plus the year's classes. Pick `5-A`. Save.
4. Filter by Class = `5-A` → only shows students in that class.
5. **Edit** a student, change class to `(unassigned)`, save → now the
   filter excludes them.

## 6. Delete-with-guard
1. Add a student in class `5-A`. From the masters view, try **Delete** the
   class → "Cannot delete: 1 student(s) are still assigned…"
2. From the students view, change the student's class to `(unassigned)`,
   save. Try the class delete again → succeeds.

## 7. Automated suite
```bash
QT_QPA_PLATFORM=offscreen pytest
```
**Expect:** all 107 tests pass.

## 8. Lint / format
```bash
ruff check .
ruff format --check .
```
Both clean.

## What to look for
- Idle RAM after opening Masters: under 150 MB.
- Switching tabs and filters is instant — no perceptible pause on the i3.
- Subjects are saved atomically with the class (if the inline list has a
  validation error, *neither* the class nor the subjects change).
