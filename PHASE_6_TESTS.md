# Phase 6 - Manual test checklist (run on the target i3)

> Goal: configure fees per class, collect a payment with an atomic
> receipt number, print A4 + thermal receipts, view a ledger, and
> generate a defaulters list.

## Prerequisites
- Phase 5 already passed.
- Migration 003 has run automatically. Verify by opening the
  **Fees** sidebar entry -- the **Structure** tab should load without
  error.

## 1. Fee structure
1. Open **Fees** -> **Structure**. Pick a class with students.
2. Click **Add row** twice. Enter:
   - `Tuition`, Rs. 1500, frequency **monthly**.
   - `Transport`, Rs. 800, frequency **monthly**.
3. Try saving with the head blank -> "Head cannot be blank."
4. Try frequency **monthly** with due-month 13 -> rejected (clamped by
   spinbox; the service also validates 1-12).
5. Save successfully -> "Fee structure saved." Re-open the tab to
   confirm rows persist.
6. Edit Tuition to Rs. 2000, remove Transport, add `Activity` Rs. 5000
   **quarterly**, save again. Verify replace-all behaviour.

## 2. Pending calculation
- Switch to **Collection**. Type the admission no. of a student in the
  class you configured. Press Enter or **Look up**.
- **Expect:** the pending grid shows one row per fee head with:
  - "Due" = instances elapsed x amount (e.g. on 15 May with monthly
    fees: 2 instances of Tuition).
  - "Paid" = 0 (no payments yet).
  - "Outstanding" = same as Due.
- The **Pay?** column is auto-checked for outstanding > 0; the rightmost
  spinbox is pre-filled with the outstanding amount in rupees.

## 3. Collect a payment
1. Untick the Activity row (if quarterly hasn't started yet, leave it
   ticked or untick to skip).
2. Reduce Tuition's amount to a partial payment (e.g. one month's worth).
3. Pick mode = **UPI**, enter a reference like `UTR1234567`.
4. Click **Save && receipt no.**.
5. **Expect:** dialog says `Receipt no. RCP/<year>/00001`. The pending
   grid reloads -- the Tuition row's Paid column reflects the partial
   payment.
6. Save again with a different student -> receipt is `00002`.
   Sequential, atomic, never duplicates.

## 4. Print receipts
1. After saving, click **Print A4 receipt...** -> save the PDF.
   - Open the file. Verify: school header (name + address), receipt
     number, date, mode, student details, item table, total in words
     ("Rupees ... Only"), signature lines.
2. Click **Print 80mm receipt...** -> save the PDF.
   - The page is 80mm wide and resembles a thermal-printer slip with
     centered header, single-column item table, and a "Thank you!"
     footer.

## 5. Ledger
1. Switch to **Ledger**. Look up the same student.
2. **Expect:** the **Payments** table lists every payment item
   chronologically (date, receipt, mode, head, amount). The
   **Outstanding by head** table shows the post-payment balances per
   head. Summary line: "Total paid: Rs. ... | Total outstanding: Rs. ..."
3. Click **Export PDF...**. Open the file: full ledger + outstanding
   summary, school header, student details.

## 6. Defaulters
1. Switch to **Defaulters**. Pick the class.
2. **Expect:** any active student with outstanding > 0 appears with
   their admission no. and outstanding amount. Footer shows the count
   and total.
3. Click **Export PDF...** -> verify the PDF matches the table.

## 7. Cross-module wiring
- Add a student in **Students** -> they show up in the **Defaulters**
  tab (after the auto-refresh on tab switch).
- Edit the fee structure -> next time you load the collection or
  ledger view, the "Due" amounts update.

## 8. Receipt number resilience
- Stop and re-open the app. Save a new payment.
- **Expect:** the receipt number continues from the next sequence
  (e.g. `00003`). Counters survive restart.

## 9. Automated suite
```bash
QT_QPA_PLATFORM=offscreen pytest
```
**Expect:** all 197 tests pass.

## 10. Lint / format
```bash
ruff check .
ruff format --check .
```
Both clean.
