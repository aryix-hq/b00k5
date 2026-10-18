# b00k5 Change Log & Architecture Decision Register

This log provides an auditable, chronological record of all architectural modifications, statutory enhancements, defect remediations, and pull requests in `b00k5`.

---

## 📅 Chronological Change Register

### [2026-10-18] — Milestone: `FEAT-PAY-01` Sovereign Payroll Core Implementation
- **Branch / PR:** `feat/sovereign-payroll-core-and-ledger`
- **Category:** `feat` / `payroll` / `ledger` / `statutory`
- **Author:** Sovereign Architecture & Core Engineering Working Group
- **Key Deliverables:**
  1. **PostgreSQL 16 Schema:** Added Section 14 to `init_schema.sql` defining `employees`, `salary_structures`, `payroll_runs`, `payslips`, and `employee_tax_declarations` with Row-Level Security (RLS) isolation and Payroll Chart of Accounts (`2070-2077`, `4020-4023`).
  2. **Statutory Calculation Engine (`PayrollService`):** Implemented Section 192 TDS (Finance Act 2024 New 115BAC vs Old regime), EPF Act 1952 (12% employee/employer, EPS capped at ₹1,250), ESI Act 1948 (0.75% / 3.25% on gross $\le$ ₹21,000), Professional Tax (Karnataka, Maharashtra, Delhi), and Loss of Pay (LOP) calendar-day proration using Banker's Rounding (`Decimal(15, 2)`).
  3. **Atomic 3-Leg Double-Entry General Ledger Postings:**
     - **Leg 1 (Month-End Accrual):** Dr. Salaries (4020), Dr. Employer PF (4021), Dr. Employer ESI (4022) vs Cr. Net Salary Payable (2070), Cr. Employee PF (2071), Cr. Employer PF (2072), Cr. Employee ESI (2073), Cr. Employer ESI (2074), Cr. PT (2075), Cr. TDS 192 (2076) with SHA-256 seal.
     - **Leg 2 (Salary Disbursement):** Dr. Net Salary Payable (2070) vs Cr. Bank Account (1010).
  4. **Schedule III Integration:** Mapped payroll liability accounts `2070-2077` into Note 7 (Other Current Liabilities) and expense accounts `4020-4023` into Note 17 (Employee Benefits Expense).
  5. **FastAPI Endpoints:** Created `/api/v1/payroll` endpoints for employees, salary structures, payroll runs, calculate, lock/post-accrual, post-disbursement, payslips, and tax declarations.
  6. **Comprehensive Automated Tests:** Implemented unit and live Postgres E2E tests in `apps/api/tests/test_payroll_ledger_inviolability.py` (6/6 passing).

---

### [2026-10-18] — Release `v1.1.0-alpha`: Enterprise Accounting Benchmark & Sovereign Payroll Roadmap
- **PR / Milestone:** `feat/enterprise-benchmark-and-feature-registry`
- **Category:** `feat` / `architecture` / `statutory`
- **Author:** Product Management & System Architecture Working Group
- **Key Deliverables:**
  1. **Master Competitive Benchmarking:** Published deep-dive comparative matrix and reverse-engineering report across `b00k5`, Zoho Books, Odoo 17/18 Accounting, Zoho Payroll, RazorpayX, and Tally Prime.
  2. **Embedded Sovereign Payroll Architecture:** Designed atomic 3-leg general ledger posting (Accrual $\rightarrow$ Disbursement $\rightarrow$ Remittance) with direct Schedule III Note 17 (*Employee Benefits Expense*) integration.
  3. **Statutory Withholding Engines:** Reverse-engineered and specified Section 192 TDS (Dual-Regime with Budget 2024 ₹75,000 standard deduction), EPF Act 1952 (ECR export), ESIC Act 1948, and state-wise Professional Tax (PT).
  4. **Supply Chain & Perpetual Inventory (Ind AS 2):** Specified Purchase Order $\rightarrow$ Goods Inward $\leftrightarrow$ Vendor Bill 3-Way Matching, Landed Cost allocation, and real-time COGS FIFO ledger vouchers.
  5. **Universal Audit Trail (Rule 3(1)):** Architected MCA Companies (Accounts) Rules 2014 Rule 3(1) tamper-proof append-only audit trail table with database triggers.
  6. **Feature Registry Expansion:** Added official feature IDs `FEAT-PAY-01` to `05`, `FEAT-INV-05` to `07`, `FEAT-SC-01` to `02`, `FEAT-BANK-04` to `05`, and `FEAT-AUDIT-01` to `wiki/FEATURE_REGISTRY.md`.

---

### [2026-10-16] — Release `v1.0.4-ga`: Repository Public Readiness, PR Template & ARYIX Ecosystem
- **PR / Milestone:** `v1.0.4-ga`
- **Category:** `feat` / `chore` / `governance`
- **Author:** Sovereign Architecture & Product Engineering Working Group
- **Key Deliverables:**
  1. **Strict PR Protocol Established:** Direct pushes and merges to `main` prohibited. Enforced feature branching, [`.github/pull_request_template.md`](../.github/pull_request_template.md), and wiki traceability.
  2. **Branch Deploy Automation:** Implemented [`scripts/branch_deploy.sh`](../scripts/branch_deploy.sh) for safely deploying, testing, and verifying any branch against clean or isolated Docker stacks.
  3. **Engineering Wiki:** Established `wiki/` directory with `README.md`, `DEFECT_TRACKER.md` (DEF-01 to DEF-21), `FEATURE_REGISTRY.md`, and `DEVELOPMENT_WORKFLOW.md`.
  4. **Open-Source Secret & PII Sanitization:** Sanitized legacy CA firm names, membership numbers, and non-synthetic MCA SRNs into generic synthetic placeholders.
  5. **ARYIX Branding & Founder Manifesto:** Implemented interactive `AboutModal.tsx` featuring the Sovereign Accounting Manifesto by Adithya Khamithkar and the Community vs Enterprise support matrix.
  6. **Statutory Document Neutrality:** Certified that customer invoices, receipts, and MCA board minutes have zero third-party vendor watermarks.
  7. **Clean Database Reset:** Destroyed legacy dirty state (`docker compose down -v`) and initialized pristine environment from `init_schema.sql`.

---

### [2026-10-15] — Release `v1.0.3`: Statutory Backup Policy & Disaster Recovery
- **PR / Milestone:** `v1.0.3`
- **Category:** `feat` / `sre`
- **Key Deliverables:**
  1. Authoring and formalization of [`docs/BACKUP_AND_DISASTER_RECOVERY_POLICY.md`](../docs/BACKUP_AND_DISASTER_RECOVERY_POLICY.md) (10-year retention under CA 2013 §128(5), IT Act §44AA/§149, CGST Act §36).
  2. Automated disaster recovery verification script (`scripts/dr_drill.py`) verifying RTO < 30s and zero ledger drift.
  3. Head-to-head competitive benchmark documentation [`docs/COMPETITIVE_BENCHMARK.md`](../docs/COMPETITIVE_BENCHMARK.md) against Tally, Zoho, QuickBooks, and ClearTax.

---

### [2026-10-14] — Release `v1.0.2`: Tab & FY Desynchronization Audit Remediations
- **PR / Milestone:** `v1.0.2`
- **Category:** `fix` / `ui`
- **Key Deliverables:**
  1. Fixed governance and yearbook tab desynchronization upon financial year switching.
  2. Vault segregation into Permanent Legal Anchors and Annual Statutory Documents.
  3. Deduplication of INC-20A Commencement of Business records.
  4. Expanded multi-line service item description box on invoices.
  5. Multi-tenant IAM profile penetration testing with Selenium (`test_selenium_iam_multitenant_profiles.py`).

---

### [2026-10-12] — Release `v1.0.1`: Core MCA Secretarial Governance & Hardened Ledger
- **PR / Milestone:** `v1.0.1`
- **Category:** `feat` / `statutory`
- **Key Deliverables:**
  1. 120-Day Board Meeting Interval Watchdog under Companies Act Section 173(1) and ICSI SS-1.
  2. Form DPT-3 loan declaration generator for director reimbursements.
  3. Hardware PKCS#11 DSC signing bridge integration on port 28045.
  4. Schedule III Division I statutory financial statements export with Banker's Rounding.
