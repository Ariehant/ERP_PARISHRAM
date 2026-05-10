# Phase 7 - Manual test checklist (run on the target i3)

> Goal: generate every report PDF from the hub, verify that the report
> card includes marks + attendance + auto-grade, and that TC + character
> certificate numbers are sequential.

## Prerequisites
- Phase 6 already passed.
- At least one class with 5+ active students, one exam with marks
  recorded, and some attendance + fee data.

## 1. Open the Reports hub
1. Sign in, click **Reports** in the sidebar.
2. **Expect:** the hub opens within ~500 ms with four group boxes:
   **Students**, **Academic**, **Finance**, **Documents**.
3. Each group has 1-4 buttons. The **Finance** and **Academic ->
   Attendance** buttons just point you back to their dedicated tabs.

## 2. Students group
1. **Student profile...** -> picker dialog asking for an admission no.
   Enter a valid one -> save the PDF.
   - **Expect:** school header, photo (if set), identity table,
     family / address / other sections.
   - Try an unknown admission no. -> "No student with adm. no. ..."
2. **Class roster...** -> pick a class -> save.
   - **Expect:** header lists the class + count, table has Roll / Adm. /
     Name / Father / Phone / Status.
3. **Admission register...** -> pick a year -> save.
   - **Expect:** every student admitted in that year window, sorted by
     admission_date.
4. **Withdrawal register...** -> pick a year -> save.
   - **Expect:** transferred / passed-out / inactive students from that
     year. (If you have none, the PDF says "No withdrawals to show.")

## 3. Academic group
1. **Mark sheet...** -> pick class + exam -> save.
   - **Expect:** rows = students, columns = subjects (each header shows
     "/<max>"), trailing Total + % columns.
2. **Report card - single...** -> pick a student.
   - **Expect:** photo + identity, subjects-by-exams matrix with
     marks/grade per cell, Overall row, attendance summary line, blank
     remark space, signature lines.
3. **Report card - whole class...** -> pick a class.
   - **Expect:** one student per page, same template. Verify the page
     count matches the active-student count.
4. **Attendance reports...** -> info dialog pointing back to the
   Attendance tab (PDFs already covered there in Phase 4).

## 4. Finance group
1. **Fee ledger / defaulters...** -> info dialog pointing back to the
   Fees tab (PDFs already covered there in Phase 6).

## 5. Documents group
1. **Transfer certificate...** -> dialog asks for admission no. + leaving
   date + reason + conduct + fees-paid checkbox. Save.
   - **Expect:** TC has a numbered reference (e.g.
     `TC/2025-26/0001`), 11 numbered fields, and signature lines.
2. **Generate a second TC** -> reference becomes `TC/2025-26/0002`.
   Counter is atomic and persistent.
3. **Character certificate...** -> dialog asks for adm. no. + conduct.
   Save. Verify the reference is `CC/2025-26/0001`.
4. **ID card sheet...** -> pick a class. Save.
   - **Expect:** 8 cards per A4 page, each with photo placeholder,
     school name, name, adm. no., class, blood group, phone.

## 6. UI responsiveness
- During each PDF generation a "Generating PDF..." dialog appears
  briefly, then "Saved to: ..." confirmation. The main window must
  remain responsive.

## 7. Automated suite
```bash
QT_QPA_PLATFORM=offscreen pytest
```
**Expect:** all 212 tests pass.

## 8. Lint / format
```bash
ruff check .
ruff format --check .
```
Both clean.
