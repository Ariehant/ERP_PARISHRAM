# Phase 3 — Build notes

## What was built
- **Repos:**
  - `app/repositories/class_repo.py` — Class + Subject CRUD; `list_for_year`,
    `count_for_year`, `class_exists_for_year` (with `exclude_id` for
    self-update), `count_students_in_class` (used for the delete guard),
    and the `replace_subjects_for_class` diff-and-apply helper that
    inserts new rows, updates existing rows by id, and deletes any rows
    whose ids are no longer in the form.
  - `app/repositories/staff_repo.py` — Staff CRUD, paged + filtered list
    (`search`, `role`, `is_active`), `emp_code_exists` (with `exclude_id`),
    and `list_active_teachers` for the class-teacher dropdown.
- **Services:**
  - `app/services/class_service.py` — single `save_class` entry point that
    validates the class fields, validates each subject (name required,
    `max_marks > 0`, no duplicate subject names), and runs the class +
    subject diff in **one transaction**. `delete_class` refuses if any
    students are still attached.
  - `app/services/staff_service.py` — case-fold role, regex emp_code
    (letters/digits/`/-_`), phone + email + joining-date checks. `delete_staff`
    refuses when the staff member is referenced as a class teacher.
- **UI:**
  - `app/ui/views/masters/view.py` — `MastersView` with two tabs (Classes
    & Subjects | Staff). Switching back to the classes tab refreshes it
    so newly added/edited teachers show up in subject/teacher labels.
  - `app/ui/views/masters/staff_form.py` — admin form (emp code, name,
    role dropdown, phone, email, joining date, qualification, active).
  - `app/ui/views/masters/staff_list.py` — paged table with search +
    role + active filters and CRUD buttons.
  - `app/ui/views/masters/class_form.py` — top half is the class itself
    (name, section, year combo defaulting to the active year, class
    teacher combo from active teachers); bottom half is the inline
    subjects table (`QTableWidget` with name / code / max-marks spinner /
    optional checkbox), Add / Remove buttons. Each row tracks its
    original subject id for the diff-apply.
  - `app/ui/views/masters/class_list.py` — paged table showing
    `class / section / class teacher / subject count / student count`,
    with academic-year selector and CRUD buttons.
- **Students integration:**
  - `students/list_view.py` — the previously-disabled **Class** combo is
    now populated from `class_repo.list_for_year(active_year)` and
    triggers `_on_filter_changed` like the others.
  - `students/form_dialog.py` — Personal tab gains a **Class** dropdown
    (`(unassigned)` + every class in the active year). The form now
    writes the picked class id (previously copied from the existing
    student, so reassignment was impossible).
- **Main window:** `_builders[2] = _build_masters_view` — `MastersView`
  imports lazily on first sidebar click, same pattern as Phase 2.
- **Tests added (32 new, 107 total):**
  - `test_class_repo` — uniqueness within year, exclude-self, the
    diff-apply (insert / update / delete), cascade subjects on class
    delete, student counter.
  - `test_staff_repo` — uniqueness, exclude-self, role + active filters,
    search, paging, `list_active_teachers`.
  - `test_class_service` — validation cases (blank name, duplicate
    classes, duplicate subjects, zero max marks), full create + update
    flow, delete-with-attached-students guard, delete-when-empty success.
  - `test_staff_service` — normalisation (case-fold role, phone trim),
    role / email / duplicate guards, "is class teacher" delete guard.
  - `test_masters_view` (pytest-qt) — both tabs render, class form
    defaults to the active year, student form's class combo is populated
    by classes in the active year.

## Decisions worth a quick review
1. **Subjects are inline only.** The brief specifies "Class form lets you
   add subjects inline" — we don't expose a stand-alone Subjects
   list/CRUD view. If exam mark entry (Phase 5) needs cross-class
   subject management, we'll add it then.
2. **Diff-apply for subjects.** `replace_subjects_for_class` keeps any
   subject row that the form sends back with the same id, deletes the
   rest, and inserts new ones. This means existing marks (Phase 5) won't
   be wiped on a casual class edit — only when a subject is explicitly
   removed.
3. **Delete guards.** Class delete refuses when students are still
   assigned (forces explicit reassignment). Staff delete refuses when
   they're a class teacher (forces explicit reassignment). Both raise
   `ValidationError` so the UI shows a friendly message rather than a
   sqlite IntegrityError.
4. **Active-year scoping.** The class list and the student form/filter
   default to the active academic year. A future year switcher (Phase 8)
   only needs to update the active row in `academic_years`; both views
   call `school_repo.get_active_academic_year` on every refresh.
5. **Class teacher dropdown is *active* teachers only.** Inactive
   teachers don't appear in the dropdown (the brief implies "is_active"
   is the operational flag). Existing inactive class-teacher
   assignments still display via the cached teacher map; you'll just see
   `(unknown)` if the staff row was hard-deleted, not an exception.
6. **No paging optimisation for classes.** A school has ~10-30 classes
   per year. `list_for_year` returns the lot; paging is a no-op
   in-memory slice. Keeps the implementation simple and the page-size
   semantics consistent with the rest of the app.

## Deferred to later phases
- **Year switcher** in the status bar (Phase 8) and a way to copy
  classes/subjects from one year to the next.
- **Class roster** report (Phase 7).
- **Bulk class assignment from Excel import** for Students (Phase 4 or
  later — would extend `student_excel.read_rows` to accept a class
  label like `5-A` and resolve it).
- **Audit log** entries for create/update/delete on staff and classes
  (Phase 8).
- **Subject-level permissions / teaching staff per subject** — not
  scoped in the brief; revisit if Phase 5 needs it.

## Performance check
- Cold start unchanged. Opening Masters builds two list views at once;
  ~110 ms on a developer laptop. Switching tabs is instant.
- Class list rendering reads `list_subjects_for_class` per row to compute
  the subject count. With ~30 classes that's 30 cheap COUNT queries
  (indexed) — well under 100 ms in practice. If we ever scale to
  hundreds of classes we'd add a single GROUP BY query instead.
