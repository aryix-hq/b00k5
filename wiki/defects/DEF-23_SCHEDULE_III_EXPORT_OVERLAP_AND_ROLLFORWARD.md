# DEF-23: Schedule III PDF Export Header Text Overlap & Permanent Account Roll-Forward Imbalance

**Defect ID:** `DEF-23`  
**Module:** `schedule_iii` / `export` / `yearbook`  
**Severity:** 🔴 Critical  
**Status:** **FIXED**  
**Resolution Verification:** `verify_balance_sheet_and_pdf.py`, `test_critical_fixes.py`

---

## 1. Problem Description
1. **PDF Export Table Header Overlap**:
   - In `apps/api/app/services/schedule_iii_service.py` (`_render_schedule_iii_pdf`), the table header on Page 1 (Balance Sheet) and Page 2 (Statement of Profit and Loss) used a 16 pt single-line box.
   - Column 3 used `drawRightString(mr - 105, cy - 12, pnl_col_header)` where `pnl_col_header` was `"For period ended 18-Oct-2026"`.
   - The 28-character string (width ~140 pt) right-aligned at `446.27` extended leftwards past `334.0` (`ml + 290`), overlapping directly on top of `"Note No."`, and Column 4 overlapped with Column 3:
     `Fo Note No ended 18-Oct-2026  year ended 31-Mar-2026`.
2. **FY 2026-27 Balance Sheet Roll-Forward Imbalance**:
   - When viewing FY 2026-27, the live ledger had zero manual opening entries for Share Capital.
   - The statutory fallback injected `share_capital = 100,000.00` from Form MGT-7A into Equity, but did **not** roll forward the prior year permanent balance sheet heads from filed Form AOC-4:
     - Opening Retained Deficit: `-₹1,63,851.00`
     - Opening Director Loan (Long-term Borrowings): `₹63,851.00`
   - Because $1,00,000 - 1,63,851 + 63,851 \equiv 0.00$, omitting the deficit and director loan created an artificial ₹1,00,000 imbalance ($\text{Equity \& Liab} = 1,05,000 \neq \text{Assets} = 5,000$).

---

## 2. Root Cause & Invariant Analysis
- **Statutory Invariant (Companies Act 2013 §128 & Schedule III Division I)**:
  - Balance sheet accounts are real and personal accounts and are permanent.
  - The audited and government-filed closing balances of FY 2025-26 from Form AOC-4 form the authentic opening balances of FY 2026-27.
  - Retained earnings at any reporting date $T$:
    $$\text{Reserves \& Surplus}_T = \text{Opening Reserves from Prior AOC-4} + \text{Net Profit/(Loss)}_{0 \to T}$$

---

## 3. Remediations Implemented
1. **PDF Table Header 2-Line Architecture**:
   - Upgraded table header bounding box to 24 pt height (`header_h = 24`).
   - Structured columns with explicit coordinates:
     - `Particulars`: `ml + 6`
     - `Note No.`: `col_note_x = ml + 265`
     - Column 3 (Current Period): Right-aligned at `col_cur_x = mr - 105`:
       - Line 1: `Figures as at` (on BS) / `For period ended` (on P&L)
       - Line 2: `${as_of_date.strftime('%d-%b-%Y')}`
     - Column 4 (Previous Period): Right-aligned at `col_prev_x = mr - 6`:
       - Line 1: `Figures as at` (on BS) / `For year ended` (on P&L)
       - Line 2: `31-Mar-${prior_end_yr}`
   - Applied identical clean 2-line header box to Note 2 (Share Capital) and synchronized `col_note_x` in `draw_bs_row` and `draw_total_row`.
2. **Permanent Account Roll-Forward Engine**:
   - In `ScheduleIIIService._resolve_schedule_iii_components`:
     - If `not is_current_from_vault` and prior statutory filing anchors exist:
       - Roll forward `prior_share_capital` if live ledger has 0 capital entry.
       - Roll forward `prior_reserves_and_surplus` (-₹1,63,851.00) into `reserves_and_surplus`.
       - Roll forward `prior_long_term_borrowings` (₹63,851.00) into `long_term_borrowings`.
       - Roll forward opening assets, advances, or other liabilities.
3. **Note 3 (Reserves and Surplus) Accurate Disclosure**:
   - Updated `notes_to_accounts["note_3"]["surplus_opening"]` to pull authentic `prior_reserves_and_surplus`.
   - Updated PDF Note 3 table to show authentic opening surplus instead of hardcoded dash.

---

## 4. Verification & Proof of Zero Drift
- **FY 2026-27 (Current Period)**:
  - Total Assets: ₹5,000.00 (`50.00` in hundreds)
  - Total Equity & Liabilities: ₹5,000.00 (`50.00` in hundreds)
  - Mathematical Drift: **0.00**
- **FY 2025-26 (Historical Baseline)**:
  - Total Assets: ₹0.00 (`-`)
  - Total Equity & Liabilities: ₹0.00 (`-`)
  - Mathematical Drift: **0.00**
- **PDF Layout Inspection**:
  - Saved and visually validated screenshots `18_pdf_balance_sheet_page1.png` and `19_pdf_profit_loss_page2.png` confirming complete elimination of text overlapping.
