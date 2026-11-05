# Stage 2: Product Feature Spec — Statutory Reconciliation Justification & Classification Review Gate
**Feature ID**: FEAT-OPS-07  
**Module**: Banking Reconciliation, General Ledger, Statutory Auditing, MCA & Income Tax Compliance  
**Status**: Ready for Execution  
**RICE Score**: Reach: 100% | Impact: Massive (5) | Confidence: 98% | Effort: 2 Sprints = High Priority  

---

## 1. Feature Overview
Solves the compliance gap where direct bank debits (e.g. debit card annual maintenance fees, POS merchant charges, foreign exchange markup, payment gateway deductions) and unbilled operational outlays (e.g. counterparty UPI/IMPS transfers without immediate supplier tax invoices) are either silently dumped into Schedule III Suspense (Account Code `2099`) or left in an ambiguous state without legal vouching.

Under **Companies Act 2013 Section 128 (Books of account to be kept by company)**, **Income-tax Act 1961 Section 37 (General business deductions)**, **Section 40A(3) (Cash expenditure threshold)**, and **CARO 2020 Clause 3(i)**, every rupee moving through the corporate bank account must have:
1. An identifiable business purpose (`wholly and exclusively for the purposes of the business`).
2. An appropriate general ledger classification mapping to Schedule III Note 18 (Finance Costs) or Note 19 (Other Expenses).
3. A contemporaneous statutory narration citing UTR, payee, and business purpose when vendor tax invoices are not immediately available.
4. Segregation of director personal transactions under Section 185 and Section 2(22)(e).

When the user triggers **"Reconcile All Statements"** (or upon statement review), the system intercepts unbilled/unmatched withdrawals and provides a modal **Statutory Justification & Classification Gate** with 1-click presets, editable narrations, and batch ledger posting.

---

## 2. User Stories & Acceptance Criteria

### User Story 1 (Global Sweep Intercept & Prompt)
- *As a Founder, CFO, or Accountant*, when I click "Reconcile All Statements" from the Bank Reconciliation workspace:
  - If any bank withdrawals or unmatched debits remain unclassified after Tier 1 (Exact match) and Tier 2 (Probable match):
  - The system must immediately present the **Statutory Justification & Classification Gate Modal**.
  - The modal lists each unbilled/unmatched line with its Date, Payee/Description, UTR, Withdrawal Amount, and current status.
  - A prominent badge/banner on the dashboard also indicates: `"{N} Unbilled Debits Require Statutory Justification [Review & Justify]"` so the user can re-open the gate at any time.

### User Story 2 (1-Click Statutory Classification Presets)
- In the review modal, each transaction provides 1-click classification presets that immediately configure the target account code and compliant statutory narration:
  1. **Bank Fee / Card Charge (`4030`)**:
     - *Target Code*: `4030` (Finance Costs & Bank Charges)
     - *Default Narration*: `"Annual debit card fee / bank maintenance charge debited by bank per bank statement advice. Statutory Finance Cost (Sch III Note 18)."`
  2. **Self-Vouched Expense (`4090`)**:
     - *Target Code*: `4090` (Miscellaneous Business Expenses)
     - *Default Narration*: `"Self-vouched business operational expense paid to {Counterparty} via {Channel} (UTR: {UTR}). Tax invoice unavailable; wholly and exclusively for business (IT Act Sec 37)."`
  3. **Vendor Advance (`1030`)**:
     - *Target Code*: `1030` (Prepaid Expenses & Vendor Advances)
     - *Default Narration*: `"Advance payment disbursed to {Counterparty} (UTR: {UTR}). Commercial tax invoice pending receipt. Sch III Current Assets."`
  4. **Director Due / Personal Swipe (`1040`)**:
     - *Target Code*: `1040` (Loans & Advances to Directors / Director Current Account)
     - *Default Narration*: `"Personal transaction debited from corporate current account. Charged to Director Current Account pending immediate reimbursement (CA2013 Sec 185)."`
  5. **Keep in Suspense (`2099`)**:
     - *Target Code*: `2099` (Schedule III Suspense Account)
     - *Default Narration*: `"Unidentified bank debit retained in Suspense Account (Code 2099) under investigation. Requires resolution prior to FY closure."`

### User Story 3 (Batch Balanced Double-Entry Journal Posting)
- When the user clicks **"Post All Statutory Allocations"**:
  - The frontend sends a single batch payload to `POST /api/v1/reconciliation/batch-allocate`.
  - For each line:
    - The backend clears Suspense (Code `2099`) if a suspense journal entry was previously posted, OR directly reconciles against Bank (Code `1010`).
    - Creates a posted Journal Entry with reference type `"suspense_allocation"`.
    - Every transaction strictly satisfies $\sum \text{Debits} - \sum \text{Credits} \equiv 0.00$.
    - Sets `reconciliation_status = "reconciled"` and records the statutory narration in `line.notes`.
  - The dashboard updates in real time, clearing the resolved items and updating the reconciled count.

---

## 3. Scope Boundaries
- **In-Scope**:
  - `apps/api/app/api/v1/reconciliation.py`:
    - Update `POST /api/v1/reconciliation/reconcile-all` to return `suspense_lines` and `requires_statutory_justification`.
    - Create `GET /api/v1/reconciliation/pending-justifications` returning unbilled debits awaiting justification.
    - Create `POST /api/v1/reconciliation/batch-allocate` accepting list of allocations, executing balanced double-entry journals.
  - `apps/web/src/app/reconciliation/page.tsx`:
    - Intercept `handleRunGlobalSweep` to open modal when `suspense_lines` are returned.
    - Persistent banner for pending justifications with quick-open button.
    - Interactive `StatutoryJustificationModal` with 1-click classification presets, account selector, editable narrations, and batch commit.
  - Automated zero-mock tests in `apps/api/tests/test_reconciliation.py`.
- **Out-of-Scope**:
  - Modifying bank statement parser schemas or third-party OCR services.

