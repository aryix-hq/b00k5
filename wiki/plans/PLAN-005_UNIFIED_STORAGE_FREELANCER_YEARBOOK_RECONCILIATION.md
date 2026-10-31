# PLAN-005: Unified Cloud & Database Management, Frictionless Freelancer Payments, Year Book Outflow Visibility, and Bank Statement Reconciliation

> **Lifecycle Stage**: Stage 3 (Phased Project Planning)  
> **Status**: APPROVED  
> **Target Branch**: `feat/FEAT-OPS-05-unified-storage-freelancer-recon`  
> **Created**: 2026-10-31  
> **Upstream Feature Spec**: [`wiki/features/FEAT-OPS-05_UNIFIED_STORAGE_FREELANCER_YEARBOOK_RECONCILIATION.md`](../features/FEAT-OPS-05_UNIFIED_STORAGE_FREELANCER_YEARBOOK_RECONCILIATION.md) (RICE Score: **1,068.75**)  
> **Source Research Note**: [`wiki/research/RES-005_UNIFIED_STORAGE_FREELANCER_RECONCILIATION.md`](../research/RES-005_UNIFIED_STORAGE_FREELANCER_RECONCILIATION.md)  
> **Planning Trio Sign-off**:
> - [x] Product Manager (`@product-manager`)
> - [x] System Architect (`@architect`)
> - [x] Technical Project Manager (`@project-manager`)

---

## 1. Executive Summary & Objective

This plan delivers four cohesive operational improvements to eliminate system clutter, streamline cash outflows, and achieve end-to-end reconciliation:

1. **Unified Cloud Storage & Database Management Hub (`/settings/integrations`)**:
   - Consolidates Google Drive sync, Cloudflare R2 / AWS S3 sovereign cloud mirror, database backups with automated retention policies, and point-in-time restore into a clean 3-tab layout:
     - **Tab 1: Cloud Storage & Sync** (Cloudflare R2 Sovereign Mirror & Google Drive Archival).
     - **Tab 2: Database Backups & Snapshots** (Instant backup trigger, retention policy controls, encrypted snapshot inventory).
     - **Tab 3: Point-in-Time Restore & Safety Checkpoints** (Pre-restore checkpoints and restore triggers).
   - Replaces redundant sidebar links with a single unified entry: **"Cloud Storage & Backups"**.
   - Preserves backward compatibility by redirecting `/gdrive` to `/settings/integrations?tab=cloud`.

2. **⚡ Simplified Freelancer Quick-Pay Flow**:
   - Introduces `POST /api/v1/payroll/contractor-payments/quick-pay` to record and disburse freelancer payouts in 1 action:
     - Automatic on-demand contractor profile creation with standard defaults (`CON-XXX`, `individual_huf`).
     - Automatic TDS calculation (194J 2% Tech, 194J 10% Prof, 194C 1%/2%, or 0% No TDS).
     - Automated dual journal entry execution: Accrual (DR Expense, CR TDS, CR Payable) and Disbursement (DR Payable, CR Bank 1010).
   - Frontend **"⚡ Quick Pay Freelancer"** modal accessible from Payroll, Expenses, and Year Book.

3. **Year Book Salaries & Freelancers Tab**:
   - Adds a **"Salaries & Freelancers"** tab to `/yearbook` for the selected Financial Year.
   - Summarizes total employee compensation, freelancer payouts, statutory TDS withheld, and net disbursed.
   - Provides searchable registers for Contractor Payments and Employee Payroll Runs with 1-click Form 16A and Bank CMS downloads.
   - Updates Year Book financial summary metrics so Net Operating Cash Outflow accurately includes payroll and contractor expenses.

4. **Bi-directional Bank Statement Reconciliation**:
   - Enhances `ReconciliationEngine` in `apps/api/app/services/reconciliation_engine.py` to evaluate withdrawal candidates against open/pending `ContractorPayment` and `PayrollRun` records by net amount, UTR, or counterparty name.
   - Enhances `POST /api/v1/reconciliation/lines/{line_id}/confirm-match` to accept `matched_contractor_payment_id` and `matched_payroll_run_id`, automatically executing disbursement (if pending), linking the bank line, and marking it `reconciled`.
   - Enhances `/reconciliation` Action Center to render candidate cards for withdrawals and provide 1-Click "Reconcile Freelancer Payment" and "Reconcile Payroll Run" actions with a manual search fallback.

---

## 2. Living Phase & Milestone Tracker

| Phase | Milestone Description | Lead Agent(s) | Target Date | Status | Deliverables / Evidence |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **Phase 1** | Unified Cloud & Database Management Page & Sidebar Consolidation | `@ui-ux`, `@fullstack-developer` | 2026-10-31 | `[PENDING]` | `/settings/integrations` 3-tab layout, `/gdrive` redirect, `Sidebar.tsx` update |
| **Phase 2** | Backend Quick-Pay API & Frictionless Freelancer Modal | `@fullstack-developer`, `@ca` | 2026-10-31 | `[PENDING]` | `/quick-pay` endpoint, zero-mock tests, QuickPay modal |
| **Phase 3** | Year Book Salaries & Freelancers Tab + Schedule III Statutory Calibration | `@ui-ux`, `@fullstack-developer`, `@ca` | 2026-10-31 | `[PENDING]` | `/yearbook` tab, FY compensation API, `schedule_iii_service.py` Note 17/19 remapping, Form 16A links |
| **Phase 4** | Bank Statement Reconciliation for Withdrawals (Freelancers & Payroll) | `@architect`, `@fullstack-developer` | 2026-10-31 | `[PENDING]` | `reconciliation_engine.py`, confirm-match expansion, Action Center UI |
| **Phase 5** | Zero-Mock Regression Suite & Ephemeral Staging Verification | `@qa`, `@engineering-manager` | 2026-10-31 | `[PENDING]` | Pytest suite, `bin/staging-deploy.sh test-and-destroy` |

---

## 3. Detailed Technical Architecture

### 3.1 Unified Storage & Backup Hub
- **Path**: `apps/web/src/app/settings/integrations/page.tsx`
- **Tabs**:
  1. `cloud`:
     - Sub-tab or card 1: Cloudflare R2 / AWS S3 Sovereign Mirror (usage meter, test connection, save credentials, sync all).
     - Sub-tab or card 2: Google Drive Archival (Service Account JSON, shared folder ID, copy client email pill, sync sweep trigger).
  2. `backups`:
     - Instant Backup trigger button.
     - Retention policy controls (auto-prune toggle, keep count, manual prune button).
     - Snapshot logs table with timestamp, size, checksum, cloud status, and download links.
  3. `restore`:
     - Pre-restore safety checkpoint trigger.
     - Available snapshots list with 1-click restore modal and confirmation safety prompt.

### 3.2 Quick Freelancer Payout Engine
- **Endpoint**: `POST /api/v1/payroll/contractor-payments/quick-pay`
- **Payload Schema**:
  ```python
  class QuickContractorPaymentRequest(BaseModel):
      freelancer_name: str
      contractor_id: Optional[uuid.UUID] = None
      pan_number: Optional[str] = None
      email: Optional[str] = None
      amount: Decimal
      amount_type: str = "gross"  # gross or net
      service_type: str = "194J_TECH"  # 194J_TECH, 194J_PROF, 194C, NO_TDS
      tds_rate: Optional[Decimal] = None
      description: str
      payment_date: Optional[date] = None
      invoice_number: Optional[str] = None
      bank_reference_or_utr: Optional[str] = None
      disburse_immediately: bool = True
  ```
- **Execution Flow**:
  1. If `contractor_id` is missing: Find existing contractor by name or PAN. If not found, auto-create contractor with next code `CON-XXX`.
  2. Compute TDS based on `service_type` and `amount_type`.
  3. Insert `ContractorPayment`.
  4. Call `PayrollService.accrue_contractor_payment` -> posts accrual journal entry.
  5. If `disburse_immediately`: Call `PayrollService.disburse_contractor_payment` with UTR -> posts disbursement journal entry to Bank (1010).

### 3.3 Year Book Compensation Integration & Schedule III Calibration
- **Endpoint**: `GET /api/v1/payroll/yearbook-summary?fy={FY}`
- **Returns**: Total employee gross, net, TDS; Total contractor gross, net, TDS; Itemized lists for both.
- **Frontend Tab**: Adds `payroll_contractors` tab to `/yearbook/page.tsx` with summary cards, freelancer register, and employee payroll run register.
- **Schedule III Calibration (`apps/api/app/services/schedule_iii_service.py`)**:
  - Remaps Account `4040` (Legal, Technical, & Freelancer Fees) and `4010` (Contractor Charges) out of `depreciation_exp` into **Note 19: Other Expenses (Professional, Legal & Technical Service Fees)**.
  - Maintains `4020`, `4021`, `4022` under **Note 17: Employee Benefits Expenses**.
  - Restricts `depreciation_exp` to Account `5020` / Schedule II fixed asset depreciation.
  - Guarantees zero ledger drift and authentic MCA AOC-4 statutory mapping.

### 3.4 Bank Statement Withdrawal Reconciliation
- **Engine Logic**:
  - In `ReconciliationEngine.reconcile_statement`:
    - Collect active `ContractorPayment`s (disbursed or approved) and `PayrollRun`s (disbursed or locked).
    - If `line.withdrawal_amount > 0`:
      - Match against `ContractorPayment`: exact net_payable == withdrawal_amount AND (contractor name in description OR UTR in reference_number).
      - Match against `PayrollRun`: exact total_net_pay == withdrawal_amount AND ("SALARY" in description OR run number in description).
      - If matched, set `confidence_score = 100.00` (or heuristic score) and note the candidate.
  - In `confirm_line_match`:
    - Handle `matched_contractor_payment_id`:
      - If payment is not yet disbursed, call `PayrollService.disburse_contractor_payment(db, tenant.id, payment_id, current_user.id, utr=line.reference_number)`.
      - Link `line.matched_journal_entry_id = payment.disbursement_journal_id`.
      - Set `line.reconciliation_status = "reconciled"`.
    - Handle `matched_payroll_run_id`:
      - If run is not yet disbursed, call `PayrollService.disburse_payroll_run(db, tenant.id, run_id, current_user.id, payout_utr=line.reference_number)`.
      - Link `line.matched_journal_entry_id = run.disbursement_journal_id`.
      - Set `line.reconciliation_status = "reconciled"`.

