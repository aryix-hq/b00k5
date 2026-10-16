# b00k5: Open-Source Financial OS, ERP & Statutory Compliance Engine for Indian Startups

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15_App_Router-black.svg)](https://nextjs.org/)
[![Docker Compose v2](https://img.shields.io/badge/Docker_Compose-v2-2496ED.svg)](https://docs.docker.com/compose/)
[![CI: Passing](https://img.shields.io/badge/CI-Passing-brightgreen.svg)](.github/workflows/ci.yml)
[![Zero-Mock Tested](https://img.shields.io/badge/Tests-Zero--Mock_Verified-success.svg)](tests/)

Engineered by **[ARYIX](https://www.aryix.co.in/)**, **b00k5** is an enterprise-grade, local-first, multi-tenant financial operating system and statutory compliance engine engineered specifically for Indian startups, Private Limited companies, One Person Companies (OPCs), and LLPs. Built strictly in compliance with the **Companies Act, 2013**, **Central Goods and Services Tax (CGST) Act, 2017**, and the **Income-tax Act, 1961**, b00k5 unifies double-entry bookkeeping, GST place-of-supply billing, smart OCR expense ingestion, multi-year bank reconciliation, Class-3 USB hardware token signing, Advance Tax forecasting, and automated Schedule III financial statement generation into a sovereign, self-hostable platform.

---

## 📜 The Sovereign Accounting Manifesto ("Why We Built b00k5")

> *"In April 2023, Intuit abruptly pulled QuickBooks out of India, stranding tens of thousands of growing businesses and proving that closed cloud ERPs pose an existential threat to business continuity.*
>
> *Meanwhile, desktop alternatives like Tally Prime remain anchored in the 1990s—vulnerable to corrupted proprietary `.tsf` binary files and isolated from modern web APIs. Cloud accounting platforms charge steep per-user monthly subscription taxes while locking your company's most sensitive commercial ledger on foreign servers.*
>
> *We engineered **b00k5** at **[ARYIX](https://www.aryix.co.in/)** on a singular mission: **your corporate financial ledger and statutory compliance must remain sovereign, local-first, and mathematically verifiable.***
>
> *b00k5 combines PostgreSQL 16 ACID transactions, authentic MinIO document preservation, and automated Companies Act secretarial governance (SS-1/SS-2) into a 100% free, open-source platform that no cloud vendor can ever turn off or hold hostage."*
>
> — **Adithya Khamithkar**, Founder, [ARYIX](https://www.aryix.co.in/)

---

## 🤝 Community Open-Source vs. ARYIX Enterprise Support

b00k5 operates under the **Commercial Open-Source Software (COSS)** model:

| Offering Tier | Scope & Features | Target Audience | Support Mechanism |
| :--- | :--- | :--- | :--- |
| **Community Edition**<br/>*(100% Free & Open Source)* | • Apache 2.0 License<br/>• Self-hosted Docker deployment<br/>• Full General Ledger, Banking, Invoicing & Vault<br/>• Self-managed backups & recovery | Technical founders, solo developers, tech-savvy CAs | GitHub Issues & Community Discussions |
| **Enterprise Support & Consulting**<br/>*(By [ARYIX](https://www.aryix.co.in/))* | • White-glove bare-metal & private cloud deployment<br/>• Custom Tally, QuickBooks & legacy ERP migrations<br/>• Dedicated statutory SLA for urgent MCA/GST changes<br/>• Custom ERP bridges, bespoke bank feeds & team onboarding | Growing startups, venture-backed companies, multi-entity groups | **Dedicated SLA & Consulting by [ARYIX](https://www.aryix.co.in/)** |

---

## 🏛️ Non-Negotiable System Invariants

1. **Mathematical Inviolability:** General Ledger double-entry invariant $\left\vert{}\sum \text{Debits} - \sum \text{Credits}\right\vert{} \equiv 0.00$ enforced at the database commit level via PostgreSQL kernel triggers. Binary floating-point arithmetic is strictly prohibited; all currency arithmetic is executed using arbitrary-precision decimals (`Decimal(15, 2)`) with Banker's Rounding (`ROUND_HALF_EVEN`).
2. **Tenant Isolation via PostgreSQL RLS:** Complete multi-tenant partitioning in PostgreSQL where every query executes with session-bound Row-Level Security (`SET LOCAL app.current_tenant = :tenant_id` and `SET LOCAL app.current_user_role = :role`).
3. **Statutory 8-Year Document Retention (Sec 128):** All vouchers, invoices, bank statements, and statutory anchors are protected under Companies Act Section 128. Deleting active tenants with existing financial records is prevented via `ON DELETE RESTRICT` foreign keys and soft archiving (`is_archived = TRUE`).
4. **Hardware-Anchored Secretarial Cryptography:** Class-3 Digital Signature Certificate (DSC) signing performed directly on the director's workstation via a localhost PKCS#11 loopback bridge (`http://127.0.0.1:28045`), ensuring private cryptographic keys never transit network boundaries.
5. **Authentic Source of Truth:** Prior year opening balances are calibrated directly from authentic filed statutory returns (**MGT-7/7A**, **AOC-4**, **ITR-6/ITR-V**). Authentic binary files (PDFs, XMLs) are permanently preserved in sovereign MinIO object storage with SHA-256 deduplication.

---

## 📊 Feature Comparison Matrix: b00k5 vs. Competitors

| Capability / Architecture | **b00k5** (Open Source) | **Zoho Books** | **Tally Prime** | **Odoo ERP** |
| :--- | :---: | :---: | :---: | :---: |
| **Hosting Model** | **Local-First / Sovereign Self-Hosted** | Closed SaaS Cloud | Desktop Monolith / LAN | Hybrid / SaaS |
| **Pricing** | **100% Free & Open Source (Apache 2.0)** | Per-org monthly subscription | Perpetual license + annual TSS | Modular app subscription |
| **MCA Compliance (INC-20A, DIR-3, DPT-3)** | **Native statutory engine & fine watchdog** | ❌ None | ❌ None | ❌ None |
| **Class-3 USB Hardware DSC Signer** | **Native PKCS#11 browser bridge** | ❌ Cloud-only / e-Sign | ⚠️ Windows desktop only | ❌ Third-party plugin |
| **Statutory 3-Stage FY Closing** | **Native (Active -> Audit Window -> Freeze)** | Manual lock dates | Manual period split | Accounting lock date |
| **Schedule III Division I Export** | **Native auto-rounding (Rs. '00, Lakhs, Cr)** | ❌ Standard P&L/BS only | ⚠️ Schedule III addon required | ❌ Requires custom localization |
| **Advance Tax (Sec 234B/234C) Watchdog**| **Native 4-installment calculator** | ❌ None | ❌ None | ❌ None |
| **GST Runway & Rule 88A Optimization** | **Native ITC netting & cash forecast** | Standard GST reports | GST returns generation | Basic GST reports |
| **Bank Feeds & 5-Year FY Selector** | **Native 3-Tier Matcher (UTR/Fuzzy/Suspense)**| Automatic cloud bank feeds | Manual statement import | Plaid / Yodlee sync |
| **Row-Level Security (RLS)** | **Native PostgreSQL 16 Kernel RLS** | Application layer filter | ❌ No RLS (Single company DB)| Application layer filter |
| **Disaster Recovery (AES-256-GCM)** | **Automated DR drills (< 30s RTO, zero drift)**| Closed proprietary cloud | Manual zip backup | Manual pg_dump / Enterprise |

---

## 📚 Complete Documentation Suite

Comprehensive architecture, schema, API, operational, and legal guides are available in the [`docs/`](docs/) directory:

| Guide | Description | Target Audience |
| :--- | :--- | :--- |
| **[Competitive Benchmark](docs/COMPETITIVE_BENCHMARK.md)** | Head-to-head comparison vs Tally Prime, Zoho Books, QuickBooks, and ClearTax. | Founders, CFOs, Investors |
| **[Backup & DR Policy](docs/BACKUP_AND_DISASTER_RECOVERY_POLICY.md)** | Statutory 10-year retention schedule, RPO/RTO SLAs, and AES-256-GCM dual-sync. | SRE, Statutory Auditors, CAs |
| **[IAM & Governance Architecture](docs/IAM_AND_GOVERNANCE_ARCHITECTURE.md)** | Multi-tenant RBAC, DIR-3 DIN verification, ICAI auditor isolation, and scoping. | CISO, Security Auditors, CS |
| **[System Architecture Blueprint](docs/ARCHITECTURE.md)** | C4 Context/Container/Component diagrams, data flows, RLS model, and state machines. | System Architects, Engineers |
| **[Relational Database Schema](docs/DATABASE_SCHEMA.md)** | Full ERD, 20+ table data dictionary, kernel triggers, and Schedule III COA. | DBAs, Backend Developers |
| **[OpenAPI 3.1 REST API Reference](docs/API_REFERENCE.md)** | Complete endpoints, query parameters, JSON payloads, rate limits, and error codes. | API Integrators, Frontend Devs |
| **[End-User Operations Manual](docs/USER_GUIDE.md)** | Step-by-step walkthroughs for invoicing, OCR bills, 3-tier bank match, and DSC. | Founders, Accountants, Operators |
| **[Administrator & Operations Manual](docs/ADMIN_GUIDE.md)**| Installation, environment variables, RBAC matrix, backups, and DR recovery. | DevOps, Sysadmins, SecOps |
| **[Production Deployment Guide](docs/DEPLOYMENT_GUIDE.md)**| Docker Compose, reverse proxy (Nginx/Caddy HTTPS), S3 setup, and scaling. | SRE, Cloud Engineers |
| **[Enterprise Cloud Deployment Guide](docs/CLOUD_DEPLOYMENT_GUIDE.md)**| Standalone VPS vs BYO Database (Aurora/Cloud SQL), BYO Redis, and BYO S3/R2. | SRE, Enterprise Architects |
| **[Diagnostics & Troubleshooting Runbook](docs/TROUBLESHOOTING.md)** | Health check one-liners, root-cause matrix, error codes, and emergency fixes. | Support Engineers, On-Call Devs |
| **[Open-Source Strategy & Clean-Room](docs/OPEN_SOURCE_STRATEGY.md)**| License matrix (Apache 2.0), SBOM with SPDX tags, and clean-room specifications. | Legal, Open-Source Contributors |

---

## ⚡ Quickstart Deployment

### Universal One-Line Automated Installer

Deploy the complete sovereign stack (Next.js 15, FastAPI, PostgreSQL 16, Redis 7, MinIO S3, Celery OCR Workers, Hardware DSC Bridge) locally or on cloud VPS in a single command:

#### Linux, macOS & Cloud VPS (Bash / Curl):
```bash
curl -fsSL https://raw.githubusercontent.com/aryix-hq/b00k5/main/scripts/install.sh | bash
```

#### Windows 10 & 11 (PowerShell):
```powershell
irm https://raw.githubusercontent.com/aryix-hq/b00k5/main/scripts/install.ps1 | iex
```

> For step-by-step instructions for specific operating systems, manual installation, reverse proxy (Caddy/Nginx) HTTPS configuration, and hardware requirements, consult the **[Universal Installation Guide](docs/INSTALLATION_GUIDE.md)**.

### Alternatively, Standard Manual Docker Compose:

```bash
# 1. Clone repository
git clone https://github.com/aryix-hq/b00k5.git
cd b00k5

# 2. Copy environment template
cp .env.example .env

# 3. Launch container fleet in detached mode
docker compose up -d --build

# 4. Seed demonstration tenant and Schedule III accounts
docker exec b00k5_api python /app/seed_data.py
```

### Deployed Services & Access Points:

| Service | Endpoint URL | Default Credentials | Description |
| :--- | :--- | :--- | :--- |
| **Web Application** | [http://localhost:3000](http://localhost:3000) | `admin@acme.corp` / `Admin@12345` | Next.js 15 App Router GUI |
| **FastAPI Core Engine** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI | OpenAPI 3.1 REST APIs |
| **MinIO Storage Console**| [http://localhost:9001](http://localhost:9001) | User: `minio_storage_admin` (in `.env`) | Sovereign S3 Document Vault |
| **MinIO S3 API Endpoint**| [http://localhost:9000](http://localhost:9000) | S3 Compatible API | Binary object streaming |
| **Hardware DSC Bridge** | [http://localhost:28045/status](http://localhost:28045/status) | Localhost loopback daemon | PKCS#11 USB Token Daemon |

---

## 🏛️ Core Architectural Modules

```
┌────────────────────────────────────────────────────────────────────────┐
│                        b00k5 PLATFORM CORE                             │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Inviolable Double-Entry GL    │ 6. Statutory Baseline Calibration   │
│ 2. Dynamic GST Engine & POS      │ 7. 3-Stage Fiscal Year Closing      │
│ 3. 3-Tier Bank Reconciliation    │ 8. Advance Tax & GST Forecast       │
│ 4. Smart Bill OCR & Founder GL   │ 9. Class-3 Hardware USB DSC Signer  │
│ 5. Schedule III Financial Dossier│ 10. Sovereign Vault & DR Engine     │
└──────────────────────────────────┴─────────────────────────────────────┘
```

1. **Inviolable Double-Entry General Ledger:**
   * Mathematical invariant $\sum \text{Debits} \equiv \sum \text{Credits}$ verified prior to commit.
   * Floating-point numbers are strictly forbidden (`NUMERIC(15, 2)` arbitrary precision with Banker's Rounding).
   * Transaction immutability enforced at kernel level: posted vouchers cannot be modified or deleted.
2. **Quote-to-Cash & Dynamic Place of Supply (POS):**
   * Automatic interstate (IGST) vs intrastate (CGST + SGST) tax determination based on customer GSTIN state prefix.
   * Modulus-36 checksum verification for all 15-character GST numbers.
   * Customer directory typeahead combobox with instant state detection.
3. **Smart Expenses & Director Loan Declarations:**
   * Multi-modal bill parsing via local Tesseract OCR and regex heuristics.
   * Founder reimbursement tracking (`Director Reimbursements Payable - Code 2105`).
   * Rule 2(1)(c)(viii) DPT-3 loan compliance tracking, ensuring director loans are strictly from personal funds.
   * Section 40A(3) Income Tax Act violation alerts for single-day cash transactions $> ₹10,000$.
4. **3-Tier Bank Reconciliation Engine:**
   * Multi-year statement filtering supporting the current FY and the last 5 financial years.
   * **Tier 1:** Deterministic match on exact UTR / Cheque reference.
   * **Tier 2:** Fuzzy heuristic match within $[-2, +5]$ days date window ($> 85\%$ score).
   * **Tier 3:** Suspense allocation routing unmatched inflows/outflows to `Code 2099`.
5. **Schedule III Non-Ind AS Financial Statements:**
   * Division I compliant Balance Sheet and Statement of Profit & Loss.
   * MCA General Instructions Clause 4 auto-rounding: automatically scales figures to **Nearest Hundreds (Rs. '00)**, **Lakhs**, or **Crores** based on company turnover.
   * Dynamic comparative reporting: Balance Sheet as at selected date vs. prior year baseline.
   * Comprehensive Auditor Export Dossier (PDF statements, accounting notes, trial balance, and SHA-256 manifest).
6. **Statutory Baseline Calibration & Multi-Year Vault:**
   * Ingests authentic prior-year filed returns (**MGT-7/7A**, **AOC-4**, **ITR-6/ITR-V**).
   * Extracts opening balances directly from filed returns, treating statutory filings as the ultimate source of truth.
   * Chronologically organizes filings year-by-year with SHA-256 deduplication.
7. **Three-Stage Fiscal Year Closing Lifecycle:**
   * **Active Operating Period:** Full voucher entry and editing during the running financial year.
   * **Audit & Filing Window (01/04 to 31/10):** Books remain accessible for year-end adjustments, statutory audit revisions, and tax filings.
   * **Statutory Freeze:** Hard lockdown upon filing or statutory cutoff, freezing prior FY records and rolling balances forward.
8. **Statutory Tax Forecasting & GST Runways:**
   * **Advance Tax Engine:** Section 208/209/210 watchdog tracking mandatory quarterly installments (15%, 45%, 75%, 100%) and computing Section 234B/234C penal interest.
   * **GST Cash Flow Runway:** Real-time quarterly, half-yearly, and annual GST liability forecasts with Rule 88A ITC utilization optimization.
9. **Class-3 Hardware USB DSC Token Signer:**
   * Direct communication with authentic HyperPKI HYP2003 / ePass2003 smart cards via local PKCS#11 bridge (`http://127.0.0.1:28045`).
   * Cryptographic private keys never leave physical smart card silicon.
   * Board Minutes compliant with ICSI Secretarial Standards (SS-1/SS-2).
10. **Sovereign Legal Locker & Disaster Recovery:**
    * Multi-bucket MinIO S3 document storage with SHA-256 integrity validation.
    * Automated AES-256-GCM encrypted database backups and offsite Google Drive sync.
    * Automated Disaster Recovery (DR) drill script verifying recovery time objective (RTO < 30s) and zero ledger drift.

---

## 🧪 Automated Verification Suite

b00k5 enforces a **Zero-Mock Testing Mandate**: all integration tests and statutory rules run against real PostgreSQL 16, Redis 7, and MinIO service containers.

```bash
# 1. Run Complete Zero-Mock Test Suite
docker exec b00k5_api pytest /app/tests/accounting_core

# 2. Run Multi-Tenancy Row-Level Security (RLS) Penetration Tests
docker exec b00k5_api pytest /app/tests/integration/test_multi_tenancy_rls.py

# 3. Run End-to-End Master Directive Audits
docker exec b00k5_api pytest /app/tests/integration/test_master_directive_audit.py

# 4. Execute SRE Disaster Recovery (DR) Verification Drill
docker exec b00k5_api python /app/scripts/dr_drill.py

# 5. Execute TypeScript Frontend Static Analysis
cd apps/web && npx tsc --noEmit
```

---

## 🛡️ Security & Open-Source Governance

* **Zero-Leak Policy:** Never commit secrets, credentials, or private founder PII into version control. CI executes automated Gitleaks scans on every commit.
* **Leaky-Bucket Rate Limiting:** Login endpoints enforce Redis token-bucket rate limiting (max 5 attempts/minute) to mitigate brute-force credential stuffing.
* **Open Source License:** Distributed under the **Apache License, Version 2.0**. Commercial use, modification, and private deployment are permitted without royalty.

---

## 🤝 Contributing & Community

Contributions are welcomed! Please read our [Open-Source Strategy](docs/OPEN_SOURCE_STRATEGY.md) and review the [Developer Guidelines](.agents/rules/developer.md) before submitting pull requests.

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/statutory-module`).
3. Commit your changes (`git commit -m 'feat: add TDS Section 194J engine'`).
4. Ensure all zero-mock tests pass (`docker exec b00k5_api pytest`).
5. Push to the branch and open a Pull Request.
