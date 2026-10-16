# b00k5 End-User Operations Manual & Workflow Guide

## 1. Introduction & Workbench Overview

**b00k5** is structured around eight dedicated operational workbenches accessible from the main navigation sidebar:

```
┌────────────────────────────────────────────────────────┐
│                      b00k5 Workbenches                 │
├─────────────────────────┬──────────────────────────────┤
│ 1. Dashboard (Radar)    │ Cash runway, MCA fine countdown & tax forecast │
│ 2. Invoices & Sales     │ Quote-to-Cash, customer directory & GST POS   │
│ 3. Expenses & Claims    │ Bill OCR, founder loan claims & Sec 40A(3)   │
│ 4. Bank Reconciliation  │ Multi-year (5 FY) 3-tier zero-drift matcher  │
│ 5. Corporate Governance │ Board Minutes, 120-day limit & hardware DSC  │
│ 6. Statutory Filings    │ Baseline anchors & 3-stage FY closing        │
│ 7. Tax & GST Forecast   │ Advance Tax Sec 234B/C & Rule 88A GST runway │
│ 8. Legal Vault          │ Encrypted S3 repository & Auditor ZIP dossier│
└─────────────────────────┴──────────────────────────────┘
```

---

## 2. Step-by-Step Task Workflows

### 2.1 Workflow 1: Initial Corporate Setup & Registration
**Objective:** Initialize an Indian legal entity, validate registration checksums, and auto-provision the Schedule III Chart of Accounts.

1. Navigate to `http://localhost:3000/setup`.
2. **Organization Identification:**
   * Enter your 21-character **Corporate Identity Number (CIN)** (e.g., `U72900KA2026PTC123456`).
   * Enter your 15-character **GSTIN** and 10-character **PAN**.
   * Enter your **Company Legal Name** exactly as printed on the Certificate of Incorporation (COI).
   * Specify the **Registered Office Address**.
3. **Founder / Director Master Account:**
   * Enter the Managing Director's official email address and master passphrase.
4. **Automated Provisioning:**
   * Click **Initialize Startup Workspace**. The system validates checksums, configures multi-tenant Row-Level Security, seeds the Schedule III Chart of Accounts, and redirects to `/dashboard`.

---

### 2.2 Workflow 2: Generating GST Tax Invoices with Dynamic POS
**Objective:** Issue a compliant tax invoice with automatic Place of Supply (POS) detection and immediate General Ledger posting.

1. Navigate to `/invoices` and click **New Tax Invoice** (`/invoices/new`).
2. **Select or Create Customer:**
   * Use the customer typeahead combobox to search existing contacts or type a new customer name.
   * Enter the customer's 15-digit GSTIN.
   * *Dynamic Place of Supply (POS) Detection:* The first 2 digits of the GSTIN (e.g., `27` for Maharashtra, `29` for Karnataka) automatically determine whether the transaction is Inter-State or Intra-State:
     * **Intra-State (Same State):** Applies **CGST (9%) + SGST (9%)**.
     * **Inter-State (Different State):** Applies **IGST (18%)**.
3. **Add Line Items:**
   * Enter item description, SAC/HSN code (e.g., `998313` for Software Platform Services), quantity, and unit rate in INR.
4. **Issue & Post:**
   * Click **Issue Tax Invoice**.
   * *Automated Accounting:* The invoice is sealed, and a balanced voucher is auto-posted to the General Ledger:
     * Debit: `Trade Receivables (Code 3101)` (Total Invoice Amount)
     * Credit: `Domestic SaaS Revenue (Code 4001)` (Taxable Subtotal)
     * Credit: `CGST/SGST/IGST Output Payable (Codes 2101/2102/2103)` (Tax Amounts)

---

### 2.3 Workflow 3: Ingesting Vendor Bills & Founder Personal Claims
**Objective:** Capture expenses via local OCR, handle founder personal payments, and enforce statutory tax disallowances.

1. Navigate to `/expenses` and click **Upload Bill** or drag-and-drop a receipt (PDF/PNG/JPEG).
2. **Local Tesseract OCR Ingestion:**
   * The platform processes the document locally without external cloud APIs.
   * Extracted metadata (Vendor Name, Invoice Date, GSTIN, Taxable Value, Tax) auto-populates the form.
3. **Payment Mode & Director Loans:**
   * Select **Payment Mode**:
     * `Company Bank Account`: Debited directly during bank reconciliation.
     * `Paid Personally by Director`: Automatically credited to **Account 2105 (Director Reimbursements Payable)**.
   * When paid by director, check the **Rule 2(1)(c)(viii) Non-Borrowed Funds Declaration** confirming funds originated from personal savings.
4. **Income Tax Section 40A(3) Watchdog:**
   * If `Payment Mode` is set to cash and the bill amount exceeds ₹10,000, the platform triggers a statutory alert warning of 100% tax disallowance under Section 40A(3).

---

### 2.4 Workflow 4: Bank Feeds & 3-Tier Reconciliation
**Objective:** Import bank statements across multiple fiscal years and achieve exact zero-drift reconciliation.

1. Navigate to `/bank`.
2. **Fiscal Year Period Filtering:**
   * In the top-right header, select your target reporting window:
     * `Current FY (FY 2026-27)`
     * `Last 5 Financial Years`
     * Specific historical year (e.g., `FY 2025-26`, `FY 2024-25`).
3. **Upload Statement:**
   * Click **Upload Statement** and select your bank PDF or CSV statement.
   * Authentic binary files are permanently preserved in the sovereign MinIO S3 bucket.
4. **Run 3-Tier Reconciliation:**
   * Click **Execute 3-Tier Matcher**:
     * **Tier 1 (Exact):** Automatically matches lines with identical UTR, Cheque, or IMPS numbers (100% confidence).
     * **Tier 2 (Fuzzy):** Highlights probable matches within a $[-2, +5]$ days date window and identical amounts for single-click review.
     * **Tier 3 (Suspense):** Unmatched line items are routed to **Account 2099 (Bank Suspense)** for maker-checker review.
5. **Verify Zero Ledger Drift:**
   * Confirm that the bank closing balance exactly matches the General Ledger balance ($\Delta = ₹0.00$).

---

### 2.5 Workflow 5: Statutory Baseline Calibration from Filed Returns
**Objective:** Ingest authentic filed MCA/ITR returns (**MGT-7**, **AOC-4**, **ITR-6**) as certified sources of truth.

1. Navigate to `/compliance` and select the **Statutory Anchors** tab.
2. Click **Ingest Filed Return**.
3. Select the return type (`AOC-4`, `MGT-7/7A`, or `ITR-6`), enter the MCA SRN or ITR Acknowledgement Number, and upload the authentic filed PDF/XML.
4. The system parses the document, computes its SHA-256 fingerprint, and stores it in the multi-year legal vault under `/vault/filings/{FY}/`.
5. **Opening Balance Calibration:**
   * Opening balances for the subsequent year are calibrated directly against filed figures.
   * If Account 2105 (Director Loans) shows ₹3,01,554.06 in the filed AOC-4, the system anchors this figure as the statutory baseline, resolving any discrepancy in DPT-3 disclosures.

---

### 2.6 Workflow 6: Managing the 3-Stage Fiscal Year Closing Lifecycle
**Objective:** Maintain audit flexibility during the statutory filing window while preventing unauthorized tampering once filed.

1. Navigate to `/compliance` -> **Fiscal Year Management**.
2. Understand the three operational stages:
   * **Stage 1: Active Operating Period (`active_operating`):** Running from 01/04/YYYY to 31/03/YYYY+1. Full day-to-day voucher creation and editing.
   * **Stage 2: Year-End Audit & Filing Window (`audit_closing_window`):** From 01/04/YYYY+1 through the statutory ITR/AOC-4 filing deadline (31/10/YYYY+1). The prior year books remain unlocked so founders and CAs can post year-end audit adjustments, book depreciation, and reconcile Form 26AS/AIS.
   * **Stage 3: Statutory Freeze (`statutory_frozen`):** When the filed ITR or AOC-4 is uploaded (or upon manual lock after 31/10), the prior FY transitions into permanent freeze. Kernel triggers reject all further modifications.

---

### 2.7 Workflow 7: Advance Tax & GST Cash Flow Forecasting
**Objective:** Monitor quarterly Advance Tax liabilities to avoid Section 234B/234C penal interest, and optimize GST cash outflow under Rule 88A.

1. Navigate to `/compliance` -> **Tax & GST Forecast**.
2. **Advance Tax Watchdog:**
   * Review projected annual taxable profit and applicable corporate tax regime (e.g., Section 115BAA at 25.168%).
   * Track the 4 statutory installments:
     * **15 June:** Cumulative 15%
     * **15 September:** Cumulative 45%
     * **15 December:** Cumulative 75%
     * **15 March:** Cumulative 100%
   * If actual tax challans paid fall short of statutory benchmarks, the system flags projected Section 234C (1% per month for deferral) and Section 234B (1% per month for default) interest.
3. **GST Cash Flow Runway:**
   * Review monthly/quarterly outward tax liability vs. available GSTR-2B Input Tax Credit.
   * The platform applies the **Rule 88A Netting Order** (IGST ITC utilized first against IGST, then CGST/SGST) to minimize immediate cash outflow through the Electronic Cash Ledger.

---

### 2.8 Workflow 8: Signing Board Minutes with Class-3 USB Token
**Objective:** Cryptographically seal Board Meeting Minutes using physical USB smart cards (HyperPKI HYP2003 / ePass2003) complying with ICSI Secretarial Standards (SS-1).

1. Navigate to `/governance` -> **Board Meetings**.
2. Select the meeting and click **Draft Minutes**. The system verifies that the interval since the previous meeting does not exceed the statutory 120-day limit under Section 173 of the Companies Act.
3. Plug the physical USB DSC token into your local workstation.
4. Ensure the local loopback bridge daemon is active (`http://127.0.0.1:28045`).
5. Click **Sign with USB DSC Token**. Enter your hardware PIN.
6. The bridge computes the cryptographic SHA-256 RSA/ECDSA signature on the physical token silicon and uploads the sealed PDF to the MinIO `b00k5-signed` bucket.

---

### 2.9 Workflow 9: Generating the Schedule III Auditor Export Dossier
**Objective:** Produce an audit-ready compliance package for your statutory CA.

1. Navigate to `/vault` -> **Auditor Export**.
2. Select the target financial year (e.g., `FY 2026-27`).
3. Click **Generate Schedule III Export Dossier**.
4. The system compiles:
   * **Schedule III Division I Balance Sheet:** Automatically formatted with MCA Clause 4 auto-rounding (Nearest Hundreds `Rs. '00`, Lakhs, or Crores based on turnover).
   * **Statement of Profit and Loss.**
   * **Comprehensive Trial Balance.**
   * **Statutory Anchors & Filing Reconciliation Report.**
   * **Cryptographic SHA-256 Manifest.**
5. Download the packaged ZIP file and transmit it directly to your statutory auditor.
