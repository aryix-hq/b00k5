# Changelog

All notable changes to `b00k5` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-10-18

### Added
- **FEAT-PAY-01 Sovereign Native Payroll Core & Double-Entry General Ledger Integration**:
  - Implemented database schema in `init_schema.sql` (Section 14) for `employees`, `salary_structures`, `payroll_runs`, `payslips`, and `employee_tax_declarations` with PostgreSQL 16 RLS policies and chart of accounts (`2070-2077`, `4020-4023`).
  - Added SQLAlchemy models in `apps/api/app/models/payroll.py` and Pydantic validation schemas in `apps/api/app/schemas/payroll.py`.
  - Built core statutory calculation engine `PayrollService` with Section 192 TDS (Finance Act 2024 New 115BAC vs Old regime), EPF Act 1952 (12% employee/employer, EPS capped at ₹1,250), ESI Act 1948 (0.75% / 3.25% on gross $\le$ ₹21,000), Professional Tax (Karnataka, Maharashtra, Delhi), and Loss of Pay (LOP) calendar-day proration using Banker's Rounding (`Decimal(15, 2)`).
  - Implemented atomic 3-Leg Double-Entry General Ledger journal vouchers: Leg 1 Month-End Accrual (Dr. 4020, 4021, 4022 vs Cr. 2070-2076) with SHA-256 tamper-evident seal, and Leg 2 Salary Disbursement (Dr. 2070 vs Cr. 1010 Bank).
  - Integrated Schedule III Balance Sheet (Note 7 Other Current Liabilities) and P&L (Note 17 Employee Benefits Expense).
  - Created REST API router in `apps/api/app/api/v1/payroll.py` and full regression test suite in `apps/api/tests/test_payroll_ledger_inviolability.py` and `apps/api/tests/test_payroll_api_e2e.py`.
  - Built dark-mode Sovereign Payroll & Statutory Roster web interface (`apps/web/src/app/payroll/page.tsx`) with Monthly Payroll Runs, Employee Onboarding & CTC breakdowns, Itemized Payslip receipts, and statutory compliance tabs.
  - Linked Payroll navigation item across Owner, CA Auditor, Super Admin, and Employee roles in `apps/web/src/components/Sidebar.tsx`.
- Comprehensive Competitor Benchmarking Matrix and reverse-engineered feature inventory comparing `b00k5` with Zoho Books, Odoo 17/18 Accounting, Zoho Payroll, RazorpayX, and Tally Prime (`docs/COMPETITIVE_BENCHMARK.md`).
- Formalized feature registry records in `wiki/FEATURE_REGISTRY.md` for:
  - `FEAT-PAY-01` to `FEAT-PAY-05`: Embedded Sovereign Payroll & Unified People Roster (Salaried 192 + Contractor 194C/J).
  - `FEAT-INV-05` to `FEAT-INV-07`: Items Master, Ind AS 2 Perpetual FIFO Inventory, and Section 17(5)(h) ITC Reversals.
  - `FEAT-SC-01` to `FEAT-SC-02`: Purchase Orders $\rightarrow$ Goods Receipts $\leftrightarrow$ Vendor Bills (3-Way Matching) and Landed Cost Allocation.
  - `FEAT-BANK-04` to `FEAT-BANK-05`: Dynamic Regex Banking Rules and Interactive Split-Match Workbench.
  - `FEAT-AUDIT-01`: MCA Rule 3(1) Companies (Accounts) Rules universal tamper-proof audit trail table with database triggers.
  - `FEAT-GST-01` to `FEAT-GST-02`: GSTR-1 Portal JSON Export and Rule 37 180-day ITC Reversal Watchdog.

### Changed
- Removed 'Sovereign' badge pill from `Sidebar.tsx` navigation across Owner, CA Auditor, Super Admin, and Employee modes.
- Neutralized user-facing UI copy in `apps/web/src/app/payroll/page.tsx` (standardizing labels to 'Payroll & Statutory Roster', 'Active salaried employees', 'Onboard Employee', and 'Salary Payslip').

## [1.0.4-ga] - 2026-10-16

### Added
- Strict Pull Request mandate & branch protection protocol.
- Branch preview build & deploy automation script (`scripts/branch_deploy.sh`).
- ARYIX ecosystem branding and Sovereign Accounting Manifesto modal.
- Wiki registry structure (`wiki/FEATURE_REGISTRY.md`, `wiki/DEFECT_TRACKER.md`, `wiki/DEVELOPMENT_WORKFLOW.md`).

### Fixed
- Scrubbed all personal and non-synthetic PII/CA firm data for public open-source repository release.
