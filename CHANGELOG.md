# Changelog

All notable changes to `b00k5` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-11-02

### Fixed
- **FIX-STAGING-01 Dynamic API Port Routing, Presigned URL Tenant Boundary, and Ephemeral Test Company Purge (`apps/web/src/lib/api.ts`, `apps/api/app/api/v1/storage.py`, `bin/staging-deploy.sh`, `docker-compose.staging.yml`, `docker/frontend.Dockerfile`, `init_schema.sql`)**:
  - **Dynamic Client Routing (`getApiBase()`)**: Added port detection in `apps/web/src/lib/api.ts` to automatically route browser requests on port 3001 to Staging API on port 8001, and port 3000 to Production API on port 8000, eliminating client-side cross-talk with production containers.
  - **Storage Presigned URL BOLA/IDOR Hardening**: Restricted cross-tenant presigned URL generation strictly to platform super administrators in `storage.py`, returning HTTP 403 Forbidden whenever tenant keys mismatch.
  - **Contractor Payments Database Schema Sync**: Added missing `cancellation_reason` and `cancelled_at` columns to `contractor_payments` table in `init_schema.sql`, matching the runtime SQLAlchemy model and resolving staging Quick-Pay insert failures.
  - **Staging Test Suite Expansion & Automatic Test Tenant Purge**: Enhanced `bin/staging-deploy.sh` to execute 13 end-to-end tests (including live backup snapshot creation, MinIO checkpoint listing, IAM security checks, and automated post-test deletion of ephemeral mock companies from PostgreSQL).
  - **Production Database Cleanup**: Cleanly purged 25 legacy mock test companies and test users created by past test runs from production PostgreSQL, restoring `ARYIX (OPC) PRIVATE` as the sole pristine company record.
- **FIX-AUDIT-ALL 360-Degree System Hardening: Statutory Reconciliation Locks, Security Boundaries, BCDR Integrity, and Ind AS 8 Compliance (`apps/api/app/services/payroll_service.py`, `apps/api/app/api/v1/expenses.py`, `apps/api/app/api/v1/invoices.py`, `apps/api/app/api/v1/storage.py`, `apps/api/app/services/db_backup.py`, `apps/web/src/app/settings/integrations/page.tsx`, `apps/web/src/app/payroll/page.tsx`, `apps/web/src/app/invoices/page.tsx`, `apps/web/src/app/expenses/page.tsx`)**:
  - **DEF-01 (Statutory Reconciliation Strike-Off Lock for Contractor Payments)**: Prohibited strike-off of freelancer/contractor payments when marked `reconciled` or linked to an audited `BankStatementLine` in `payroll_service.py`. Enforces double-entry Bank Reconciliation Statement (BRS) integrity per CARO 2020.
  - **DEF-02 (Statutory Reconciliation Strike-Off Lock for Expenses)**: Blocked strike-off of corporate expenses when marked `reconciled` or matched against bank feed in `expenses.py`.
  - **DEF-03 (Paid & Reconciled Invoice Cancellation Prohibition)**: Prohibited direct strike-off of paid or reconciled outward tax invoices in `invoices.py`. Directs users to issue statutory Credit Notes under Section 34 of the CGST Act 2017 to preserve Accounts Receivable audit trail.
  - **DEF-04 (Next.js 14 App Router State Preservation)**: Preserved `window.history.state` during tab and provider switching in `settings/integrations/page.tsx`, eliminating flight router tree clobbering and root layout crashes (`can't access property "get", t.parallelRoutes is null`).
  - **DEF-05 (BCDR Silent Restore Failure Hardening)**: Corrected `DatabaseBackupManager.execute_pg_restore` in `db_backup.py` to return `False` and log errors on `pg_restore` exit code $> 1$, eliminating false-positive disaster recovery reports.
  - **DEF-06 (AppSec Presigned URL Authentication & Tenant Isolation)**: Secured `GET /api/v1/storage/presigned-url` behind mandatory `get_current_tenant` and `get_current_user` IAM dependencies, enforcing namespace isolation to prevent unauthenticated cross-tenant file downloads.
  - **DEF-07 (BOLA / IDOR Cloud Sync Status Fix)**: Scoped `GET /api/v1/storage/sync-status/{sync_id}` to `CloudSyncLedger.tenant_id == tenant.id`, preventing unauthorized enumeration of sync telemetry.
  - **DEF-08 (Frontend UI Button Locks)**: Replaced active strike-off buttons with disabled lock indicators and statutory tooltips on reconciled transactions in `payroll/page.tsx`, `invoices/page.tsx`, and `expenses/page.tsx`.
  - **DEF-09 (Ind AS 8 / AS-5 Accounting Dating)**: Fixed invoice strike-off reversal JV dating to `dt_date.today()` (current active fiscal period) rather than backdating into closed financial years.
  - **DEF-11 (Decimal Monetary Precision)**: Migrated float conversions in `auditor_dossier_service.py` to strict `Decimal` string formatting, eliminating IEEE 754 precision drift.
  - **DEF-12 (Null-Safe Metric Formatting)**: Guarded all remaining `.toFixed()` calls in `settings/integrations/page.tsx` against undefined byte and duration counts.

### Added
- **FEAT-OPS-06 Stakeholder-Centric Auditor Dossier & Dual-Plane BCP/DR Backup Hierarchy (`apps/api/app/services/auditor_dossier_service.py`, `apps/api/app/api/v1/storage.py`, `apps/api/app/services/gdrive_virtualizer.py`, `tests/integration/test_stakeholder_dossier_and_bcp.py`)**:
  - Restructured `AuditorDossierService` export engine to generate a canonical, stakeholder-oriented 9-section statutory hierarchy (.zip):
    - `00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/` (Founder & CFO: Executive Financial Briefing, Compliance Scorecard, Permanent Registrations COI/MOA/AOA/PAN/TAN/GST/ADT-1, Governance Profile JSON).
    - `01_STATUTORY_FINANCIAL_STATEMENTS_SCHEDULE_III/` (CA & External Auditor: Schedule III Balance Sheet, P&L, Notes 1-22, Trial Balance, CARO 2020 Order).
    - `02_CORPORATE_GOVERNANCE_AND_SECRETARIAL_MCA/` (Company Secretary: SS-1 Board Minutes, SS-2 AGM/EGM Minutes, MCA Annual Filings AOC-4/MGT-7A with SRN receipts, CA2013 Statutory Registers).
    - `03_TAX_COMPLIANCE_AND_STATUTORY_RETURNS/` (CA & Tax Auditor: GST GSTR-1/3B/9/2B, Direct Tax ITR-6/26AS/AIS/TIS/Advance Tax 280, TDS 24Q/26Q/16/16A).
    - `04_BANKING_CASH_AND_TREASURY_RECONCILIATION/` (CFO & Auditor: Monthly Bank Statements, Bank Reconciliation BRS Registers, CMS Bulk Payout Logs).
    - `05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/` (Auditor: Monthly Outward Tax Invoices, Sales Register, Debtors Ageing Schedule).
    - `06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/` (Auditor: Monthly Inward Vendor Bills & Expense Vouchers, Bills Summary, MSME Creditors Ageing, Input Tax Credit ITC Register).
    - `07_PAYROLL_PERSONNEL_AND_LABOR_LAW_COMPLIANCE/` (Auditor & HR: Monthly Salary Registers, EPFO ECR, ESIC, PT Form 5, Contractor TDS Summaries).
    - `08_AUDIT_TRAIL_AND_CRYPTOGRAPHIC_INTEGRITY/` (Auditor & MCA Sec 128: Statutory Close Checklist, Section 128 Audit Trail Certificate, Cryptographic SHA-256 Digest Manifest).
  - Implemented Dual-Plane Cloud Backup Synchronization across Cloudflare R2, AWS S3, and Google Drive:
    - **Plane 1 (Disaster Recovery & Machine Speed Restore)**: Preserves atomic AES-256-GCM encrypted database dumps, MinIO raw object tarballs, and integrity manifests in `checkpoints/` (`RTO < 10 min`, `RPO < 1 hr`).
    - **Plane 2 (Statutory Governance & Human Audit)**: Organizes live documents into canonical `FY {YYYY}-{YY} (AY {YYYY+1}-{YY+1})` and `00_Entity_Master_Permanent_Records/` hierarchies without software lock-in.
  - Added `get_indian_fy_ay_label` and `build_statutory_dossier_path` to `DirectoryVirtualizer` with 100% backward compatibility for existing tests.
  - Added comprehensive automated test suite in `tests/integration/test_stakeholder_dossier_and_bcp.py` verifying all 9 statutory sections, cryptographic hashes, and executive briefing accuracy.

## [Unreleased] - 2026-11-01

### Fixed
- **FIX-BACKUP-10 Unified Backup & Checkpoint API Routing and R2 Mirroring (`apps/web/src/app/settings/integrations/page.tsx`, `apps/api/app/api/v1/system.py`, `apps/api/app/api/v1/backup.py`, `apps/api/app/main.py`)**:
  - Re-routed frontend backup trigger, audit logs, MinIO snapshots, checkpoint creation, and restore execution from mismatched `/api/v1/backup/...` paths to canonical `/api/v1/system/backup-...` endpoints, eliminating HTTP 404 "Not Found" failures across `/settings/integrations`.
  - Added dedicated FastAPI compatibility alias router `apps/api/app/api/v1/backup.py` mounted at `/api/v1/backup` (`/trigger`, `/logs`, `/minio-snapshots`, `/minio-checkpoint`, `/restore`), providing dual-route resilience for all backup and restore operations.
  - Relaxed `trigger_database_backup` authorization from strict `require_super_admin` to `require_super_admin_or_owner`, enabling authorized company owners and directors to run on-demand database backups and automatic Cloudflare R2 / S3 mirrors.
  - Normalized `RestoreCheckpointRequest` to accept polymorphic key mappings (`object_key` or `snapshot_key`, `decryption_secret` or `admin_secret`).
  - Broadened S3 backup mirror query in `storage.py` to include tenant-scoped and system-level backups (`or_(DatabaseBackupLog.tenant_id == tenant.id, DatabaseBackupLog.tenant_id.is_(None))`).
- **FIX-STORAGE-09 Cloudflare R2 / S3 Storage Quota Null-Safe Rendering (`apps/web/src/app/settings/integrations/page.tsx`, `apps/api/app/api/v1/storage.py`)**:
  - Guarded Cloudflare R2 / S3 Quota & Capacity Usage card rendering with strict `configured` and numeric `typeof total_mb === 'number'` assertions, eliminating `TypeError: can't access property "toFixed", eb.storage_usage.total_mb is undefined` when viewing unconfigured or uninitialized remote buckets.
  - Implemented nullish coalescing defaults across all metric calculations (`total_mb`, `used_percentage`, `remaining_free_gb`, `free_tier_gb`, `file_count`, `reclaimed_mb`) and dual-key category lookups (`sales_invoices`/`invoices`, `vendor_bills`/`bills`, `statutory_vault`/`statutory`, `database_backups`/`backups`).
  - Enhanced `GET /api/v1/storage/s3-config` to return structured zero-metric usage schemas for configured buckets awaiting initial sync and `None` when unconfigured.
- **FIX-PAYROLL-08 Statutory & Bank CMS Export Authorization Credentials (`apps/web/src/app/payroll/page.tsx`)**:
  - Replaced ad-hoc `localStorage.getItem('token')` fetch logic in `handleDownloadFile` with standardized `fetchRawApi` from `@/lib/api`.
  - Resolves HTTP 401 Unauthorized (`Authentication credentials not provided`) error when downloading HDFC ENet, ICICI CMS, SBI CMP, EPFO ECR, ESIC, PT returns, and Form 16A PDF certificates.
  - Automatically extracts dynamic server-provided attachment filename from `Content-Disposition` header with robust fallback to default statutory filename.
- **FIX-UI-01 App Router Shallow Navigation Crash (React Invariant #310 & `t.parallelRoutes is null`)**:
  - Replaced Next.js `router.replace` with native `window.history.replaceState` in `apps/web/src/app/settings/integrations/page.tsx` for shallow tab and provider switching (`cloud`, `backups`, `restore`, `gdrive`, `s3`/Cloudflare), eliminating Next.js 14 App Router Flight reducer crash (`parallelRoutes.get()` on null segment cache).
  - Hardened `apps/web/src/app/global-error.tsx` root layout error boundary with clean `window.location.reload()` and `/dashboard` fallback, preventing infinite crash loops on client router cache corruption.

### Added
- **FEAT-PAYROLL-07 Contractor & Freelancer Payment Statutory Strike-Off Engine with Audit Notes**:
  - Implemented `POST /api/v1/payroll/contractor-payments/{payment_id}/strike-off` with `ContractorPaymentStrikeOffRequest` (`reason: str`).
  - Added statutory contra reversal engine in `PayrollService.strike_off_contractor_payment`: automatically posts offsetting contra journal entries for posted accrual JVs (`JV-REV-CPAY-...`) and disbursement JVs (`JV-REV-DISB-...`), cancels related TDS deductions, and preserves strict ledger balance equilibrium ($\sum \text{Dr} = \sum \text{Cr} \equiv 0.00$).
  - Added `cancellation_reason` and `cancelled_at` fields to `contractor_payments` and updated `get_yearbook_compensation_summary` and `calculate_form_16a` to exclude struck-off records from Year Book burn and Form 16A TDS certificates.
  - Added "Strike Off" action modal to `/payroll` with payment breakdown, statutory audit explanation, and live table updates (red `STRUCK OFF` badge, strike-through styling, and inline reason tooltip).
  - Added comprehensive automated test suite in `apps/api/tests/test_payroll_contractors.py` validating 100% test pass rate with zero ledger drift.

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
