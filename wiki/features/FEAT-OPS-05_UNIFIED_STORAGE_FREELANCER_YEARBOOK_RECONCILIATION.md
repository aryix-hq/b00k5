# FEAT-OPS-05: Unified Cloud & Database Management, Frictionless Freelancer Payments, Year Book Outflow Visibility, and Bank Statement Reconciliation

> **Lifecycle Stage**: Stage 2 (Product Requirements & RICE Prioritization)  
> **Status**: Approved  
> **Author**: Product Manager (`@product-manager`)  
> **Target Branch**: `feat/FEAT-OPS-05-unified-storage-freelancer-recon`  
> **Source Research Note**: [`wiki/research/RES-005_UNIFIED_STORAGE_FREELANCER_RECONCILIATION.md`](../research/RES-005_UNIFIED_STORAGE_FREELANCER_RECONCILIATION.md)  
> **Phased Implementation Plan**: [`wiki/plans/PLAN-005_UNIFIED_STORAGE_FREELANCER_YEARBOOK_RECONCILIATION.md`](../plans/PLAN-005_UNIFIED_STORAGE_FREELANCER_YEARBOOK_RECONCILIATION.md)  

---

## 1. Executive Summary & Problem Statement

### 1.1 User Problem
1. **Cluttered Cloud Storage & Database Architecture**:
   - Google Drive sync, Cloudflare R2 / S3 sovereign mirror, database backup triggers, retention policy meters, and database restore checkpoints are scattered across disjointed routes (`/gdrive` vs. `/settings/integrations`) and displayed as a single, overwhelming 1,100-line vertical stack.
2. **High Friction in Freelancer Payouts**:
   - Small businesses and startup founders paying a freelance developer or designer must complete a 4-step bureaucratic journey (onboard contractor with 12 fields -> record payout claim -> accrue bill to GL -> disburse with bank details).
3. **Missing Remuneration in Year Book**:
   - `/yearbook` renders vendor bills and sales invoices, but omits employee salaries and contractor payouts, preventing founders and auditors from viewing complete annual operating outflows and statutory TDS in the Year Book.
4. **Unilateral Bank Reconciliation**:
   - Bank statement reconciliation in `/reconciliation` only suggests intelligent candidates for deposits against customer invoices. Withdrawals for freelancer payments and salaries fail to surface candidate matches, forcing manual suspense workarounds.

### 1.2 Proposed Solution
- **Consolidated Tabbed Cloud & Database Hub**: Unify Google Drive sync, Cloudflare R2/S3 sovereign mirror, backup automation with retention policies, and point-in-time restore under `/settings/integrations` with clean tabs and a single sidebar entry.
- **⚡ Quick Pay Freelancer Flow**: 1-Click modal allowing instant recording and disbursement of freelancer payments with automated contractor creation, TDS calculation (194J/194C/0%), and double-entry GL posting.
- **Year Book Salaries & Freelancers Tab**: Comprehensive view of annual employee payroll runs and contractor claims with statutory TDS summaries and net cash outflows.
- **Bi-directional Bank Statement Reconciliation**: Extend `ReconciliationEngine` and reconciliation UI to match bank statement withdrawals against open freelancer payouts, payroll runs, and expenses with 1-click reconciliation.

---

## 2. RICE Prioritization & Scoring

$$\text{RICE Score} = \frac{\text{Reach} \times \text{Impact} \times \text{Confidence}}{\text{Effort}}$$

| Factor | Value | Rationale |
| :--- | :---: | :--- |
| **Reach (R)** | **450** | Affects daily financial operations: every backup/restore event, every freelancer payout, every monthly bank statement reconciliation, and every annual audit review. |
| **Impact (I)** | **3.0 (Massive)** | Reduces freelancer payment time from 5 minutes to 15 seconds; unlocks full-spectrum bank reconciliation for withdrawals; resolves UI clutter. |
| **Confidence (C)** | **95%** | Backend double-entry ledger models, payroll models, and reconciliation engines already exist and need cohesion and candidate expansion. |
| **Effort (E)** | **1.2 Person-Weeks** | Phased across 4 clear milestones (Storage Tab Consolidation, Quick Pay Freelancer, Year Book Compensation Tab, Bank Reconciliation for Withdrawals). |
| **TOTAL SCORE** | **1,068.75** | **Top Priority Operational Efficiency Initiative.** |

---

## 3. User Acceptance Criteria (UAC)

- [ ] **UAC-01 (Unified Storage & Backup Tabs)**: `/settings/integrations` features clean, distinct tabs:
  - Tab 1: **Cloud Storage & Sync** (Cloudflare R2 Sovereign Mirror + Google Drive Archival).
  - Tab 2: **Database Backups & Snapshots** (Instant backup trigger, retention policy controls, encrypted snapshot inventory).
  - Tab 3: **Restore & Safety Checkpoints** (Pre-restore rollback checkpoints and restore confirmation).
  - Navigating to `/gdrive` seamlessly redirects or renders the unified page under Tab 1.
  - Sidebar under "Cloud & Database" shows a single unified entry: **"Cloud Storage & Backups"**.
- [ ] **UAC-02 (Simplified Quick Freelancer Payment)**:
  - Users can click **"⚡ Quick Pay Freelancer"** from Payroll, Expenses, or Year Book.
  - Entering a freelancer name, amount, service type (194J 2% Tech, 194J 10% Prof, 194C 1%/2%, or 0% No TDS), and clicking submit executes:
    - Auto-onboarding of contractor if new.
    - Automated TDS deduction and net payable calculation.
    - Accrual journal posting (DR 4040/4020, CR 2060, CR 2040).
    - Immediate disbursement journal posting (DR 2040, CR 1010 Bank) if "Disburse from Bank immediately" is checked.
- [ ] **UAC-03 (Year Book Salaries & Freelancers Tab)**:
  - `/yearbook` includes a **"Salaries & Freelancers"** tab for the selected Financial Year.
  - Renders total employee compensation, total freelancer payouts, and total statutory TDS withheld.
  - Displays searchable registers for Contractor Payments and Employee Payroll Runs with download links for Form 16A and Bank CMS files.
  - Total operating outflow in Year Book top metrics reflects salaries and contractor payments.
- [ ] **UAC-04 (Bank Reconciliation for Freelancers & Salaries)**:
  - In `apps/api/app/services/reconciliation_engine.py`, bank statement withdrawals evaluate candidate matches against open `ContractorPayment` and `PayrollRun` records by net amount, UTR, or counterparty name.
  - In `/reconciliation`, when a withdrawal line is selected, the Action Center displays candidate matches for Contractor Payments and Payroll Runs.
  - Clicking **"Reconcile Freelancer Payment"** or **"Reconcile Payroll Run"** executes settlement, links the bank statement line, and marks it `reconciled` with 100% audit confidence.

