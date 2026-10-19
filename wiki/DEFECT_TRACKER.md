# b00k5 Defect Tracker & Remediation Inventory

This document tracks all identified software defects, statutory compliance anomalies, security issues, and UI/UX regressions across `b00k5`. Every defect is assigned a tracking ID, classified by severity, and traced to its zero-mock verification test.

---

## 🚦 Severity Classification

| Level | Severity | Description | SLA for Fix |
| :---: | :--- | :--- | :---: |
| 🔴 | **CRITICAL** | Data loss, multi-tenant RLS leak, ledger drift, statutory deadline failure, or secret exposure. | Immediate (< 4 hrs) |
| 🟠 | **HIGH** | Financial calculation mismatch, GST POS miscalculation, document corruption, or broken auth role. | 24 Hours |
| 🟡 | **MEDIUM** | UI state desync, missing non-critical validation, tab desynchronization, or UX confusion. | 3 Days |
| 🟢 | **LOW** | Cosmetic spacing, typo, minor print CSS enhancement, or non-blocking telemetry improvement. | Next Sprint |

---

## 📋 Master Defect Inventory (DEF-01 to DEF-21)

| Defect ID | Module | Title | Severity | Status | Root Cause & Resolution | Verification Test |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| **DEF-01** | `auth` | Multi-Tenant Session Cross-Contamination | 🔴 Critical | **FIXED** | User session retained stale `tenant_id` upon re-login. Resolved via strict session reset and server-side JWT tenant claims validation. | `tests/integration/test_critical_fixes.py` |
| **DEF-02** | `ledger` | Floating-Point Binary Imprecision in GST | 🔴 Critical | **FIXED** | Native Python `float` was used in POS calculation causing rounding drift. Converted all monetary math to `Decimal(15, 2)` with Banker's Rounding (`ROUND_HALF_EVEN`). | `tests/unit/test_ledger_math.py` |
| **DEF-03** | `vault` | MinIO Storage Key Path Injection | 🔴 Critical | **FIXED** | Upload path permitted unvalidated characters. Enforced UUID-prefixed strict slugification and tenant namespace isolation. | `tests/integration/test_phase12_tax_vault_gst_backup_e2e.py` |
| **DEF-04** | `governance` | SS-1 120-Day Board Meeting Interval Breach | 🔴 Critical | **FIXED** | Board meeting interval watchdog failed to trigger when gap exceeded 120 days. Implemented statutory countdown query under Companies Act §173(1). | `tests/integration/test_phase7_statutory_and_llp.py` |
| **DEF-05** | `dsc` | PKCS#11 Local Loopback Port Timeout | 🟠 High | **FIXED** | Bridge on port 28045 hung on token disconnect. Added 3-second heartbeat and auto-reconnect fallback. | `tests/e2e/governance_dsc_sign.spec.ts` |
| **DEF-06** | `invoices` | Inter-State IGST vs Intra-State CGST/SGST Desync | 🔴 Critical | **FIXED** | POS state code comparison failed when state codes were strings with leading zeros. Enforced 2-digit integer normalized comparison. | `tests/integration/test_critical_fixes.py` |
| **DEF-07** | `banking` | Bank Feed UTR Deduplication Failure | 🟠 High | **FIXED** | Identical transactions imported twice in multi-batch CSV upload. Implemented compound unique constraint on `(tenant_id, account_id, utr_or_reference_number)`. | `tests/unit/test_bank_parser.py` |
| **DEF-08** | `expenses` | OCR Extraction Timeout on Multi-Page PDF | 🟠 High | **FIXED** | Synchronous OCR in request thread timed out after 30s. Moved Tesseract/pdfplumber to Celery background task queue. | `tests/integration/test_critical_fixes.py` |
| **DEF-09** | `iam` | Auditor Access Allowed Expense Modifications | 🔴 Critical | **FIXED** | Role `auditor_ca` had update permissions on expenses. Added read-only policy guard prohibiting mutation endpoints. | `tests/e2e/test_selenium_iam_multitenant_profiles.py` |
| **DEF-10** | `compliance` | INC-20A Borrowing Power Gate Bypass | 🔴 Critical | **FIXED** | Borrowing operations were accessible before Sec 10A declaration was verified. Added `borrowing_powers_active` check guard on credit facilities. | `tests/integration/test_critical_fixes.py` |
| **DEF-11** | `vault` | Synthetic Overwrite of Authentic PDFs | 🔴 Critical | **FIXED** | System generated synthetic ReportLab files overwriting original vendor tax invoices. Strictly enforced MinIO authentic binary preservation. | `tests/integration/test_master_directive_audit.py` |
| **DEF-12** | `yearbook` | Schedule III Division I Auto-Rounding Drift | 🟠 High | **FIXED** | Rounding to Lakhs/Thousands resulted in balance sheet imbalance. Implemented plug-balancing into Reserves & Surplus. | `tests/integration/test_phase11_tally_speed_einvoice_and_mca.py` |
| **DEF-13** | `taxes` | Advance Tax 234C Interest Calculation Error | 🟠 High | **FIXED** | Installment schedule did not account for statutory thresholds (15%, 45%, 75%, 100%). Implemented statutory 4-stage tax watchdog. | `tests/integration/test_phase8_statutory_baseline_and_advance_tax.py` |
| **DEF-14** | `tds` | Section 194J Professional Fee Rate Anomaly | 🟠 High | **FIXED** | System applied 10% for Technical Services instead of 2% under amended Sec 194J(1). Added sub-category selector (Technical 2% vs Professional 10%). | `tests/integration/test_phase10_tds_and_fixed_assets.py` |
| **DEF-15** | `branding` | Logo File Load Path Traversal | 🔴 Critical | **FIXED** | PDFService loaded logo paths directly from disk. Enforced MinIO authenticated S3 stream with SHA-256 deduplication and text fallback. | `tests/integration/test_phase2_branding_vault_dpt3.py` |
| **DEF-16** | `llp` | LLP Form 11 / Form 8 Inapplicable Fields | 🟡 Medium | **FIXED** | Private Limited share capital inputs rendered for LLP entities. Implemented entity-aware form switching (LLP Contribution vs Share Capital). | `tests/integration/test_phase7_statutory_and_llp.py` |
| **DEF-17** | `export` | Auditor Dossier Export Incomplete | 🟠 High | **FIXED** | Dossier ZIP omitted bank statements and statutory returns. Refactored `auditor_dossier_service.py` to bundle all verified records. | `tests/integration/test_phase12_tax_vault_gst_backup_e2e.py` |
| **DEF-18** | `ui` | Overlapping Typography on Mobile & Print | 🟡 Medium | **FIXED** | Print CSS lacked `@page` boundaries, cutting off statutory footers. Added print-specific CSS and responsive typography tokens. | `tests/e2e/test_selenium_full_page_audit.py` |
| **DEF-19** | `db` | Database Backup RTO Exceeded 60s | 🟠 High | **FIXED** | Single-threaded pg_dump was slow. Upgraded to AES-256-GCM parallel compression drill achieving < 30s RTO. | `scripts/dr_drill.py` |
| **DEF-20** | `iam` | Duplicate Navigation Links for IAM | 🟡 Medium | **FIXED** | Both `/iam` and `/settings/team` appeared in navigation. Consolidated into `/iam` with Target Organization Scope Badge. | `tests/e2e/test_selenium_aryix_branding_and_about.py` |
| **DEF-21** | `branding` | Non-Compliant Brand Name Suffix & Watermarks | 🟠 High | **FIXED** | UI used `Aryix (OPC) Pvt Ltd` and risked invoice watermarks. Enforced clean **ARYIX** brand, link to `https://www.aryix.co.in/`, and strict Statutory Document Neutrality. | `tests/e2e/test_selenium_aryix_branding_and_about.py` |
| **DEF-22** | `ci/cd` | Breaking Gitleaks-Action v2 License Requirement | 🔴 Critical | **FIXED** | `gitleaks/gitleaks-action@v2` introduced a breaking license paywall failing CI. Remediated by installing official open-source Gitleaks binary directly and coupling with `scripts/scan_secrets_and_pii.sh`. | `.github/workflows/ci.yml` |
| **DEF-23** | `export` | Schedule III PDF Export Header Overlap & Balance Sheet Roll-Forward Imbalance | 🔴 Critical | **FIXED** | Single-line PDF table header in `_render_schedule_iii_pdf` overlapped `"Note No."` and `"For period ended"`. Converted to structured 2-line header. Live ledger lacked roll-forward of prior year AOC-4 balance sheet anchors (deficit & director loan), creating ₹1,00,000 artificial imbalance. Implemented automatic permanent account roll-forward restoring zero mathematical drift. | `verify_balance_sheet_and_pdf.py` |
| **DEF-24** | `vault` | Form AOC-4 Vault Misclassification, SRN Truncation & Statutory Anchor Discrepancy | 🔴 Critical | **FIXED** | Uploaded Auditor Report Extract was misclassified as Form AOC-4 due to matching `"ATTACHED WITH FORM AOC-4"`, overwriting authentic Form AOC-4 and causing fallback to synthetic zero-sum values. Fixed classification regex with negative lookaheads, preserved full MCA V3 SRNs without truncation, enabled dual-bucket lookup (`b00k5-statutory` and `b00k5-vault`), added `other_current_liabilities` roll-forward, and synchronized statutory anchors with zero mathematical drift. | `tests/test_roc_compliance_and_esign.py::test_authentic_aoc4_schedule_iii_extraction_and_equilibrium` |


---

## 📑 Tab & FY Desynchronization Audit (TAB-FY-01 to TAB-FY-06)

| Audit ID | Route / Component | Defect Description | Severity | Status | Verification Proof |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **TAB-FY-01** | `/governance` | Switching FY in header desynchronized Board Meeting sub-tabs. | 🟡 Medium | **FIXED** | Wired reactive `useFiscalYear` hook to trigger automatic refetch across all child meeting rosters. |
| **TAB-FY-02** | `/yearbook` | Filings tab retained cached records from prior period after year switch. | 🟡 Medium | **FIXED** | Added FY cache key to SWR/fetcher invalidating stale annual return caches. |
| **TAB-FY-03** | `/reconciliation` | Bank statement month tabs remained selected when switching to a year with different statement dates. | 🟡 Medium | **FIXED** | Reset active month index to first available month in the newly selected financial year. |
| **TAB-FY-04** | `/vault` | Permanent documents (CIN, PAN, INC-20A) rendered with yearly selector tabs. | 🟡 Medium | **FIXED** | Split Vault into Permanent Anchors (single upload, no yearly tabs) and Annual Statutory Records (yearly tabs). |
| **TAB-FY-05** | `/vault` | Duplicate INC-20A entries appeared under both General Corporate and MCA Filings. | 🟡 Medium | **FIXED** | Deduplicated document category mappings to render INC-20A exclusively under Statutory Incorporation Anchors. |
| **TAB-FY-06** | `/invoices` | Item description box was too small for complex multi-line service contracts. | 🟢 Low | **FIXED** | Upgraded item description to expandable multi-line text area with dynamic row height. |

