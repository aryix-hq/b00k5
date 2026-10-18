# FEAT-ROC-03: MCA Form AOC-4 & Form MGT-7A Statutory Calibration & Schedule III Comparative Presentation Engine

**Feature ID:** `FEAT-ROC-03`  
**Status:** Implemented (Verified via Automated Zero-Mock CI Test Suite)  
**Owner:** Architecture & Financial Compliance  
**Statutory Basis:**
- **Companies Act, 2013:**
  - Section 128 & 130: Maintenance and re-opening of statutory books of accounts on order.
  - Section 137: Copy of financial statement to be filed with Registrar (Form AOC-4 / AOC-4 XBRL).
  - Section 92: Annual Return for Small Companies / One Person Companies (Form MGT-7 / MGT-7A).
  - Schedule III Division I: Non-Ind AS financial reporting and mandatory comparative presentation (Current reporting period vs Previous reporting period).
  - Schedule III Clause 4: Automatic turnover-based statutory scale rounding (`hundreds`, `thousands`, `lakhs`, `crores`).
  - Schedule III 2021 Amendment Mandate: Shareholding details of promoters (Item 6(J)), shareholders holding > 5% shares, and 11 mandatory accounting ratios.

---

## 1. Scope & Objective

1. **OCR & Regex Parsing of Government-Filed Returns**:
   - Parse authentic filed Form AOC-4 (Financial Statements, SRN: `7616438575`, DIN: `11249061`, UDIN: `2611249061AAAAA1234`) and Form MGT-7A (Annual Return, SRN: `AC6319079`).
   - Extract Schedule III heads: Paid-up Share Capital (`2010`: ₹1,00,000), Retained Deficit (`2020`: -₹1,63,851), Long-term Borrowings (`2030`: ₹63,851), Other Expenses (`4040`: ₹1,63,851), Net Profit/Loss (`5020`: -₹1,63,851).
   - Extract MGT-7 corporate attributes: Authorized Capital (₹1,00,000, 10,000 shares @ ₹10), Paid-up Capital (₹1,00,000), Net Worth (-₹63,851.00), and 100% Promoter Shareholding.

2. **Statutory Baseline Calibration Engine**:
   - Anchor government filings in PostgreSQL table `statutory_filing_anchors` via `StatutoryAnchorService.sync_statutory_anchors_from_vault`.
   - Prevent duplicate anchors; enforce idempotent synchronization on document upload/update.

3. **Schedule III Division I Comparative Presentation**:
   - Present Current Reporting Period alongside Previous Reporting Period (FY 2025-26 / AY 2026-27) derived directly from filed AOC-4/MGT-7 anchors.
   - For historical periods with 0 live transactions, populate directly from filed Form AOC-4 preserving zero mathematical drift:
     $$\text{Assets} \equiv \text{Equity \& Liabilities} \equiv ₹0.00$$
     $$\text{Share Capital } (₹1,00,000) + \text{Reserves } (-₹1,63,851) + \text{Borrowings } (₹63,851) \equiv ₹0.00$$

4. **Web Frontend Presentation (`apps/web/src/components/yearbook/ScheduleIIIViewer.tsx`)**:
   - Render Statutory Provenance Verification Banner with SRN badges (`7616438575` and `AC6319079`) and Zero Mathematical Drift seal.
   - Comparative 3-column Balance Sheet and Statement of Profit and Loss tables (`Particulars`, `Current Period`, `Previous Period`).
   - Note 2 & Form MGT-7A Governance & Shareholding Pattern Disclosure Card.
   - Expandable structured Notes to Accounts (Notes 1 to 20).
   - Certified Statutory Dossier package export (ZIP containing 11-page PDF and comparative CSVs).

---

## 2. Acceptance Criteria & Verification Evidence

- [x] **Zero Drift Ledger Balance**: $\sum \text{Assets} - \sum \text{Equity \& Liabilities} \equiv 0.00$.
- [x] **MCA Form AOC-4 & MGT-7A Anchored**: Verified in PostgreSQL with SRNs `7616438575` and `AC6319079`.
- [x] **Schedule III Comparative Presentation**: Current Period (FY 2026-27) vs Previous Period (FY 2025-26) fully rendered.
- [x] **Schedule III Clause 4 Rounding**: Scale base < 10 Lakhs rounds to nearest hundreds with 2 decimal precision.
- [x] **TypeScript Clean**: `tsc --noEmit` exited with code 0 across `apps/web`.
- [x] **Automated Test Suite**: `test_aoc4_mgt7_statutory_anchor_and_schedule_iii_comparative` passed 100%.
