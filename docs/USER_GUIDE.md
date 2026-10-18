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
│ 9. Payroll & Compliance │ Salaried runs, Form 16, EPFO/ESIC/PT, 194C/194J Contractors │
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

---

### 2.10 Workflow 10: Processing Salaried Payroll & Filing Statutory Returns (EPFO, ESIC, PT, Form 16)
**Objective:** Execute monthly salaried payroll runs, auto-post two-legged double-entry vouchers (Accrual & Disbursement), generate EPFO ECR electronic files, ESIC returns, PT challan exports, and download statutory Form 16 Part B tax certificates.

1. Navigate to `/payroll` from the main navigation sidebar.
2. **Review Monthly Payroll Runs (Tab 1: "Run Payroll"):**
   * View all historical payroll runs with their respective pay periods, employee counts, total gross pay, deductions, and net disbursed amounts.
   * Check run status: `Draft` -> `Calculated` -> `Accrued (Leg 1)` -> `Disbursed (Leg 2)`.
3. **Execute a New Monthly Payroll Run:**
   * Click **Execute Salaried Payroll Run** in the header.
   * Select the target **Month** and **Year** (e.g., September 2026).
   * Confirm the calculation. The payroll engine automatically applies Indian statutory rules:
     * **Provident Fund (EPF):** Computes Employee Contribution (12% of Basic up to statutory ceiling ₹15,000, i.e., ₹1,800/mo cap unless voluntary PF) and Employer Contribution (12% split into 8.33% EPS and 3.67% EPF + 0.5% EDLI + 0.5% Admin).
     * **Employees' State Insurance (ESIC):** Auto-detected if Gross $\le$ ₹21,000/mo. Computes Employee Contribution (0.75% of Gross) and Employer Contribution (3.25% of Gross).
     * **Professional Tax (PT):** Applies state-specific slabs (e.g., Karnataka: ₹200/mo for gross $\ge$ ₹15,000; Maharashtra: ₹200/mo, ₹300 in Feb).
     * **TDS under Section 192:** Computes monthly withholding under the New Tax Regime (default Section 115BAC) or Old Regime based on employee declarations.
4. **Post Two-Legged General Ledger Vouchers:**
   * **Leg 1: Accrual Voucher:** Click **Post Leg 1 Accrual**. Automatically posts and cryptographically seals a balanced General Ledger voucher:
     * Debit: `Salaries & Wages (Code 4010)` (Gross Salary)
     * Debit: `Employer PF Contribution (Code 4011)`
     * Debit: `Employer ESIC Contribution (Code 4012)`
     * Credit: `Net Salaries Payable (Code 2050)`
     * Credit: `TDS Payable u/s 192 (Code 2060)`
     * Credit: `Provident Fund Payable (Code 2070)`
     * Credit: `ESIC Payable (Code 2071)`
     * Credit: `Professional Tax Payable (Code 2072)`
   * **Leg 2: Disbursement Voucher:** Click **Post Leg 2 Disbursement**. Enter bank payout reference / UTR number.
     * Debit: `Net Salaries Payable (Code 2050)`
     * Credit: `Bank Account (Code 1010)`
5. **Download Statutory Filing Return Files (Tab 3: "Statutory Filings"):**
   * **EPFO ECR Electronic File (`.txt`):** Click **Download ECR File**. Produces the official `#~#` delimited plain-text upload file containing UAN, Member Name, Gross Wages, EPF Wages, EPS Wages, EDLI Wages, EE Share, ER EPS Share, ER EPF Diff, and Non-Contributory Days (NCP). Upload directly to the EPFO Unified Portal without manual data entry.
   * **ESIC Monthly Contribution Spreadsheet (`.xlsx`):** Click **Download ESIC Sheet**. Generates the standardized Excel schedule with IP Numbers, Insured Person Names, Total Days Worked, Wages, and Employee Share for the ESIC Insurance Portal.
   * **Professional Tax (PT) Challan Reports:** Download state-wise PT monthly return schedules formatted for state commercial tax portals.
6. **Generate Form 16 Part B Certificates (Tab 4: "Tax & Form 16"):**
   * Select the employee and assessment year.
   * View the annualized tax computation card: Gross Salary, Section 10 exemptions, Section 16(ia) standard deduction (₹75,000 for FY 2026-27), Chapter VI-A deductions, Total Taxable Income, Rebate u/s 87A, Health & Education Cess (4%), and Total Tax Deducted.
   * Click **Download Form 16 Part B (PDF)** to produce a certified, printable Form 16 Part B PDF certificate with deductor/deductee identity grids and digital signature placeholder.

---

### 2.11 Workflow 11: Managing Contractors, Freelancers, Section 194C/194J TDS Withholding & Form 16A Certificates
**Objective:** Onboard external vendors, consultants, and independent freelancers, withhold statutory TDS under Section 194C or 194J (compliant with CBDT Circular 23/2017), auto-post two-legged accrual/payout vouchers, and generate certified Form 16A PDF tax deduction certificates.

1. Navigate to `/payroll` and switch to the **Contractors & Freelancers** tab (5th tab).
2. **Onboard Contractor or Professional (Contractor Directory):**
   * Click **Onboard Contractor / Freelancer**.
   * Fill out the onboarding form:
     * **Contractor Code:** Unique identifier (e.g., `CNT-001`).
     * **Legal Name:** Official business or individual name matching income tax records.
     * **Entity Type:** Select from `individual`, `huf`, `partnership`, `company`, or `llp`.
     * **PAN (Permanent Account Number):** 10-character PAN. If not provided, statutory higher rate withholding (20% u/s 206AA) applies.
     * **GSTIN (Optional):** 15-character GST identification number if registered.
     * **Default Statutory Section & Rate:**
       * `194C` (Contractors / Sub-contractors): **1%** for Individuals/HUF; **2%** for Companies/LLPs/Partnerships.
       * `194J(a)` (Technical Services / Royalty): **2%**.
       * `194J(b)` (Professional Services, Legal, Medical, Architectural): **10%**.
     * **Bank Details:** Account Number and IFSC Code for direct NEFT/RTGS disbursals.
   * Click **Save & Onboard**.
3. **Record Contractor Invoice / Payout Claim:**
   * Click **Record Payout Claim** in the contractor payouts section.
   * Select the onboarded contractor.
   * Enter the **Base Service Amount** (e.g., ₹1,00,000) and **GST Amount** (e.g., 18% = ₹18,000).
   * Enter the contractor's **Invoice Number** and **Invoice Date**.
   * **Live Statutory Breakdown Card:**
     * The system instantly calculates TDS strictly on the **Base Service Amount** (excluding GST), in accordance with **CBDT Circular 23/2017**.
     * *Example (194J Professional 10% on ₹1,00,000 + 18% GST):*
       * Base Service Amount: ₹1,00,000
       * GST Input (18%): ₹18,000
       * Total Invoice: ₹1,18,000
       * TDS Withheld (10% on ₹1,00,000): ₹10,000
       * **Net Payable to Contractor:** ₹1,08,000
   * Click **Save Contractor Payment**.
4. **Post Two-Legged General Ledger Vouchers:**
   * **Leg 1: Accrual Voucher:** On the payout row, click **Accrue (Leg 1)**.
     * Debit: `Contractor / Professional Fees (Account 4040 / 4020)` (Base Amount: ₹1,00,000)
     * Debit: `Input GST / Electronic Credit Ledger (Account 1030)` (GST: ₹18,000)
     * Credit: `TDS Payable u/s 194C / 194J (Account 2060 / 2061)` (TDS: ₹10,000)
     * Credit: `Trade Payables - Contractors (Account 2040)` (Net Payable: ₹1,08,000)
   * **Leg 2: Disbursement Voucher:** After releasing payment via net banking, click **Disburse (Leg 2)** and enter the bank payment UTR / reference number.
     * Debit: `Trade Payables - Contractors (Account 2040)` (₹1,08,000)
     * Credit: `Bank Account (Account 1010)` (₹1,08,000)
5. **Issue Certified Form 16A TDS Certificates:**
   * Under the **Contractor Directory** or next to any disbursed claim, click **Form 16A (PDF)**.
   * Select the target Quarter (e.g., `Q2`) and Financial Year (e.g., `2026-27`).
   * The platform compiles all payments and TDS deposits for that quarter and streams a certified **Form 16A PDF Certificate** (under Section 203 of the Income-tax Act, 1961):
     * Deductor identity & TAN/PAN header.
     * Deductee identity, PAN, and address.
     * Summary of payments credited and tax deducted at source.
     * Bank Challan / BSR Code / Challan Identification Number (CIN) details.
     * Statutory verification statement and digital signature block.
   * Download and issue the PDF directly to your contractor or freelancer.


---

### 2.12 Workflow 12: Generating Bank Corporate CMS Batch Payout Files (HDFC ENet, ICICI CMS, SBI CMP)
**Objective:** Eliminate manual per-beneficiary corporate netbanking entry by exporting standard offline Corporate Management System (CMS) bulk batch payout files for salaried payroll runs and contractor payouts.

1. **Salaried Monthly Run Batch Payouts:**
   * Navigate to `/payroll` and view the **Run Payroll** tab (or **Statutory Filings** tab).
   * Once a payroll run is finalized or disbursed, locate the **Bank CMS** export triggers:
     * **HDFC ENet (.csv):** Click **HDFC** or **Download HDFC ENet CSV**. Formatted with Transaction Type (`IFT`/`NEFT`/`RTGS`), Beneficiary Account, Amount, Beneficiary Name, IFSC Code, Debit Account, and Narration (`SALARY_YYYYMM`).
     * **ICICI CMS (.csv):** Click **ICICI** or **Download ICICI CMS CSV**. Formatted with Payment Indicator (`I`/`N`/`R`), Beneficiary Account, Amount, Beneficiary Name, IFSC, Debit Account, and Remarks.
     * **SBI CMP (.csv):** Click **SBI** or **Download SBI CMP CSV**. Formatted with Payment Mode (`OWN`/`NEFT`/`RTGS`), Beneficiary Account, Amount, Beneficiary Name, IFSC, Debit Account, and Remittance Info.
2. **Contractors & Freelancers Bulk Payouts:**
   * Switch to the **Contractors & Freelancers** tab.
   * Review the list of contractor payout claims with status `approved` or `disbursed`.
   * In the **Batch Payout** toolbar, select the bank format of your corporate account:
     * Click **HDFC ENet**, **ICICI CMS**, or **SBI CMP**.
     * The system gathers all approved payments, pulls contractor IFSC and account details, formats the file according to bank CMS protocol, and streams the batch file `HDFC_ENet_Contractors_YYYY-MM-DD.csv`.
3. **Upload to Corporate Netbanking:**
   * Log into your HDFC ENet, ICICI Corporate Internet Banking (CIB), or SBI Corporate Portal.
   * Go to **Bulk Upload / CMS Payouts** > **Upload File**.
   * Select the generated CSV and submit for corporate maker-checker authorization.
   * Once authorized by corporate signatories, all employees and contractors receive credited funds simultaneously with zero cloud GSP or proprietary payment gateway lock-in.

---

### 2.13 Workflow 13: Exporting Official GSTR-1 Portal-Ready JSON for Direct GSTN Upload
**Objective:** Generate official GSTN offline utility JSON returns directly from verified General Ledger vouchers for 1-click upload to `gst.gov.in` without cloud GSPs or intermediary fees.

1. Navigate to `/invoices`.
2. **Open GSTR-1 Export Modal:**
   * In the top-right header actions, click **Export GSTR-1 JSON** (accessible in both operational mode and statutory audit mode).
3. **Select Return Period:**
   * Select the target **Return Year** (e.g., `2026`).
   * Select the target **Return Month** (e.g., `October` / `10`).
   * Review the target filename: `GSTR1_<GSTIN>_<MMYYYY>.json`.
4. **Statutory Payload Synthesis:**
   * Click **Download GSTR-1 JSON**.
   * The platform aggregates all active, non-voided sales invoices and credit/debit notes for the selected period, categorizing them into official GSTN offline utility sections:
     * **B2B (Table 4):** Taxable outward supplies made to registered persons with recipient GSTIN, invoice date, IRN, reverse charge flag, and tax rate breakdowns.
     * **B2CL (Table 5):** Inter-state taxable outward supplies to unregistered persons where invoice value exceeds ₹2.5 Lakhs (or state threshold).
     * **B2CS (Table 7):** Intra-state and small inter-state supplies to unregistered consumers aggregated by POS and GST rate.
     * **CDNR (Table 9B):** Credit notes, debit notes, and refund vouchers issued to registered persons.
     * **EXP (Table 6A):** Direct zero-rated export supplies with or without payment of tax.
     * **HSN Summary (Table 12):** Mandatory HSN-wise summary of outward supplies with Description, UQC (`NOS`, `KGS`, `OTH`), Total Quantity, Taxable Value, Integrated Tax, Central Tax, and State Tax.
     * **Doc Issue Summary (Table 13):** Serial number range of invoices issued, cancelled, and net issued.
5. **Direct Portal Upload:**
   * Log into `https://www.gst.gov.in` with your company DSC or credentials.
   * Navigate to **Services > Returns > Returns Dashboard > Select FY & Period**.
   * Under **Details of outward supplies of goods or services (GSTR-1)**, click **Prepare Offline**.
   * Click **Choose File**, select the downloaded `GSTR1_<GSTIN>_<MMYYYY>.json`, and click **Upload**.
   * The GSTN portal processes the file and auto-populates all GSTR-1 tables instantly with zero validation errors.


---

### 2.12 Workflow 12: Generating Bank Corporate CMS Batch Payout Files (HDFC ENet, ICICI CMS, SBI CMP)
**Objective:** Eliminate manual per-beneficiary corporate netbanking entry by exporting standard offline Corporate Management System (CMS) bulk batch payout files for salaried payroll runs and contractor payouts.

1. **Salaried Monthly Run Batch Payouts:**
   * Navigate to `/payroll` and view the **Run Payroll** tab (or **Statutory Filings** tab).
   * Once a payroll run is finalized or disbursed, locate the **Bank CMS** export triggers:
     * **HDFC ENet (.csv):** Click **HDFC** or **Download HDFC ENet CSV**. Formatted with Transaction Type (`IFT`/`NEFT`/`RTGS`), Beneficiary Account, Amount, Beneficiary Name, IFSC Code, Debit Account, and Narration (`SALARY_YYYYMM`).
     * **ICICI CMS (.csv):** Click **ICICI** or **Download ICICI CMS CSV**. Formatted with Payment Indicator (`I`/`N`/`R`), Beneficiary Account, Amount, Beneficiary Name, IFSC, Debit Account, and Remarks.
     * **SBI CMP (.csv):** Click **SBI** or **Download SBI CMP CSV**. Formatted with Payment Mode (`OWN`/`NEFT`/`RTGS`), Beneficiary Account, Amount, Beneficiary Name, IFSC, Debit Account, and Remittance Info.
2. **Contractors & Freelancers Bulk Payouts:**
   * Switch to the **Contractors & Freelancers** tab.
   * Review the list of contractor payout claims with status `approved` or `disbursed`.
   * In the **Batch Payout** toolbar, select the bank format of your corporate account:
     * Click **HDFC ENet**, **ICICI CMS**, or **SBI CMP**.
     * The system gathers all approved payments, pulls contractor IFSC and account details, formats the file according to bank CMS protocol, and streams the batch file `HDFC_ENet_Contractors_YYYY-MM-DD.csv`.
3. **Upload to Corporate Netbanking:**
   * Log into your HDFC ENet, ICICI Corporate Internet Banking (CIB), or SBI Corporate Portal.
   * Go to **Bulk Upload / CMS Payouts** > **Upload File**.
   * Select the generated CSV and submit for corporate maker-checker authorization.
   * Once authorized by corporate signatories, all employees and contractors receive credited funds simultaneously with zero cloud GSP or proprietary payment gateway lock-in.

---

### 2.13 Workflow 13: Exporting Official GSTR-1 Portal-Ready JSON for Direct GSTN Upload
**Objective:** Generate official GSTN offline utility JSON returns directly from verified General Ledger vouchers for 1-click upload to `gst.gov.in` without cloud GSPs or intermediary fees.

1. Navigate to `/invoices`.
2. **Open GSTR-1 Export Modal:**
   * In the top-right header actions, click **Export GSTR-1 JSON** (accessible in both operational mode and statutory audit mode).
3. **Select Return Period:**
   * Select the target **Return Year** (e.g., `2026`).
   * Select the target **Return Month** (e.g., `October` / `10`).
   * Review the target filename: `GSTR1_<GSTIN>_<MMYYYY>.json`.
4. **Statutory Payload Synthesis:**
   * Click **Download GSTR-1 JSON**.
   * The platform aggregates all active, non-voided sales invoices and credit/debit notes for the selected period, categorizing them into official GSTN offline utility sections:
     * **B2B (Table 4):** Taxable outward supplies made to registered persons with recipient GSTIN, invoice date, IRN, reverse charge flag, and tax rate breakdowns.
     * **B2CL (Table 5):** Inter-state taxable outward supplies to unregistered persons where invoice value exceeds ₹2.5 Lakhs (or state threshold).
     * **B2CS (Table 7):** Intra-state and small inter-state supplies to unregistered consumers aggregated by POS and GST rate.
     * **CDNR (Table 9B):** Credit notes, debit notes, and refund vouchers issued to registered persons.
     * **EXP (Table 6A):** Direct zero-rated export supplies with or without payment of tax.
     * **HSN Summary (Table 12):** Mandatory HSN-wise summary of outward supplies with Description, UQC (`NOS`, `KGS`, `OTH`), Total Quantity, Taxable Value, Integrated Tax, Central Tax, and State Tax.
     * **Doc Issue Summary (Table 13):** Serial number range of invoices issued, cancelled, and net issued.
5. **Direct Portal Upload:**
   * Log into `https://www.gst.gov.in` with your company DSC or credentials.
   * Navigate to **Services > Returns > Returns Dashboard > Select FY & Period**.
   * Under **Details of outward supplies of goods or services (GSTR-1)**, click **Prepare Offline**.
   * Click **Choose File**, select the downloaded `GSTR1_<GSTIN>_<MMYYYY>.json`, and click **Upload**.
   * The GSTN portal processes the file and auto-populates all GSTR-1 tables instantly with zero validation errors.

