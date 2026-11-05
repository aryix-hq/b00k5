# Statutory Bank Reconciliation & Unbilled Expense Governance Manual

**Jurisdiction:** India (Companies Act 2013, Income-tax Act 1961, CARO 2020, and GST Acts)  
**System Engine:** b00k5 Financial OS  
**Status:** Canonical Statutory Policy & Engineering Specification  

---

## 1. Executive Summary & Statutory Framework

Bank Reconciliation Statements (BRS) are not merely internal cash tracking tools; under **Section 128 of the Companies Act, 2013**, **Section 37 of the Income-tax Act, 1961**, and **CARO 2020 (Order 3(vii) & 3(ix))**, every debit or credit flowing through the corporate current account must reconcile with double-entry general ledger records supported by verifiable audit evidence.

This manual documents the mandatory statutory rules for handling:
1. **Direct Bank Debits** (Bank charges, debit card annual fees, processing charges).
2. **Unbilled Current Account Debits** (Business operational expenses lacking vendor tax invoices).
3. **Vendor & Contractor Advances** (Payments made prior to receiving a tax invoice).
4. **Director / Founder Personal Swipes** (Commingled personal transactions).
5. **Suspense Account Clearance Invariant** (Account Code `2099`).

---

## 2. Rule 1: Direct Bank Debits & Debit Card Annual Fees

### Statutory Basis:
- **Income-tax Act, 1961 — Section 37(1):** Bank charges, card annual maintenance charges (AMC), processing fees, and forex markups incurred on a corporate current account are 100% tax-deductible financial expenses incurred wholly and exclusively for business purposes.
- **Companies Act, 2013 — Schedule III Division I:** Must be disclosed in the Statement of Profit and Loss under **Note 18: Finance Costs & Bank Charges**.
- **Documentary Evidence:** **No third-party vendor invoice is legally required.** The bank statement entry accompanied by the bank's automated electronic debit advice serves as primary statutory evidence.

### Accounting Mechanics:
- **Debit:** Account Code `4030` (*Finance Costs & Bank Charges*)
- **Credit:** Account Code `1010` (*Operating Bank Account*)
- **GST Consideration:** Banks issue consolidated monthly GST tax invoices available via net banking. If claiming Input Tax Credit (ITC), record the bank's GSTIN; otherwise, expense the gross amount (fee + 18% GST) directly to `4030`.

### b00k5 Invariant:
The automated reconciliation engine pattern-matches keywords (`DEBIT CARD`, `AMC`, `ANNUAL FEE`, `CHARGES`, `FEE`, `ISSUANCE`) and auto-posts a balanced journal entry with **100% Tier-1 Exact Match confidence**.

---

## 3. Rule 2: Unbilled Business Debits & Self-Vouching Protocols

### Statutory Basis:
- **Section 128(1), Companies Act, 2013:** Books of account must give a true and fair view of the state of affairs on an accrual basis.
- **Section 37(1), Income-tax Act, 1961:** An expense is allowable only if it has a direct business nexus.
- **Section 40A(3), Income-tax Act, 1961:** Any expenditure exceeding ₹10,000 paid in cash in a single day is disallowed. Payments executed through the current account (electronic banking / UPI / card) are immune to Section 40A(3) cash disallowance.

### The Self-Vouching Criteria:
When a merchant does not provide a formal GST invoice (e.g., local transit, urgent stationery, client refreshments, minor tech tools), the company must maintain an **Internal Payment / Self-Voucher**.

The audit record **MUST** include:
1. **Transaction Reference / UTR:** Extracted directly from bank statement.
2. **Payee Name / UPI Handle:** Counterparty identification.
3. **Business Purpose & Nexus:** Clear, factual justification (e.g., *"Client pitch refreshments at meeting"*, *"Urgent HDMI adapter for boardroom display"*).
4. **Director / Owner Verification:** Approval signature or authenticated b00k5 login context.

### Account Code Selection:
* `4010` — Direct Operations / Freelancer Vouchers
* `4020` — Office Supplies & Consumables
* `4050` — Travel & Client Conveyance
* `4080` — Software & Digital Subscriptions
* `4090` — Miscellaneous Business Operating Expenses

---

## 4. Rule 3: Vendor Advances (Bill Awaited)

### Statutory Invariant:
If payment was made to a vendor, contractor, or service provider but the invoice is pending delivery, **do NOT charge the transaction directly to Profit & Loss**. 
Booking unbilled vendor disbursements to P&L prematurely violates matching principles and triggers statutory auditor objections under CARO 2020.

### Accounting Mechanics:
- **Debit:** Account Code `1030` (*Prepaid Expenses & Vendor Advances*) or `1050` (*Loans & Advances*) — Current Asset
- **Credit:** Account Code `1010` (*Operating Bank Account*)
- **Subsequent Clearance:** Upon receiving the vendor's tax invoice, create the vendor bill (which credits Accounts Payable) and post a contra settlement clearing `1030`.

---

## 5. Rule 4: Director Personal Swipe Segregation

### Statutory Prohibition:
- **Companies Act, 2013 — Section 185:** Restricts loans/advances to directors without special resolution.
- **Income-tax Act, 1961 — Section 2(22)(e):** Commingled personal expenses paid by an entity with accumulated profits can be recharacterized by tax authorities as **Deemed Dividends**, attracting penal taxation and disqualification of deduction.

### Mandatory Treatment:
Personal transactions must **never** be booked as business operating expenses.
- **Debit:** Account Code `1040` (*Loans & Advances to Directors*) or `2040` (*Director Current Account*)
- **Credit:** Account Code `1010` (*Operating Bank Account*)
- **Resolution:** The director must remit the exact amount back from their personal bank account to the corporate current account. Upon receiving the refund, reconcile the credit against `1040` to return the asset balance to zero.

---

## 6. Rule 5: Schedule III Suspense Account Invariant (Code 2099)

### The Holding Rule:
If a transaction cannot be identified during month-end close:
1. It is temporarily routed to **`2099 - Schedule III Suspense Account`**.
2. This ensures the Bank Reconciliation Statement (BRS) reconciles mathematically without delaying financial close.
3. **CARO 2020 Invariant:** No balance may remain in Account `2099` at statutory fiscal year-end (March 31). All suspense entries must be allocated to their true asset, liability, or expense codes before auditor sign-off.

---

## 7. Audit Justification & Narration Templates

| Transaction Type | Target Account Code | Schedule III Line Item | Statutory Narration Template |
| :--- | :--- | :--- | :--- |
| **Debit Card AMC / Fee** | `4030` | Note 18: Finance Costs | `Debit card annual fee for corporate account as per bank statement advice.` |
| **SMS / Minimum Balance Fee** | `4030` | Note 18: Finance Costs | `Bank maintenance & notification fee debited as per bank debit advice.` |
| **Self-Vouched Minor Expense** | `4090` / `4020` | Note 19: Other Expenses | `Business expense to [Payee] via UTR [Ref]. Third-party bill unavailable; self-vouched business operational expense.` |
| **Vendor Advance (Bill Pending)** | `1030` | Note 9: Short-Term Loans & Advances | `Advance payment to [Vendor] for [Services] via UTR [Ref]. Tax invoice pending receipt.` |
| **Director Personal Debit** | `1040` | Note 9: Due from Directors | `Personal transaction debited from current account. Charged to Director Current Account pending refund.` |
| **Unidentified Investigation** | `2099` | Note 7: Other Current Liabilities (Suspense) | `Unidentified debit routed to Suspense Account Code 2099 pending investigation.` |

---

## 8. Reconcile All Feature: Current Design vs. Statutory Justification Gate

### Current Design:
- Clicking **"Reconcile All"** (`POST /api/v1/reconciliation/reconcile-all`) performs an automated bulk sweep.
- Matches all Tier-1 exact invoices, contractor payments, and pattern-matched bank charges.
- Any unbilled or unmatched debit is automatically routed into **Tier-3 Suspense Account (`2099`)** without pausing for user input.

### Target Enhanced Design: "Statutory Justification & Classification Gate"
To eliminate post-sweep manual searching, clicking **"Reconcile All"** should:
1. Run the Tier-1 exact auto-match first.
2. If any unbilled debits remain, pause and trigger an interactive **Statutory Justification Modal**:
   - Presents a card/row for each unbilled debit with amount, date, and UTR.
   - Offers 1-click classification: `[Bank Fee 4030]`, `[Business Expense 4090]`, `[Vendor Advance 1030]`, `[Director Due 1040]`, or `[Keep in Suspense 2099]`.
   - Pre-fills statutory narration text.
   - Batch-posts all reconciled entries to the general ledger in one click.

