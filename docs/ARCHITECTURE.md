# b00k5 System Architecture & Engineering Blueprint

## 1. Executive Architecture Summary

**b00k5** is an open-source, local-first, multi-tenant financial operating system, general ledger, statutory compliance engine, and legal document vault designed specifically for Indian corporate entities (Private Limited, One Person Companies, and LLPs) operating under the **Companies Act, 2013**, **Central Goods and Services Tax (CGST) Act, 2017**, and the **Income-tax Act, 1961**.

The architecture adheres to four foundational engineering imperatives:
1. **Mathematical Inviolability:** General Ledger double-entry invariant $\sum \text{Debits} \equiv \sum \text{Credits}$ enforced at the database transaction level via triggers. Float arithmetic is strictly prohibited; all currency calculations utilize arbitrary-precision decimals (`Decimal(15, 2)`) with Banker's Rounding (`ROUND_HALF_EVEN`).
2. **Tenant Isolation via Row-Level Security (RLS):** Complete multi-tenant partitioning in PostgreSQL where every table enforces `tenant_id` scoping via PostgreSQL session variables (`app.current_tenant_id`) and forced RLS policies.
3. **Hardware-Anchored Secretarial Cryptography:** Class-3 Digital Signature Certificate (DSC) signing performed on the client director's workstation via a localhost PKCS#11 loopback bridge (`http://127.0.0.1:28045`), ensuring private cryptographic keys never transit network boundaries.
4. **Statutory Watchdog Automation:** Real-time countdown tracking and compounding fine calculators for mandatory Indian corporate compliance (INC-20A, DIR-3 KYC, AOC-4, MGT-7, and Section 173 Board Meeting intervals).

---

## 2. C4 Architecture Specification

### 2.1 C4 Level 1: System Context Diagram

The System Context diagram details how human actors and external statutory systems interact with the b00k5 platform boundaries.

```mermaid
flowchart TD
    subgraph Users ["Corporate Actors & Auditors"]
        Founder["Startup Founder / Director<br/>(Class 3 DSC Signer)"]
        Accountant["Head of Finance / Accountant<br/>(Maker / Bookkeeper)"]
        Auditor["Statutory Auditor / CA<br/>(External Reviewer)"]
    end

    subgraph Platform ["b00k5 Financial OS Boundary"]
        b00k5App["b00k5 Platform<br/>(Local-First ERP, GL & Compliance)"]
    end

    subgraph ExternalSystems ["External Statutory Gateways & Hardware"]
        HSMToken["HyperPKI USB DSC Token<br/>(HYP2003 / ePass2003 PKCS#11)"]
        GoogleDrive["Google Drive API<br/>(Offsite Encrypted DR Backups)"]
        MCA["MCA21 Portal / GSTN<br/>(Statutory Filings Target)"]
    end

    Founder -->|"Manages company, reviews compliance, signs Board Minutes"| b00k5App
    Accountant -->|"Issues GST invoices, scans vendor bills, reconciles bank lines"| b00k5App
    Auditor -->|"Inspects General Ledger, Trial Balance, and exports Auditor Pack"| b00k5App

    Founder -.->|"Plugs physical token into workstation"| HSMToken
    b00k5App <-->|"Cryptographic hash signing via PKCS#11 bridge"| HSMToken
    b00k5App -->|"Automated encrypted database dumps & vault sync"| GoogleDrive
    b00k5App -.->|"Generates compliant PDF documents & XML/XBRL readiness"| MCA
```

---

### 2.2 C4 Level 2: Container Diagram

The Container diagram illustrates the runtime microservices, data stores, worker queues, and reverse-proxy components.

```mermaid
flowchart TB
    subgraph ClientLayer ["Client Presentation Layer"]
        Browser["Next.js 14 Web Application<br/>(React, Tailwind CSS, Lucide)<br/>Port: 3000"]
        Bridge["DSC PKCS#11 Loopback Daemon<br/>(Python / SoftHSM2 / PyKCS11)<br/>Port: 28045 (Localhost)"]
    end

    subgraph APILayer ["Application & API Core"]
        FastAPI["FastAPI Financial Engine<br/>(Async SQLAlchemy, Pydantic v2)<br/>Port: 8000"]
    end

    subgraph WorkersLayer ["Asynchronous Processing Fleet (Celery)"]
        WorkerOCR["Celery Worker: OCR<br/>(Tesseract, pdfplumber, OpenCV)<br/>Queue: ocr_queue"]
        WorkerReconcile["Celery Worker: Reconcile<br/>(3-Tier Bank Matcher)<br/>Queue: reconcile_queue"]
        WorkerSync["Celery Worker: GDrive Sync<br/>(Google API Client, DB Dumps)<br/>Queue: gdrive_queue"]
    end

    subgraph DataStorage ["Persistence & Object Storage"]
        Postgres[("PostgreSQL 16 Engine<br/>(Double-Entry Schema, RLS, Triggers)<br/>Port: 5432")]
        Redis[("Redis 7 In-Memory Cache<br/>(Task Broker & Result Backend)<br/>Port: 6379")]
        MinIO[("MinIO S3 Object Storage<br/>(Encrypted Document Locker)<br/>Ports: 9000 (API), 9001 (Console)")]
    end

    Browser -->|"HTTP / REST API (JWT Authenticated)"| FastAPI
    Browser <-->|"HTTP JSON-RPC (Hash signing)"| Bridge
    FastAPI -->|"Async connection pool (asyncpg)"| Postgres
    FastAPI -->|"Enqueue background tasks"| Redis
    FastAPI -->|"Store/retrieve statutory documents & receipts"| MinIO

    Redis -->|"Dispatches ocr_queue"| WorkerOCR
    Redis -->|"Dispatches reconcile_queue"| WorkerReconcile
    Redis -->|"Dispatches gdrive_queue"| WorkerSync

    WorkerOCR -->|"Reads raw files / stores parsed text"| MinIO
    WorkerOCR -->|"Updates invoice & expense models"| Postgres
    WorkerReconcile -->|"Matches bank lines against GL"| Postgres
    WorkerSync -->|"Reads documents / writes sync ledger"| MinIO
    WorkerSync -->|"Fetches encrypted database dumps"| Postgres
```

---

### 2.3 C4 Level 3: Component Diagram (FastAPI Financial Engine)

Inside the FastAPI Container (`apps/api/app`), modules are partitioned into decoupled domain routers, dependencies, and business domain engines:

```mermaid
flowchart LR
    subgraph APIRouters ["Domain API Routers (/api/v1)"]
        AuthRouter["auth.py<br/>(JWT, Google OAuth2)"]
        InvoicesRouter["invoices.py<br/>(GST Invoicing)"]
        ExpensesRouter["expenses.py<br/>(OCR & Reimbursements)"]
        ReconcileRouter["reconciliation.py<br/>(Bank Statement Matching)"]
        LedgerRouter["ledger.py<br/>(General Ledger & Period Close)"]
        ComplianceRouter["compliance.py<br/>(Watchdog & Minutes)"]
        VaultRouter["vault.py<br/>(Document Locker & Zip)"]
        StorageRouter["storage.py<br/>(Google Drive Integration)"]
        IAMRouter["iam.py<br/>(Tenant RBAC)"]
    end

    subgraph ServiceEngines ["Core Domain Business Services"]
        GSTEngine["gst_calculator.py<br/>(Place of Supply & Tax Legs)"]
        LedgerService["ledger_service.py<br/>(Atomic Journal Postings)"]
        ReconcileEngine["reconciliation_engine.py<br/>(3-Tier Bank Matcher)"]
        BillAnalyzer["bill_analyzer.py<br/>(RegEx & Indian GSTIN Parser)"]
        PeriodCloseEngine["period_close_engine.py<br/>(Nominal Zeroing & Roll)"]
        SubledgerService["subledger_service.py<br/>(AR/AP Aging & Bad Debts)"]
        DocAssembly["document_assembly.py<br/>(MCA SS-1/SS-2 Minutes Gen)"]
        ESignService["esign_service.py<br/>(pyHanko PAdES Signer)"]
        DBBackupService["db_backup.py<br/>(pg_dump & AES-256)"]
    end

    InvoicesRouter --> GSTEngine
    GSTEngine --> LedgerService
    ExpensesRouter --> BillAnalyzer
    ExpensesRouter --> LedgerService
    ReconcileRouter --> ReconcileEngine
    ReconcileEngine --> LedgerService
    LedgerRouter --> LedgerService
    LedgerRouter --> PeriodCloseEngine
    LedgerRouter --> SubledgerService
    ComplianceRouter --> DocAssembly
    DocAssembly --> ESignService
    StorageRouter --> DBBackupService
```

---

## 3. Core Business Logic & State Machines

### 3.1 Double-Entry General Ledger Invariant Engine

The General Ledger relies on an inviolable mathematical guarantee:
$$\sum_{i=1}^{n} \text{Debit}_i = \sum_{j=1}^{m} \text{Credit}_j$$

Every financial event in b00k5 is mapped to balanced journal lines:
1. **Invoice Issuance (Quote-to-Cash):**
   * **Debit:** `Accounts Receivable (Code 1020)` for Grand Total
   * **Credit:** `Operating SaaS/Consulting Revenue (Code 3010/3020)` for Subtotal
   * **Credit:** `Output CGST (Code 2050)` & `Output SGST (Code 2051)` (if Intra-state) OR `Output IGST (Code 2052)` (if Inter-state)
2. **Founder Personal Expense (Procure-to-Pay):**
   * **Debit:** `Expense Account (Code 4010-4090)` for Base Cost
   * **Debit:** `Input GST Credit (Code 1030-1032)` for Input Tax
   * **Credit:** `Director Reimbursements Payable (Code 2105)` for Grand Total
3. **Database-Level Trigger (`check_zero_sum_balance`):**
   * Executed at transaction commit (`CONSTRAINT TRIGGER DEFERRABLE INITIALLY DEFERRED`).
   * Computes discrepancy $\delta = |\sum \text{Debit} - \sum \text{Credit}|$. If $\delta > 0.00$, the transaction aborts with an uncatchable SQL `RAISE EXCEPTION`.

```mermaid
stateDiagram-v2
    [*] --> Draft : Draft Invoice / Expense Created
    Draft --> Validated : Mod-36 GSTIN & Tax Verified
    Validated --> Committed : Atomic DB Transaction Open
    state Committed {
        PostDebitLeg --> PostCreditLeg
        PostCreditLeg --> EvaluateZeroSumTrigger
        EvaluateZeroSumTrigger --> AbortRollback : Discrepancy > 0.00
        EvaluateZeroSumTrigger --> LedgerWritten : Discrepancy == 0.00
    }
    AbortRollback --> Draft : Raise Error 400
    LedgerWritten --> Posted : Immutable Journal Voucher Generated
    Posted --> [*]
```

---

### 3.2 3-Tier Bank Reconciliation Engine

The reconciliation engine processes ingested bank statements (PDF, CSV, Excel) through a deterministic 3-tier cascade:

```mermaid
flowchart TD
    StatementLine["Raw Bank Statement Line<br/>(Date, Description, Debit/Credit, Balance)"] --> Tokenizer["bank_tokenizer.py<br/>(Extracts UTR, Cheque No, Counterparty)"]
    
    Tokenizer --> Tier1{"Tier 1: Deterministic Match<br/>Exact UTR / Cheque Ref"}
    Tier1 -->|Found Exact GL Bank Leg| MatchTier1["Status: Matched (Tier 1)<br/>Confidence: 1.0<br/>Voucher Linked"]
    
    Tier1 -->|No Exact UTR| Tier2{"Tier 2: Heuristic Fuzzy Match<br/>Date: [-2, +5] Days<br/>Amount: Exact<br/>Similarity: > 0.85"}
    Tier2 -->|High Match Score| MatchTier2["Status: Matched (Tier 2)<br/>Confidence: >= 0.85<br/>Voucher Linked"]
    
    Tier2 -->|No Heuristic Candidate| AutoCategory{"Special Account Rule?<br/>Bank Charges (4030)<br/>Interest Income (3030)<br/>FD Principal (1040)"}
    AutoCategory -->|Matched Rule| AutoVoucher["Auto-Generate Journal Voucher<br/>Debit/Credit matched to standard COA"]
    
    AutoCategory -->|Unidentified Inflow/Outflow| Tier3["Tier 3: Suspense Allocation<br/>Route to 2099 Bank Suspense<br/>Flag for Founder Review"]
```

---

### 3.3 Hardware DSC Token Signing Lifecycle (MCA Secretarial Standards)

In strict accordance with the Information Technology Act, 2000 and MCA Secretarial Standards (SS-1 and SS-2):
1. **Document Assembly:** FastAPI compiles dynamic HTML/CSS Board Meeting Minutes or Resolutions with the official Corporate Letterhead (CIN, Registered Office, Board Attendance).
2. **PDF Compilation & SHA-256 Digest:** The document is rendered into an immutable PDF, and its SHA-256 hash digest is generated.
3. **Localhost PKCS#11 Loopback Request:** The browser contacts `http://127.0.0.1:28045/sign-hash`.
4. **Hardware Execution:** The local bridge accesses the HyperPKI HYP2003 / ePass2003 USB token via native dynamic driver (`libespki.dylib`, `libespki.so`, or `eps2003csp11.dll`), authenticates the User PIN, and performs RSA-2048 signing on-chip.
5. **PAdES Timestamp & Cryptographic Audit:** The signature is injected into the PDF via pyHanko, verified against the public X.509 certificate, and recorded in `dsc_signature_audit`.

```mermaid
sequenceDiagram
    autonumber
    actor Founder as Authorized Director
    participant Web as Next.js Web UI (:3000)
    participant API as FastAPI Backend (:8000)
    participant Bridge as Local DSC Bridge (:28045)
    participant Token as USB Token (PKCS#11)
    participant DB as PostgreSQL (:5432)

    Founder->>Web: Click "Sign Minutes via Hardware DSC"
    Web->>API: POST /api/v1/compliance/generate-document?doc_type=board_minutes
    API->>API: Generate PDF & Compute SHA-256 Hash
    API-->>Web: Return doc_id, document_hash, unsigned_pdf_url
    
    Web->>Bridge: POST /sign-hash { hash, pin, slot: 0 }
    Bridge->>Token: C_Login(CKU_USER, PIN)
    Token-->>Bridge: CKR_OK
    Bridge->>Token: C_SignInit(CKM_RSA_PKCS) + C_Sign(hash)
    Token-->>Bridge: Cryptographic Signature Bytes
    Bridge-->>Web: Return signature_hex, x509_cert_der
    
    Web->>API: POST /api/v1/dsc/submit-signature { doc_id, signature_hex, x509_cert }
    API->>API: Inject PAdES PKCS#7 signature into PDF (pyHanko)
    API->>DB: INSERT INTO dsc_signature_audit (doc_id, signer_din, sha256_hash)
    DB-->>API: Row Committed
    API-->>Web: Return signed_pdf_download_url
    Web-->>Founder: Show "✓ Cryptographically Signed & Locked"
```

---

## 4. Multi-Tenant Row-Level Security (RLS) Engine

Multi-tenancy in b00k5 does not rely on application-level `WHERE tenant_id = ...` filters, which are susceptible to developer error. Instead, security is enforced in the database kernel:

1. **Table Policies:** All business tables enable PostgreSQL RLS:
   ```sql
   ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
   ALTER TABLE journal_entries FORCE ROW LEVEL SECURITY;

   CREATE POLICY tenant_isolation_policy ON journal_entries
       FOR ALL
       USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID)
       WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID);
   ```
2. **Session Context Injection:** The database dependency (`apps/api/app/api/deps.py`) sets the tenant ID on every session checkout:
   ```python
   await db.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant.id}';"))
   ```
3. **Cross-Tenant Breach Prevention:** If a rogue query attempts to select, insert, update, or delete data belonging to another tenant, PostgreSQL silently excludes the records or aborts the query with zero rows affected.

---

## 5. Network & Deployment Topology

```
Host Network / Ingress
  ├── :3000   -> Next.js Web Frontend (SSR / React 18)
  ├── :8000   -> FastAPI Core Engine (Uvicorn Async Worker)
  ├── :9000   -> MinIO S3 Object Storage API
  ├── :9001   -> MinIO Object Storage Web Console
  ├── :28045  -> DSC PKCS#11 Hardware Token Loopback Bridge
  └── Internal Docker Network (b00k5-net):
        ├── b00k5_postgres:5432 (PostgreSQL 16 Engine)
        ├── b00k5_redis:6379    (Redis 7 Broker)
        ├── b00k5_minio:9000    (Internal S3 Endpoint)
        ├── b00k5_worker_ocr    (Celery prefork worker - 2 processes)
        ├── b00k5_worker_reconcile (Celery prefork worker - 2 processes)
        └── b00k5_worker_sync   (Celery prefork worker - 2 processes)
```
