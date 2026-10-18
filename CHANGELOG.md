# Changelog

All notable changes to `b00k5` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-10-18

### Added
- **FEAT-ROC-03 MCA Form AOC-4 & Form MGT-7A Statutory Calibration & Schedule III Comparative Presentation Engine**:
  - Implemented OCR and regex extraction engine in `apps/api/app/services/statutory_vault_engine.py` parsing filed Form AOC-4 (SRN, DIN, UDIN, balance sheet heads) and Form MGT-7A (SRN, authorized capital, paid-up capital, net worth, promoter shareholding pattern).
  - Added baseline synchronization engine `sync_statutory_anchors_from_vault` in `apps/api/app/services/statutory_anchor_service.py` anchoring filed government forms as immutable statutory anchors (`StatutoryFilingAnchor`).
  - Calibrated live Schedule III financial statements engine in `apps/api/app/services/schedule_iii_service.py`:
    - Synchronizes vault anchors for both current and prior reporting periods.
    - Implemented Schedule III Division I comparative presentation: Current reporting period vs Previous reporting period (FY 2025-26 / AY 2026-27).
    - Directly auto-populates historical period financial figures from filed Form AOC-4 when live ledger transactions are zero, maintaining zero mathematical drift.
    - Exported statutory dossier package (`generate_statutory_dossier_package`) producing 11-page certified PDF and comparative Balance Sheet / P&L CSVs.
  - Enhanced Next.js frontend component `apps/web/src/components/yearbook/ScheduleIIIViewer.tsx`:
    - Rendered Statutory Provenance Verification Banner citing Form AOC-4 SRN `7616438575` and Form MGT-7A SRN `AC6319079` with zero mathematical drift indicator.
    - Refactored Balance Sheet and Statement of Profit and Loss tables into clean 3-column Schedule III Division I comparative format (`Particulars`, `Current Period`, `Previous Period`).
    - Added Note 2 & Form MGT-7A Governance & Shareholding Pattern Disclosure Card with Authorised Capital (₹1,00,000), Paid-up Capital (₹1,00,000), Net Worth (-₹63,851.00), >5% Shareholders table, and Promoter Shareholding table (100% promoter held).
    - Built expandable Notes to Accounts (Notes 1 to 20) with comparative values, accounting policies, and mandatory ratio disclosures.
  - Added automated test suite `test_aoc4_mgt7_statutory_anchor_and_schedule_iii_comparative` in `apps/api/tests/test_roc_compliance_and_esign.py`.
- **FEAT-PAY-01 Sovereign Native Payroll Core & Double-Entry General Ledger Integration**:
  - Implemented database schema in `init_schema.sql` (Section 14) for `employees`, `salary_structures`, `payroll_runs`, `payslips`, and `employee_tax_declarations` with PostgreSQL 16 RLS policies and chart of accounts (`2070-2077`, `4020-4023`).
  - Added SQLAlchemy models in `apps/api/app/models/payroll.py` and Pydantic validation schemas in `apps/api/app/schemas/payroll.py`.
  - Built core statutory calculation engine `PayrollService` with Section 192 TDS (Finance Act 2024 New 115BAC vs Old regime), EPF Act 1952 (12% employee/employer, EPS capped at ₹1,250), ESI Act 1948 (0.75% / 3.25% on gross $\le$ ₹21,000), Professional Tax (Karnataka, Maharashtra, Delhi), and Loss of Pay (LOP) calendar-day proration using Banker's Rounding (`Decimal(15, 2)`).
  - Implemented atomic 3-Leg Double-Entry General Ledger journal vouchers: Leg 1 Month-End Accrual (Dr. 4020, 4021, 4022 vs Cr. 2070-2076) with SHA-256 tamper-evident seal, and Leg 2 Salary Disbursement (Dr. 2070 vs Cr. 1010 Bank).
  - Integrated Schedule III Balance Sheet (Note 7 Other Current Liabilities) and P&L (Note 17 Employee Benefits Expense).
  - Created REST API router in `apps/api/app/api/v1/payroll.py` and full regression test suite in `apps/api/tests/test_payroll_ledger_inviolability.py` and `apps/api/tests/test_payroll_api_e2e.py`.
  - Built dark-mode Sovereign Payroll & Statutory Roster web interface (`apps/web/src/app/payroll/page.tsx`) with Monthly Payroll Runs, Employee Onboarding & CTC breakdowns, Itemized Payslip receipts, and statutory compliance tabs.
  - Linked Payroll navigation item across Owner, CA Auditor, Super Admin, and Employee roles in `apps/web/src/components/Sidebar.tsx`.
- **FEAT-PAY-02 Statutory Portals Exporter Suite & Section 192 Form 16 Engine**:
  - Implemented official EPFO Electronic Challan cum Return (ECR 2.0) `#~#` pipe-delimited text generator adhering to EPF Scheme 1952 Paragraph 38 specification with 11 statutory fields and wage capping (`/api/v1/payroll/runs/{id}/export/epfo-ecr`).
  - Added ESIC Monthly Return portal upload CSV generator with 10-digit IP number validation and paid working days schedule (`/api/v1/payroll/runs/{id}/export/esic`).
  - Built State-Wise Professional Tax (PT) Form 5 monthly return summary exporter with wage slab grouping and headcount totals (`/api/v1/payroll/runs/{id}/export/pt`).
  - Implemented Section 192 Form 16 Part A and Part B annual salary and tax computation engine, incorporating Finance Act 2024 New Tax Regime (Section 115BAC ₹75,000 standard deduction, Section 87A rebate, and 4% health & education cess) and certified ReportLab PDF certificate generation (`/api/v1/payroll/employees/{id}/form-16/pdf`).
  - Enhanced Next.js Payroll UI (`apps/web/src/app/payroll/page.tsx`) with 1-click download actions for ECR, ESIC, and PT across Payroll Runs and Statutory Breakdown tabs, and Form 16 PDF download buttons in the Itemized Payslips table.
  - Added comprehensive automated test suite `apps/api/tests/test_payroll_statutory_exporters.py` (4/4 tests passing, bringing payroll test coverage to 17/17 passing tests).
- **FEAT-PAY-05 Contractor & Freelancer Payouts, Section 194C/194J Statutory TDS Withholding, and Form 16A PDF Engine**:
  - Provisioned `contractors` and `contractor_payments` tables in `init_schema.sql` (Section 15) with PostgreSQL 16 multi-tenant Row-Level Security policies (`tenant_isolation_contractors`, `tenant_isolation_contractor_payments`).
  - Added SQLAlchemy models in `apps/api/app/models/payroll.py` and Pydantic schemas in `apps/api/app/schemas/payroll.py` supporting entity types (`individual`, `huf`, `partnership`, `company`, `llp`), PAN/GSTIN tracking, and Section 194C/194J schemes.
  - Implemented statutory withholding engine in `apps/api/app/services/payroll_service.py` adhering to CBDT Circular 23/2017 (TDS deducted strictly on gross service base excluding GST), two-legged double-entry ledger vouchers (Leg 1 Accrual: Dr. 4040/4020, Dr. 1030 GST vs Cr. 2060/2061 TDS, Cr. 2040 Payables; Leg 2 Disbursement: Dr. 2040 Payables vs Cr. 1010 Bank), and Section 203 Form 16A quarterly summary computation.
  - Implemented ReportLab Form 16A PDF certificate generator in `apps/api/app/services/pdf_service.py` (`generate_form_16a_pdf`) with deductor/deductee identity grid, payment and TDS schedules, words converter, and digital signature block.
  - Built REST API endpoints (`/api/v1/payroll/contractors`, `/api/v1/payroll/contractor-payments`, accrue, disburse, and form-16a pdf download).
  - Designed interactive UI tab 'Contractors & Freelancers' in `apps/web/src/app/payroll/page.tsx` with Contractor Directory, Payout Claims ledger, Onboarding Modal, Record Payout Modal with live statutory breakdown card, and Form 16A PDF download triggers.
  - Added test suite `apps/api/tests/test_payroll_contractors.py` (3/3 passing), bringing test suite to 53/53 green tests.
- Comprehensive Competitor Benchmarking Matrix and reverse-engineered feature inventory comparing `b00k5` with Zoho Books, Odoo 17/18 Accounting, Zoho Payroll, RazorpayX, and Tally Prime (`docs/COMPETITIVE_BENCHMARK.md`).
- Formalized feature registry records in `wiki/FEATURE_REGISTRY.md` for:
  - `FEAT-PAY-01` to `FEAT-PAY-05`: Embedded Sovereign Payroll & Unified People Roster (Salaried 192 + Contractor 194C/J).
  - `FEAT-INV-05` to `FEAT-INV-07`: Items Master, Ind AS 2 Perpetual FIFO Inventory, and Section 17(5)(h) ITC Reversals.
  - `FEAT-SC-01` to `FEAT-SC-02`: Purchase Orders $\rightarrow$ Goods Receipts $\leftrightarrow$ Vendor Bills (3-Way Matching) and Landed Cost Allocation.
  - `FEAT-BANK-04` to `FEAT-BANK-05`: Dynamic Regex Banking Rules and Interactive Split-Match Workbench.
  - `FEAT-AUDIT-01`: MCA Rule 3(1) Companies (Accounts) Rules universal tamper-proof audit trail table with database triggers.
  - `FEAT-GST-01` to `FEAT-GST-02`: GSTR-1 Portal JSON Export and Rule 37 180-day ITC Reversal Watchdog.
- **FEAT-BANK-04 Corporate Bank CMS Batch Payout Rails (HDFC ENet, ICICI CMS, SBI CMP)**:
  - Built offline corporate netbanking batch file generator in `apps/api/app/services/payroll_service.py` supporting `hdfc_enet`, `icici_cms`, and `sbi_cmp` formats for both monthly salaried runs and approved contractor payout claims.
  - Added REST endpoints `GET /api/v1/payroll/runs/{id}/export/bank-cms` and `GET /api/v1/payroll/contractor-payments/export/bank-cms`.
  - Added single-click export triggers across Tab 1 (Run Payroll), Tab 3 (Statutory Filings), and Tab 5 (Contractors & Freelancers) in `apps/web/src/app/payroll/page.tsx`.
  - Added automated test suite `apps/api/tests/test_bank_cms_exporter.py` verifying all 3 bank formats.
- **FEAT-GST-01 Official GSTR-1 Portal-Ready JSON Exporter (Offline Utility)**:
  - Implemented official GSTN offline utility JSON synthesizer in `apps/api/app/services/gstr1_export_service.py` producing schema-compliant payloads covering B2B (Table 4), B2CL (Table 5), B2CS (Table 7), CDNR (Table 9B), EXP (Table 6A), HSN Summary (Table 12), and Document Issue (Table 13).
  - Added REST endpoint `GET /api/v1/invoices/export/gstr-1` in `apps/api/app/api/v1/invoices.py`.
  - Added GSTR-1 Export Modal and header action trigger in `apps/web/src/app/invoices/page.tsx` with Year and Month selectors for direct upload to `gst.gov.in`.
  - Added automated test suite `apps/api/tests/test_gstr1_json_exporter.py`.
- **Architectural Research Specifications (Options B & C)**:
  - Authored [`docs/RESEARCH_OPTION_B_AUDIT_TRAIL_AND_BACKUP.md`](file:///Users/adithya/Code/b00k5/docs/RESEARCH_OPTION_B_AUDIT_TRAIL_AND_BACKUP.md) covering MCA Rule 3(1) Companies (Accounts) Rules 2014 immutable audit trail triggers, REVOKE policies, and AES-256 local encrypted backup/restore specs (`FEAT-AUDIT-01`, `FEAT-SYS-02`).
  - Authored [`docs/RESEARCH_OPTION_C_SUPPLY_CHAIN_AND_INVENTORY.md`](file:///Users/adithya/Code/b00k5/docs/RESEARCH_OPTION_C_SUPPLY_CHAIN_AND_INVENTORY.md) covering Supply Chain 3-Way PO Matching (PO $\rightarrow$ GRN $\rightarrow$ Bill), Ind AS 2 / ICDS II perpetual FIFO inventory, landed cost allocation, and CGST Section 17(5)(h) ITC write-off rules (`FEAT-SC-01`, `FEAT-INV-05`).

### Changed
- Removed 'Sovereign' badge pill from `Sidebar.tsx` navigation across Owner, CA Auditor, Super Admin, and Employee modes.
- Neutralized user-facing UI copy in `apps/web/src/app/payroll/page.tsx` (standardizing labels to 'Payroll & Statutory Roster', 'Active salaried employees', 'Onboard Employee', and 'Salary Payslip').

### Fixed
- **DEF-PAY-01 URL Tab Parameter Synchronization**: Synchronized `activeTab` with query parameter `?tab=payslips` so employee navigation lands directly on personal payslips.
- **DEF-PAY-02 Role-Based Privilege Boundaries in Payroll UI**: Isolated corporate management tabs (`Payroll Runs`, `Employee Roster`, `Contractors`, `Statutory Breakdown`) and admin action buttons (`New Payroll Run`, `Onboard Employee`) from employee sessions. Rendered tailored employee self-service workbench with personal take-home, TDS, and EPF metrics.
- **DEF-PAY-03 Employee Self-Service Payslip Retrieval**: Added dedicated `GET /api/v1/payroll/my-payslips` endpoint returning payslips filtered strictly to authenticated employee email, avoiding corporate `/runs` 403 Forbidden errors.
- **DEF-PAY-04 Form 16 Part B Certificate Self-Service**: Authorized employee access to `GET /api/v1/payroll/employees/{id}/form-16/pdf` for their own tax certificate download.
- **DEF-PAY-05 Offset-Naive vs Offset-Aware Timezone Error**: Normalized `inv.expires_at` timezone handling in invitation acceptance flow (`POST /api/v1/tenants/accept-invite`).

## [1.0.4-ga] - 2026-10-16

### Added
- Strict Pull Request mandate & branch protection protocol.
- Branch preview build & deploy automation script (`scripts/branch_deploy.sh`).
- ARYIX ecosystem branding and Sovereign Accounting Manifesto modal.
- Wiki registry structure (`wiki/FEATURE_REGISTRY.md`, `wiki/DEFECT_TRACKER.md`, `wiki/DEVELOPMENT_WORKFLOW.md`).

### Fixed
- Scrubbed all personal and non-synthetic PII/CA firm data for public open-source repository release.
