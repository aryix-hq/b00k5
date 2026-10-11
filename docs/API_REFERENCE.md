# b00k5 REST API Reference Specification (OpenAPI 3.1)

## 1. Global Request & Authentication Architecture

* **Base URL:** `http://localhost:8000/api/v1`
* **Content Type:** `application/json` (except file uploads which use `multipart/form-data`)
* **Interactive Documentation (Swagger):** `http://localhost:8000/docs`
* **Machine-Readable OpenAPI Spec:** `http://localhost:8000/openapi.json`

### 1.1 Authentication & Multi-Tenant Headers

All protected endpoints require a valid JSON Web Token (JWT) in the HTTP `Authorization` header and support explicit tenant scoping:

| Header | Format | Description |
| :--- | :--- | :--- |
| `Authorization` | `Bearer <JWT_TOKEN>` | HS256-signed JWT carrying `sub` (User ID), `email`, and `tenant_id`. |
| `X-Tenant-ID` | `<UUID>` | Optional tenant override. Used when a user belongs to multiple organizations. |

```bash
# Example Authenticated Request
curl -X GET http://localhost:8000/api/v1/compliance/dashboard \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6..." \
  -H "X-Tenant-ID: 11111111-1111-1111-1111-111111111111"
```

---

## 2. API Endpoints by Domain Router

### 2.1 Authentication Router (`/auth`)

#### `POST /api/v1/auth/login`
Authenticates user credentials and issues a JWT token.
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

#### `POST /api/v1/auth/google/login`
Seamless 1-click Google OAuth / Gmail sign-in. Dynamic user provisioning and tenant attachment.
* **Request Body:**
  ```json
  {
    "email": "founder@yourstartup.com",
    "name": "Vikram Sharma",
    "google_id": "1049281729481928"
  }
  ```
* **Response (200 OK):** Identical to standard login token response.

#### `GET /api/v1/auth/me`
Retrieves authenticated user profile and list of affiliated corporate tenants.
* **Response (200 OK):**
  ```json
  {
    "id": "33333333-3333-3333-3333-333333333333",
    "email": "admin@acme.corp",
    "first_name": "Vikram",
    "last_name": "Narayan",
    "is_active": true,
    "tenants": [
      {
        "id": "11111111-1111-1111-1111-111111111111",
        "legal_name": "Acme Technologies Private Limited",
        "cin": "U72900KA2026PTC123456",
        "gstin": "29AABCA1234F1Z5",
        "role": "owner"
      }
    ]
  }
  ```

---

### 2.2 First-Run Setup & Onboarding Router (`/setup`)

#### `POST /api/v1/setup/wizard`
Provisions an organization, parses CIN, creates initial administrator user, and seeds the 21-account Schedule III Chart of Accounts.
* **Request Body:**
  ```json
  {
    "company_name": "Acme Technologies Private Limited",
    "cin": "U72900KA2026PTC123456",
    "gstin": "29AABCA1234F1Z5",
    "pan": "AABCA1234F",
    "state_code": "29",
    "registered_office": "100 Feet Road, Indiranagar, Bengaluru, KA 560038",
    "admin_email": "admin@acme.corp",
    "admin_password": "Admin@12345"
  }
  ```

#### `GET /api/v1/setup/company-profile`
Fetches corporate metadata, registration numbers, and letterhead assets.

#### `POST /api/v1/setup/upload-logo`
Accepts `multipart/form-data` containing corporate brand logo, scales it for letterhead rendering, and stores in MinIO vault.

---

### 2.3 Invoicing & GST Engine Router (`/invoices`)

#### `GET /api/v1/invoices/`
Lists all customer invoices with optional filtering by status (`draft`, `sent`, `paid`, `overdue`).

#### `POST /api/v1/invoices/`
Generates a Tax Invoice, validates GSTIN with Modulus-36 checksum, evaluates Place of Supply (POS) for IGST vs CGST/SGST, and automatically commits a balanced double-entry voucher to the General Ledger.
* **Request Body:**
  ```json
  {
    "contact_id": "c1111111-1111-1111-1111-111111111111",
    "type": "tax_invoice",
    "issue_date": "2026-05-15",
    "due_date": "2026-05-30",
    "place_of_supply": "29",
    "items": [
      {
        "description": "Enterprise SaaS Platform Subscription (Annual)",
        "hsn_sac_code": "998313",
        "quantity": 1.0,
        "unit_price": 100000.00,
        "tax_rate_percent": 18.00
      }
    ]
  }
  ```
* **Response (201 Created):**
  ```json
  {
    "id": "e819b2ca-...",
    "invoice_number": "INV-2026-001",
    "subtotal": "100000.00",
    "cgst_total": "9000.00",
    "sgst_total": "9000.00",
    "igst_total": "0.00",
    "grand_total": "118000.00",
    "is_interstate": false,
    "journal_entry_id": "jv-9281-..."
  }
  ```

#### `GET /api/v1/invoices/hsn-master`
Returns standard Indian HSN/SAC master codes for IT services, software consulting, legal counsel, and hardware.

---

### 2.4 General Ledger & Financial Reporting Router (`/ledger`)

#### `GET /api/v1/ledger/trial-balance`
Computes real-time opening, debit, credit, and closing balances for every leaf account in the Chart of Accounts. Asserts $\sum \text{Debits} \equiv \sum \text{Credits}$.
* **Query Parameters:** `as_of_date` (YYYY-MM-DD)
* **Response (200 OK):**
  ```json
  {
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "as_of_date": "2026-10-03",
    "items": [
      { "code": "1010", "name": "Bank Current Account", "debit": 150000.00, "credit": 0.00 },
      { "code": "1020", "name": "Trade Receivables", "debit": 118000.00, "credit": 0.00 },
      { "code": "2010", "name": "Share Capital", "debit": 0.00, "credit": 100000.00 },
      { "code": "3010", "name": "SaaS Revenue", "debit": 0.00, "credit": 100000.00 },
      { "code": "2050", "name": "Output CGST", "debit": 0.00, "credit": 9000.00 },
      { "code": "2051", "name": "Output SGST", "debit": 0.00, "credit": 9000.00 }
    ],
    "total_debits": 268000.00,
    "total_credits": 268000.00,
    "is_balanced": true
  }
  ```

#### `GET /api/v1/ledger/profit-and-loss`
Generates Schedule III Statement of Profit & Loss (Revenue from Operations, Other Income, Expenses, Tax, Net Profit).

#### `GET /api/v1/ledger/balance-sheet`
Generates Schedule III Balance Sheet (Equities & Liabilities vs Assets).

#### `POST /api/v1/ledger/year-end-close`
Executes an atomic fiscal year rollover:
1. Validates zero-drift ledger state.
2. Zeros nominal accounts (Codes 3000-5999).
3. Transfers Net Profit into Reserves & Surplus / Retained Earnings (`Code 2020`).
4. Locks previous fiscal period (`is_closed = true`).

---

### 2.5 Expenses & Founder Reimbursements Router (`/expenses`)

#### `POST /api/v1/expenses/`
Ingests a vendor bill or founder personal claim. Evaluates Section 40A(3) cash expense limits (> ₹10,000) and DPT-3 deemed deposit rules.
* **Request Body:**
  ```json
  {
    "merchant_name": "Google Cloud India Pvt Ltd",
    "merchant_gstin": "27AABCG1234F1Z1",
    "total_amount": 15420.00,
    "expense_date": "2026-05-12",
    "category": "cloud_hosting",
    "category_code": "4010",
    "payment_mode": "credit_card",
    "paid_personally": true,
    "director_payable_code": "2105"
  }
  ```

#### `POST /api/v1/expenses/scan-bill`
Uploads a receipt image/PDF via `multipart/form-data`. Analyzes invoice date, merchant name, GSTIN, and line item tax amounts.

#### `POST /api/v1/expenses/settle-reimbursement`
Posts a balancing journal voucher discharging the company's liability to the founder (`Debit 2105 Director Reimbursements | Credit 1010 Bank Current Account`).

#### `DELETE /api/v1/expenses/{id}`
Strikes off an expense voucher with compulsory audit trail justification (`?reason=...`). Marks record `is_struck_off = true` without modifying posted journal entries.

#### `GET /api/v1/expenses/export-auditor-package`
Generates a downloadable ZIP archive containing all expense records, receipt PDFs, and an Excel/CSV index for statutory auditors.

---

### 2.6 Bank Statements & 3-Tier Reconciliation Router (`/reconciliation`)

#### `POST /api/v1/reconciliation/upload-statement`
Accepts `multipart/form-data` containing bank statement (PDF, CSV, XLS). Parses transactions, detects bank format (HDFC, ICICI, SBI), and stores records.

#### `POST /api/v1/reconciliation/execute-reconciliation`
Executes 3-Tier matching algorithm for a specified statement ID.

#### `POST /api/v1/reconciliation/reconcile-all`
Runs 3-Tier reconciliation across all pending bank statements in the tenant's workspace. Auto-generates journal entries for bank charges (`Code 4030`), interest income (`Code 3030`), and FD transfers (`Code 1040`).

---

### 2.7 Document Locker Vault Router (`/vault`)

#### `POST /api/v1/vault/smart-ingest`
Accepts legal documents (COI, MOA, AOA, PAN, GST Certificate, INC-20A). Computes SHA-256 hash, extracts corporate registration data, and indexes in MinIO bucket `b00k5-vault`.

#### `GET /api/v1/vault/export-auditor-pack`
Generates a master compliance ZIP archive structured into:
* `01_Corporate_Legal/` (COI, MOA, AOA)
* `02_Tax_Registrations/` (PAN, GST REG-06)
* `03_Governance_Minutes/` (Signed Board Minutes)
* `04_Financial_Ledger/` (Trial Balance CSV, General Ledger)
* `SHA256_CHECKSUMS.txt` (Cryptographic verification manifest)

---

### 2.8 Statutory Compliance Watchdog Router (`/compliance`)

#### `GET /api/v1/compliance/dashboard`
Returns live statutory countdowns, overdue events, and accumulated MCA penalties (e.g. ₹100/day for delayed INC-20A or AOC-4).

#### `POST /api/v1/compliance/generate-document?doc_type=board_minutes`
Assembles official Board Meeting Minutes adhering to Secretarial Standard-1 (SS-1). Returns document metadata and SHA-256 hash for hardware DSC signing.

#### `GET /api/v1/compliance/statutory-documents-status`
Returns upload status, verification flags, and compliance health for all 5 mandatory corporate registrations.

---

### 2.9 Hardware Token DSC Signer Router (`/dsc`)

#### `GET /api/v1/dsc/status`
Queries the hardware signer status (via bridge on `http://127.0.0.1:28045`). Confirms USB token presence and PKCS#11 driver binding.

#### `POST /api/v1/dsc/submit-signature`
Submits signed cryptographic hash bytes, verifies the signature against director DIN, injects PAdES signature into the PDF, and logs an entry in `dsc_signature_audit`.

---

### 2.10 Storage & Cloud Sync Router (`/storage`)

#### `GET /api/v1/storage/gdrive-auth-url`
Generates Google OAuth2 authorization URL with offline access scope for automated Google Drive backups.

#### `POST /api/v1/storage/gdrive-connect-google`
Exchanges OAuth2 authorization code for long-lived refresh token and stores encrypted credentials.

#### `POST /api/v1/storage/gdrive-sync-all`
Dispatches background Celery job to synchronize MinIO vault files and PostgreSQL backups to the tenant's dedicated Google Drive folder.

---

### 2.11 Identity & Access Management Router (`/iam`)

#### `GET /api/v1/iam/users`
Lists all team members, assigned RBAC roles (`owner`, `admin`, `accountant`, `auditor_ca`), DINs, and active status.

#### `POST /api/v1/iam/users`
Invites a new team member or statutory auditor with designated permissions.

#### `DELETE /api/v1/iam/users/{id}`
Revokes user membership and terminates active session tokens.

---

### 2.12 System & Disaster Recovery Router (`/system`)

#### `GET /api/v1/system/health`
Returns system operational status, database connectivity, and engine version.

#### `GET /api/v1/system/fiscal-calendar`
Returns active Indian Financial Year (e.g., `FY 2025-26`) and Assessment Year (`AY 2026-27`).

#### `POST /api/v1/system/backup-database`
Generates an encrypted gzip PostgreSQL dump (`pg_dump`) and registers the backup in `database_backup_logs`.

#### `GET /api/v1/system/backup-logs`
Returns historical database backup log entries with file sizes and Google Drive synchronization states.
