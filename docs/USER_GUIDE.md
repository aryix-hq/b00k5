# b00k5 End-User Operations Manual & Workflow Guide

## 1. Introduction & UI Navigation

**b00k5** is structured around seven primary operational workbenches accessible from the main navigation sidebar:

```
┌────────────────────────────────────────────────────────┐
│                      b00k5 Workbenches                 │
├─────────────────────────┬──────────────────────────────┤
│ 1. Dashboard (Radar)    │ Overview of cash & MCA fines │
│ 2. Invoices & Sales     │ Quote-to-Cash & GST POS      │
│ 3. Expenses & Claims    │ Procure-to-Pay & Founder GL  │
│ 4. Bank Reconciliation  │ 3-Tier Zero-Drift Matcher    │
│ 5. Corporate Governance │ Board Minutes & Hardware DSC │
│ 6. Legal Vault          │ Encrypted S3 Document Locker │
│ 7. Team & Access (IAM)  │ RBAC Roles & CA Audit Access │
└─────────────────────────┴──────────────────────────────┘
```

---

## 2. Step-by-Step Task Workflows

### 2.1 Workflow 1: Initial Corporate Setup & CIN Ingestion
**Objective:** Initialize a legal entity, configure MCA registration numbers, and provision the Schedule III Chart of Accounts.

1. Navigate to `http://localhost:3000/setup`.
2. **Step 1 - Organization Identification:**
   * Enter your 21-digit **Corporate Identity Number (CIN)** (e.g., `U72900KA2026PTC123456`).
   * The platform decodes company type (PTC), state code (`29` - Karnataka), and incorporation year (`2026`).
   * Enter your **Company Legal Name** exactly as printed on the MCA Certificate of Incorporation (COI).
   * Enter your 15-character **GSTIN** and 10-character **PAN**.
   * Specify the **Registered Office Address**.
3. **Step 2 - Administrator Credentials:**
   * Provide the Founder / Managing Director's email and master passphrase.
4. **Step 3 - Automated Ledger Provisioning:**
   * Click **Initialize Startup Workspace**.
   * *Expected System Action:* The backend validates checksums, provisions the multi-tenant database boundary, seeds the 21-account Schedule III Chart of Accounts, and redirects to `/dashboard`.

---

### 2.2 Workflow 2: Issuing GST Tax Invoices
**Objective:** Issue a compliant tax invoice with automatic Place of Supply (POS) and general ledger posting.

1. Navigate to `/invoices` and click **New Tax Invoice** (`/invoices/new`).
2. **Select or Create Customer:**
   * Choose an existing customer from the dropdown or click **Add New Contact**.
   * Enter the customer's legal trade name and 15-digit GSTIN.
   * *Dynamic Detection:* The platform inspects the first 2 digits of the customer's GSTIN to establish their State Code.
3. **Place of Supply (POS) Determination:**
   * If customer State Code matches your company's State Code (e.g. both `29`):
     * The invoice is marked **Intra-State**.
     * Applicable Taxes: **CGST (9%) + SGST (9%)**.
   * If customer State Code differs (e.g. `29` KA vs `27` MH):
     * The invoice is marked **Inter-State**.
     * Applicable Taxes: **IGST (18%)**.
4. **Add Invoice Items:**
   * Enter description, SAC/HSN code (e.g., `998313` for Software Platform Services), quantity, and unit rate in INR.
5. **Issue & Post:**
   * Click **Issue Invoice**.
   * *Expected System Action:* Generates sequential invoice number (`INV-2026-001`), renders downloadable PDF, and posts atomic journal voucher:
     * `DR Accounts Receivable (1020): ₹1,18,000`
     * `CR SaaS Revenue (3010): ₹1,00,000`
     * `CR Output CGST (2050): ₹9,000`
     * `CR Output SGST (2051): ₹9,000`

---

### 2.3 Workflow 3: Logging Expenses & Founder Personal Claims
**Objective:** Record operational vendor expenses, analyze receipt PDFs via OCR, and track founder out-of-pocket claims.

1. Navigate to `/expenses`.
2. Click **Add Expense**.
3. **Upload Receipt / Bill:**
   * Drag-and-drop receipt image or vendor bill PDF.
   * Click **Analyze with Smart OCR**.
   * *AI/OCR Action:* Tesseract/pdfplumber parses merchant name, vendor GSTIN, invoice date, base amount, and GST.
4. **Select Expense Category:**
   * Choose standard classification:
     * *Cloud Hosting (4010)* (AWS, Google Cloud, DigitalOcean)
     * *Legal & Professional Fees (5010)* (CA, Lawyer, Company Secretary)
     * *Office Rent & Co-Working (5020)*
     * *Hardware & Tools (1050)*
5. **Founder Payment Checkbox (`Paid Personally`):**
   * If the founder paid from their personal bank account / credit card, toggle **"Paid Personally by Founder / Director"**.
   * *Statutory Rule:* The platform assigns the liability to `Director Reimbursements Payable (Code 2105)`.
   * *Section 40A(3) Check:* If cash payment exceeds ₹10,000, an amber warning displays alerting you of Income Tax disallowance risks.
6. Click **Save & Post Expense**.
7. **Settling Founder Reimbursements:**
   * When the company reimburses the founder via NEFT/IMPS:
   * Click **Settle Reimbursement**.
   * Enter transaction reference (UTR) and payment date.
   * *Ledger Action:* Automatically posts:
     * `DR Director Reimbursements Payable (2105): ₹X`
     * `CR Bank Current Account (1010): ₹X`

---

### 2.4 Workflow 4: Bank Statement Ingestion & 3-Tier Reconciliation
**Objective:** Ingest monthly bank statements and reconcile all bank lines with zero discrepancy.

1. Navigate to `/reconciliation`.
2. Select your bank account from the dropdown (e.g., `HDFC Bank - Current Account`).
3. Click **Upload Bank Statement** and select your statement file (PDF or CSV).
4. Review extracted transactions in the Statement Workbench.
5. Click **Reconcile Statement**:
   * **Tier 1 (Deterministic):** Automatically matches lines having identical UTR or Cheque Numbers with general ledger vouchers.
   * **Tier 2 (Heuristic):** Matches lines within $[-2, +5]$ days having identical amounts and similar counterparty names ($> 85\%$ score).
   * **Special Account Generator:** Automatically posts Bank Charges (`Code 4030`) and FD Interest (`Code 3030`).
   * **Tier 3 (Suspense):** Any unidentified remaining inflow/outflow is routed to `Bank Reconciliation Suspense (Code 2099)`.
6. Inspect the summary indicator to verify `Status: Reconciled` and `Discrepancy: ₹0.00`.

---

### 2.5 Workflow 5: Corporate Governance & Hardware DSC Signing
**Objective:** Assemble MCA-compliant Board Meeting Minutes and cryptographically sign them using a physical Class-3 USB Token.

1. Navigate to `/governance`.
2. **Review Statutory Radar:**
   * Verify the interval counter for Section 173 (maximum 120 days between consecutive Board Meetings).
   * Verify Form INC-20A status (must display `✓ Filed / Completed`).
3. **Assemble Board Meeting Minutes:**
   * Select template: **Board Meeting Minutes (SS-1)**.
   * Confirm Meeting Number (e.g., `BM/2026-27/01`), Date, Time, and Venue.
   * Mark Directors present.
   * Click **Generate Minutes Document**.
   * The platform renders official letterhead minutes with SHA-256 hash.
4. **Cryptographic Hardware Signing:**
   * Ensure your HyperPKI HYP2003 / ePass2003 USB token is inserted into your computer.
   * Ensure local bridge is running (`cd bridge && bash run_bridge.sh`).
   * Enter your 6-digit **Token User PIN** in the signing modal.
   * Click **Sign with Hardware Token**.
   * *Action:* Bridge communicates via PKCS#11 to compute RSA signature on-chip.
   * The signed minutes are locked with a verifiable PAdES digital signature seal.

---

### 2.6 Workflow 6: Managing Legal Document Locker & Auditor Pack Export
**Objective:** Store statutory corporate licenses and export encrypted packs for external Chartered Accountants.

1. Navigate to `/vault`.
2. **Upload Documents into Designated Categories:**
   * *Corporate Legal:* Certificate of Incorporation, MOA, AOA, INC-20A filing receipt.
   * *Tax Registrations:* PAN Card, TAN Allotment Letter, GST REG-06 Certificate.
   * *Statutory Filings:* Form AOC-4, MGT-7, DPT-3.
3. Every document receives an immediate SHA-256 fingerprint displayed on screen.
4. **Export for Statutory Auditor:**
   * Click **Export Auditor Compliance Pack**.
   * The system compiles a structured ZIP archive containing all verified PDFs, ledger exports, and a `SHA256_CHECKSUMS.txt` manifest.
   * Transmit the ZIP archive directly to your CA firm.
