# Changelog

All notable changes to `b00k5` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-10-31

### Fixed
- **FIX-OPS-06 Sidebar Icon Import & Turnkey Production Deployment Script**:
  - Fixed missing `HardDrive` named import from `lucide-react` in `apps/web/src/components/Sidebar.tsx` that caused `tsc --noEmit` and `npm run build` in Docker production builds to fail with `Cannot find name 'HardDrive'`.
  - Replaced 0-byte `docker-compose.prod.yml` with clean production container overrides and restart policies.
  - Created first-class production deployment engine `bin/prod-deploy.sh` (with `bin/deploy-prod.sh` symlink) providing pre-flight type checking, container fleet builds, readiness polling, and ledger drift assertions.

### Added
- **FEAT-OPS-05 Unified Cloud & Database Management, Frictionless Freelancer Payments, Year Book Compensation Visibility, and Bank Statement Reconciliation**:
  - **Unified Cloud Storage & Database Management Console (`apps/web/src/app/settings/integrations/page.tsx`, `apps/web/src/components/storage/GoogleDriveSyncView.tsx`)**:
    - Consolidated Google Drive sync, S3/Cloudflare R2 cloud mirroring, and PostgreSQL database backup/restore into a single unified 3-tab console (`cloud`, `backups`, `restore`), eliminating navigation clutter and duplicate entry points.
    - Encapsulated Google Drive service account credentials, connection health verification, multi-bucket mirroring, and file archiving into `GoogleDriveSyncView`.
    - Added live 10 GB quota gauge with backup auto-retention policy and password-gated recovery modal (`AdminPass2026!`) with automatic pre-restore safety snapshot generation.
    - Added auto-redirection on legacy `/gdrive` route and updated navigation sidebar to "Cloud Storage & Backups".
  - **⚡ Frictionless Quick-Pay Freelancer & Contractor Payments (`apps/api/app/services/payroll_service.py`, `apps/web/src/components/payroll/QuickPayFreelancerModal.tsx`)**:
    - Added `QuickContractorPaymentRequest` schema with auto-onboarding (`name`, `pan`, `bank_account_number`, `ifsc_code`), `amount_type` (`gross` vs `net`), and `service_type` (`194J_TECH` at 2%, `194J_PROF` at 10%, `194C` at 1%/2%, `NO_TDS`).
    - Implemented `quick_pay_contractor` service to auto-provision contractors, compute TDS deductions, post Leg 1 Accrual JV (DR 4040, CR 2060, CR 2040), and post Leg 2 Bank Remittance JV (DR 2040, CR 1010) when immediate payout is selected.
    - Built responsive `QuickPayFreelancerModal` with real-time tax calculation preview and 1-click execution integrated into `/payroll` and `/yearbook`.
    - Exposed `POST /api/v1/payroll/contractor-payments/quick-pay` with full idempotency and double-entry balance sheet equilibrium.
  - **Year Book Compensation Visibility & Schedule III Statutory Realignment (`apps/api/app/services/schedule_iii_service.py`, `apps/web/src/app/yearbook/page.tsx`)**:
    - Recalibrated Schedule III P&L line-item mapping in `apps/api/app/services/schedule_iii_service.py` so GL account `4040` (Legal, MCA & Professional Fees) maps to `other_expenses` (Note 19) instead of being erroneously directed to `depreciation_exp`, while `4020` remains under `employee_benefits` (Note 17).
    - Added `get_yearbook_compensation_summary` service and `GET /api/v1/payroll/yearbook-summary` endpoint for aggregated FY employee salaries, contractor fees, and TDS deductions.
    - Added `'payroll_contractors'` ("Salaries & Freelancers") tab to `/yearbook` featuring Compensation Outflow KPI cards, Freelancer Payments Register, and Payroll Runs Register.
    - Recalibrated top-level Year Book Operating Expenses metric card to include personnel and freelancer burn: `totalBillsAmount + compensationSummary.grand_total_compensation_gross`.
  - **Bank Statement Withdrawal Reconciliation Engine (`apps/api/app/services/reconciliation_engine.py`, `apps/web/src/app/reconciliation/page.tsx`)**:
    - Enhanced `reconcile_statement` withdrawal processing: Tier 1 exact match against UTR/reference number and Tier 2 fuzzy contractor name + exact amount matching against open `ContractorPayment` and `PayrollRun` disbursements.
    - Automatically marks pending contractor payments as `PAID` and posts Leg 2 Disbursement JV upon verified statement match.
    - Added `matched_contractor_payment_id` and `matched_payroll_run_id` to `ConfirmMatchRequest` and `POST /api/v1/bank/statements/lines/{line_id}/confirm-match`.
    - Built interactive Action Center UI candidate cards for manual 1-click confirmation of candidate salary and freelancer payouts.
  - **Zero-Mock Verification & Docker Staging Certification (`apps/api/tests/test_quick_pay_and_reconciliation.py`, `bin/staging-deploy.sh`)**:
    - Verified quick-pay tax withholding formulas, immediate vs. deferred settlement JVs, Schedule III note separation, and statement withdrawal matching across 20 test cases with 100% pass rate in isolated Docker staging.

## [Unreleased] - 2026-10-29

### Added
- **FEAT-GST-04 GSTR-1 Table 13 Document Summary, 44+ GSTN UQC Validation, and Section 234B/C Advance Tax Penalty Warning Gauges**:
  - **GSTR-1 Table 13 Document Summary Engine (`apps/api/app/services/gstr1_service.py`)**:
    - Automated calculation of document issuance numbers across 6 statutory natures (1: Invoices, 4: Debit Notes, 5: Credit Notes, 6: Receipt Vouchers, 7: Payment Vouchers, 12: Delivery Challans).
    - Added prefix-aware natural serial decomposition (`from`, `to`, `totnum`, `canc`, `net_issue`) adhering to GST Rule 46(b) 16-character limits and GSTN Table 13 official schema specifications.
    - Updated Table 12 HSN Summary to aggregate by composite key `(hsn_code, uqc)` with automatic `NA` enforcement on Chapter 99 services.
  - **UQC Core Model & Validation Architecture (`apps/api/app/core/uqc.py`, `apps/api/app/models/invoice.py`, `apps/api/app/schemas/invoice.py`)**:
    - Added persistent `uqc VARCHAR(10)` column on `invoice_items` with auto-migration.
    - Introduced GSTN official catalog with 44+ unit quantity codes (`NOS`, `BOX`, `KGS`, `MTR`, etc.).
    - Strictly enforced GST Rule 46 service invariant: HSN codes starting with `99` (SAC) mandate `uqc = "NA"` while goods mandate non-`NA` codes.
    - Exposed `GET /api/v1/invoices/uqc-catalog` endpoint for frontend dropdown integration.
  - **Frontend InvoiceForm & UQC Validation (`apps/web/src/components/invoices/InvoiceForm.tsx`, `apps/web/src/app/invoices/new/page.tsx`)**:
    - Built reusable line-item editor with real-time Chapter 99 auto-detection, disabling unit selection with statutory tooltip guidance for service SAC codes, and standard 44+ GSTN dropdowns for goods.
    - Added live intra-state (CGST+SGST) vs inter-state (IGST) split computation with banker's precision rounding.
  - **Year Book Advance Tax §234B/C Penalty Warning Gauges (`apps/web/src/components/yearbook/AdvanceTaxGauges.tsx`, `apps/web/src/app/yearbook/page.tsx`)**:
    - Built interactive quarterly gauge widget (Q1 15%, Q2 45%, Q3 75%, Q4 100%) integrated with `/api/v1/compliance/advance-tax/forecast`.
    - Visualized Section 208 statutory thresholds (₹10,000 net liability), Safe Harbor markers (12% Q1, 36% Q2), and real-time penal interest tracking for §234C deferral and §234B default interest.
    - Provided proactive monthly recommended savings reserve callouts and quick ITNS 280 challan recording triggers.
  - **Zero-Mock Unit Tests (`apps/api/tests/test_gstr1_table13_and_uqc.py`, `apps/api/tests/test_compliance.py`)**:
    - Verified Table 13 document summary generation, contiguous prefix-based grouping, cancellation counts, UQC service invariant enforcement, and corporate tax regime calculations with 100% test pass rate.

## [Unreleased] - 2026-10-18

### Fixed
- **DEF-24 Form AOC-4 Vault Misclassification, SRN Truncation & Statutory Anchor Discrepancy**:
  - Remediated statutory filing classification in `apps/api/app/services/statutory_vault_engine.py` to prevent auditor report extracts (`EXTRACT OF AUDITOR`) containing `"ATTACHED WITH FORM AOC-4"` from being misclassified as Form AOC-4 and overwriting authentic financial statements in `DocumentVault`.
  - Preserved authentic 11-digit MCA V3 Service Request Numbers (e.g. `1-27616438562`) by eliminating string-truncation bugs.
  - Added multi-bucket vault probing in `apps/api/app/services/statutory_anchor_service.py` to discover and synchronize filings stored across both `b00k5-statutory` and `b00k5-vault` MinIO storage buckets.
  - Added `other_current_liabilities` roll-forward in `apps/api/app/services/schedule_iii_service.py`, ensuring complete permanent account continuity.
  - Synchronized statutory figures with full balance sheet and P&L line-item fidelity matching uploaded Form AOC-4 documents, verifying zero balance sheet drift ($\left|\text{Assets} - \text{Liabilities}\right| \equiv 0.00$) across both historical and current reporting periods.
- **DEF-23 Schedule III PDF Export Header Overlap & Permanent Account Roll-Forward**:
  - Remediated table column header overlap in `ScheduleIIIService._render_schedule_iii_pdf` on Page 1 (Balance Sheet) and Page 2 (Statement of Profit and Loss) by refactoring the single-line header box to a structured 2-line layout (`Particulars`, `Note No.`, `Figures as at` / date, and `For period ended` / date) with generous column clearances.
  - Eliminated artificial ₹1,00,000 balance sheet drift in `ScheduleIIIService._resolve_schedule_iii_components` by rolling forward permanent balance sheet accounts (opening retained deficit and director long-term borrowings) from filed Form AOC-4 anchors into ongoing fiscal year operations, achieving exact equilibrium ($\text{Assets} \equiv \text{Liabilities} \equiv ₹5,000.00$) with zero mathematical drift.
  - Updated Schedule III Note 3 (*Reserves and Surplus*) opening surplus disclosure to pull authentic prior year opening reserves anchor in both PDF export and web API summary.

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
