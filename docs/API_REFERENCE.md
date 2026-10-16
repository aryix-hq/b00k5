# b00k5 REST API Reference Specification (OpenAPI 3.1)

## 1. Global Request & Authentication Architecture

* **Base URL:** `http://localhost:8000/api/v1`
* **Content Type:** `application/json` (except document uploads which use `multipart/form-data`)
* **Interactive Documentation (Swagger):** `http://localhost:8000/docs`
* **Machine-Readable OpenAPI Spec:** `http://localhost:8000/openapi.json`

### 1.1 Authentication & Multi-Tenant Headers

All protected endpoints require a valid JSON Web Token (JWT) in the HTTP `Authorization` header and support explicit tenant scoping:

| Header | Format | Description |
| :--- | :--- | :--- |
| `Authorization` | `Bearer <JWT_TOKEN>` | HS256-signed JWT carrying `sub` (User ID), `email`, and `tenant_id`. |
| `X-Tenant-ID` | `<UUID>` | Optional tenant override for multi-organization users. |

```bash
# Example Authenticated Request
curl -X GET http://localhost:8000/api/v1/compliance/dashboard \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6..." \
  -H "X-Tenant-ID: 11111111-1111-1111-1111-111111111111"
```

### 1.2 Rate Limiting Architecture

The authentication endpoints (`/auth/login`) enforce a **Leaky-Bucket Rate Limiter** backed by the Redis connection pool singleton:
* **Max Attempts:** 5 login requests per minute per IP / username key.
* **Exceeded Behavior:** Returns `HTTP 429 Too Many Requests` with a `Retry-After: <seconds>` response header.
* **Brute-Force Protection:** Automatically locks out suspect IPs after consecutive failures.

---

## 2. API Endpoints by Domain Router

### 2.1 Authentication Router (`/auth`)

#### `POST /api/v1/auth/login`
Authenticates credentials, enforces token-bucket rate limiting, and issues a JWT token.
* **Rate Limit:** 5 requests/min.
* **Request Body:**
  ```json
  {
    "email": "admin@acme.corp",
    "password": "Admin@12345"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user_id": "33333333-3333-3333-3333-333333333333",
    "email": "admin@acme.corp",
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "role": "owner"
  }
  ```
* **Error Response (429 Too Many Requests):**
  ```json
  {
    "detail": "Rate limit exceeded. Maximum 5 login attempts per minute allowed.",
    "retry_after_seconds": 48
  }
  ```

#### `POST /api/v1/auth/google/login`
1-click Google OAuth / Gmail sign-in with automatic user provisioning.
* **Request Body:**
  ```json
  {
    "email": "founder@yourstartup.com",
    "name": "Vikram Sharma",
    "google_id": "1049281729481928"
  }
  ```

#### `POST /api/v1/auth/refresh`
Refreshes an active session token prior to expiry.

---

### 2.2 General Ledger Router (`/ledger`)

#### `GET /api/v1/ledger/accounts`
Retrieves the Schedule III Division I Chart of Accounts for the authenticated tenant.
* **Response (200 OK):**
  ```json
  [
    {
      "id": "a1111111-1111-1111-1111-111111111111",
      "code": "1001",
      "name": "Equity Share Capital",
      "classification": "EQUITY",
      "schedule_iii_head": "Share Capital",
      "current_balance": 100000.00
    },
    {
      "id": "a2222222-2222-2222-2222-222222222222",
      "code": "2105",
      "name": "Director Reimbursements Payable",
      "classification": "LIABILITY",
      "schedule_iii_head": "Other Current Liabilities",
      "current_balance": 301554.06
    }
  ]
  ```

#### `POST /api/v1/ledger/journal-entries`
Creates a double-entry voucher. Enforces $\sum \text{Debits} \equiv \sum \text{Credits}$.
* **Request Body:**
  ```json
  {
    "date": "2026-10-15",
    "entry_type": "STANDARD",
    "narration": "Founder seed working capital injection under Rule 2(1)(c)(viii)",
    "lines": [
      {
        "account_id": "3102-bank-account-uuid",
        "debit": 500000.00,
        "credit": 0.00,
        "narration": "HDFC Current Account receipt"
      },
      {
        "account_id": "2105-director-loan-uuid",
        "debit": 0.00,
        "credit": 500000.00,
        "narration": "Founder loan from personal funds"
      }
    ]
  }
  ```

#### `POST /api/v1/ledger/journal-entries/{id}/post`
Posts a draft voucher to the General Ledger. Engages the `enforce_journal_immutability` trigger.

#### `GET /api/v1/ledger/trial-balance`
Generates real-time Trial Balance verifying $\left\vert{}\sum \text{Dr} - \sum \text{Cr}\right\vert{} \equiv 0.00$.
* **Query Parameters:** `fiscal_year` (string), `as_of_date` (date).

#### `GET /api/v1/ledger/balance-sheet`
Generates Schedule III Non-Ind AS (Division I) Balance Sheet with automatic statutory rounding.
* **Query Parameters:** `as_of_date` (date), `rounding` (`auto` | `hundreds` | `lakhs` | `crores`).
* **Auto-Rounding Logic:** Evaluates turnover and automatically scales figures to `Rs. '00 (Nearest Hundreds)` for startups ($< ₹100\text{ Cr}$) per MCA Schedule III General Instructions Clause 4.

---

### 2.3 Invoices & Sales Router (`/invoices`)

#### `POST /api/v1/invoices`
Creates a GST-compliant tax invoice with automatic Place of Supply (POS) and auto-posts to the GL.
* **Request Body:**
  ```json
  {
    "customer_id": "contact-uuid",
    "invoice_number": "INV-2026-0042",
    "invoice_date": "2026-10-15",
    "due_date": "2026-11-14",
    "place_of_supply": "27",
    "items": [
      {
        "description": "Annual Enterprise SaaS Platform Subscription",
        "hsn_sac": "998313",
        "quantity": 1,
        "unit_price": 250000.00,
        "tax_rate": 18.0
      }
    ]
  }
  ```
* **Dynamic Place of Supply Evaluation:**
  * If customer state code (`27` MH) $\ne$ company state code (`29` KA): Evaluated as **Inter-State**. Applies **IGST 18%** (₹45,000.00). Total: ₹295,000.00.
  * If customer state code matches company: Evaluated as **Intra-State**. Applies **CGST 9%** + **SGST 9%**.

#### `GET /api/v1/invoices/contacts/search`
Typeahead combobox search for customer contacts with automated GSTIN state extraction.
* **Query Parameters:** `q` (string query).

---

### 2.4 Expenses & Bill OCR Router (`/expenses`)

#### `POST /api/v1/expenses/upload`
Uploads a scanned vendor bill or expense receipt (`multipart/form-data`) for asynchronous OCR.
* **Form Data:** `file` (PDF, PNG, JPEG).
* **Processing:** Celery `ocr_queue` extracts Vendor Name, Date, GSTIN, Line Items, and Total.

#### `POST /api/v1/expenses`
Records an approved expense voucher with director loan and Section 40A(3) checks.
* **Request Body:**
  ```json
  {
    "expense_date": "2026-10-15",
    "vendor_name": "Amazon Web Services India",
    "total_amount": 14500.00,
    "payment_mode": "DIRECTOR_PERSONAL",
    "is_director_loan": true,
    "dpt3_declaration_signed": true,
    "category": "Cloud Hosting & Infrastructure"
  }
  ```
* **Statutory Checks Executed:**
  * If `payment_mode == "PETTY_CASH"` and `total_amount > 10000.00`: Flags `sec40a3_violation = true` (Disallowance under Section 40A(3) of Income Tax Act).
  * If `is_director_loan == true`: Credits `Account 2105 (Director Reimbursements Payable)` and verifies Rule 2(1)(c)(viii) non-borrowed fund declaration.

---

### 2.5 Banking & 3-Tier Reconciliation Router (`/bank`)

#### `GET /api/v1/bank/statements`
Retrieves imported bank statements with multi-year fiscal year filtering.
* **Query Parameters:** `period_fy` (e.g., `FY 2026-27`, `LAST_5_YEARS`, or `ALL`).

#### `POST /api/v1/bank/statements/upload`
Uploads raw bank statement (PDF / CSV) into sovereign MinIO bucket and parses transaction lines.

#### `POST /api/v1/bank/statements/{id}/reconcile`
Executes the **3-Tier Reconciliation Cascade**:
* **Tier 1:** Deterministic exact UTR / Cheque reference match.
* **Tier 2:** Heuristic fuzzy match (exact amount, $[-2, +5]$ days date window, $>85\%$ narrative similarity).
* **Tier 3:** Routes unmatched records to `Account 2099 (Suspense)`.

---

### 2.6 Corporate Governance & Statutory Anchors (`/compliance`)

#### `GET /api/v1/compliance/dashboard`
Returns live countdowns and compounding penalty calculations for statutory MCA filings:
* `INC-20A` (Commencement of Business within 180 days).
* `DIR-3 KYC` (Annual Director KYC due 30 September; ₹5,000 late fee).
* `AOC-4` (Annual Financial Statements within 30 days of AGM; ₹100/day compounding fine).
* `MGT-7/7A` (Annual Return within 60 days of AGM; ₹100/day compounding fine).
* Section 173 Board Meeting interval watchdog (Max 120 days between consecutive meetings).

#### `GET /api/v1/compliance/fiscal-years`
Returns the status of all financial years (`active_operating`, `audit_closing_window`, `statutory_frozen`).

#### `POST /api/v1/compliance/statutory-anchors`
Ingests filed statutory returns (**MGT-7**, **AOC-4**, **ITR-6**) as certified sources of truth:
* **Request Body:**
  ```json
  {
    "fiscal_year": "FY 2025-26",
    "assessment_year": "AY 2026-27",
    "form_type": "AOC_4",
    "srn_or_ack_number": "F12345678",
    "filing_date": "2026-10-15",
    "schedule_iii_payload": {
      "share_capital": 100000.00,
      "reserves_and_surplus": -450000.00,
      "director_loans_2105": 301554.06
    }
  }
  ```
* **Effect:** Locks the anchor with SHA-256 integrity, establishes baseline opening balances for FY 2026-27, and auto-triggers statutory freezing of FY 2025-26.

---

### 2.7 Statutory Tax & GST Forecasting (`/compliance/tax`, `/compliance/gst`)

#### `GET /api/v1/compliance/tax/advance-tax-forecast`
Calculates mandatory quarterly Advance Tax installments and Section 234B/234C interest.
* **Query Parameters:** `fiscal_year` (string).
* **Response (200 OK):**
  ```json
  {
    "fiscal_year": "FY 2026-27",
    "assessment_year": "AY 2027-28",
    "tax_regime": "SECTION_115BAA",
    "effective_tax_rate": 25.168,
    "projected_annual_profit": 1200000.00,
    "gross_projected_tax": 302016.00,
    "tds_credits_claimed": 15000.00,
    "net_advance_tax_payable": 287016.00,
    "installments": [
      { "quarter": "Q1", "due_date": "2026-06-15", "pct": 15, "cumulative_due": 43052.40, "paid": 45000.00, "status": "COMPLIED" },
      { "quarter": "Q2", "due_date": "2026-09-15", "pct": 45, "cumulative_due": 129157.20, "paid": 130000.00, "status": "COMPLIED" },
      { "quarter": "Q3", "due_date": "2026-12-15", "pct": 75, "cumulative_due": 215262.00, "paid": 0.00, "status": "UPCOMING" },
      { "quarter": "Q4", "due_date": "2027-03-15", "pct": 100, "cumulative_due": 287016.00, "paid": 0.00, "status": "UPCOMING" }
    ],
    "interest_234c_penal": 0.00,
    "interest_234b_penal": 0.00
  }
  ```

#### `GET /api/v1/compliance/gst/forecast`
Forecasts quarterly, half-yearly, and annual GST liability applying Rule 88A ITC netting order.
* **Query Parameters:** `period_fy` (string), `frequency` (`monthly` | `quarterly`).

---

### 2.8 Document Vault & Auditor Dossier (`/vault`)

#### `GET /api/v1/vault/export-dossier`
Generates a complete, cryptographically verified Auditor Export Dossier (ZIP).
* **Query Parameters:** `fiscal_year` (string).
* **Package Contents:**
  1. `Schedule_III_Balance_Sheet.pdf` (Division I Non-Ind AS with Clause 4 auto-rounding).
  2. `Schedule_III_Profit_Loss.pdf`.
  3. `General_Ledger_Trial_Balance.xlsx`.
  4. `Statutory_Anchors_Verification.json`.
  5. `Bank_Reconciliation_Summary.pdf`.
  6. `manifest.sha256` (Cryptographic checksum of all dossier artifacts).

---

### 2.9 System Telemetry & SRE DR Drill (`/system`)

#### `POST /api/v1/system/dr-drill`
Executes the live 6-gate Disaster Recovery Drill verifying RTO SLA ($< 30\text{s}$) and zero ledger drift.
* **Response (200 OK):**
  ```json
  {
    "status": "PASS",
    "execution_time_seconds": 0.58,
    "gates_evaluated": 6,
    "gates_passed": 6,
    "source_ledger_balance": 74694900.38,
    "recovered_ledger_balance": 74694900.38,
    "ledger_drift": 0.00,
    "rto_sla_met": true
  }
  ```
