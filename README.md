# b00k5: Open-Source Financial OS, ERP & Statutory Compliance Engine for Indian Startups

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14_App_Router-black.svg)](https://nextjs.org/)
[![Docker Compose v2](https://img.shields.io/badge/Docker_Compose-v2-2496ED.svg)](https://docs.docker.com/compose/)

**b00k5** is an enterprise-grade, local-first, multi-tenant financial operating system designed to eliminate the operational and regulatory friction Indian early-stage startups incur managing bookkeeping, corporate governance, and statutory audits. Built strictly according to the **Companies Act, 2013**, **CGST Act, 2017**, and the **Income-tax Act, 1961**.

---

## 📚 Complete Documentation Suite

Comprehensive architecture, schema, API, operational, and legal guides are available in the [`docs/`](docs/) directory:

| Guide | Description | Target Audience |
| :--- | :--- | :--- |
| **[System Architecture Blueprint](docs/ARCHITECTURE.md)** | C4 Context/Container/Component diagrams, data flows, and state machines. | System Architects, Engineers |
| **[Relational Database Schema](docs/DATABASE_SCHEMA.md)** | Full ERD, 18+ table data dictionary, kernel triggers, and Schedule III COA. | DBAs, Backend Developers |
| **[OpenAPI 3.1 REST API Reference](docs/API_REFERENCE.md)** | Endpoints, query parameters, JSON request/response payloads, and error codes. | API Integrators, Frontend Devs |
| **[End-User Operations Manual](docs/USER_GUIDE.md)** | Step-by-step walkthroughs for invoicing, OCR bills, 3-tier bank match, and DSC. | Founders, Accountants, Operators |
| **[Administrator & Operations Manual](docs/ADMIN_GUIDE.md)**| Installation, environment variables, RBAC matrix, backups, and DR recovery. | DevOps, Sysadmins, SecOps |
| **[Diagnostics & Troubleshooting Runbook](docs/TROUBLESHOOTING.md)** | Health check one-liners, root-cause matrix, error codes, and emergency fixes. | Support Engineers, On-Call Devs |
| **[Open-Source Strategy & Clean-Room](docs/OPEN_SOURCE_STRATEGY.md)**| License matrix (Apache 2.0), SBOM with SPDX tags, and clean-room specifications. | Legal, Open-Source Contributors |

---

## ⚡ Quickstart Deployment

Deploy the entire b00k5 fleet (Next.js, FastAPI, PostgreSQL, Redis, MinIO, Celery Workers, Mock HSM Bridge) in a single command:

```bash
git clone https://github.com/your-org/b00k5.git
cd b00k5
./install.sh
```

### Deployed Services & Endpoints:

| Service | Endpoint URL | Default Credentials |
| :--- | :--- | :--- |
| **Web Application** | [http://localhost:3000](http://localhost:3000) | `admin@acme.corp` / `Admin@12345` |
| **FastAPI Core Engine** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI |
| **MinIO Object Console** | [http://localhost:9001](http://localhost:9001) | User: `minio_storage_admin` (Password in `.env`) |
| **Hardware DSC Bridge** | [http://localhost:28045/status](http://localhost:28045/status) | Localhost loopback daemon |

---

## 🏛️ Core Accounting Pillars & Modules

```
┌────────────────────────────────────────────────────────────────────────┐
│                        b00k5 CORE MODULES                              │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Inviolable Double-Entry GL    │ 5. Legal Locker & Document Vault    │
│ 2. Dynamic GST Engine & HSN/SAC  │ 6. Statutory Compliance Watchdog    │
│ 3. 3-Tier Bank Reconciliation    │ 7. Hardware USB DSC Token Signer    │
│ 4. Smart Bill OCR & Founder GL   │ 8. Disaster Recovery & GDrive Sync  │
└──────────────────────────────────┴─────────────────────────────────────┘
```

1. **Inviolable Double-Entry General Ledger:**
   * Mathematical invariant $\sum \text{Debits} \equiv \sum \text{Credits}$ enforced at database commit via PostgreSQL triggers.
   * Floating-point arithmetic is strictly prohibited; all currency arithmetic is executed using arbitrary-precision decimals (`Decimal(15, 2)`) with Banker's Rounding (`ROUND_HALF_EVEN`).
   * Transaction immutability: posted journal entries cannot be edited or deleted.
2. **Quote-to-Cash & Dynamic Place of Supply (POS):**
   * Automatic interstate (IGST) vs intrastate (CGST + SGST) tax determination based on customer GSTIN state prefix.
   * Modulus-36 checksum verification for all 15-character GST numbers.
3. **Smart Expenses & Founder Out-of-Pocket Claims:**
   * Multi-modal bill parsing via local Tesseract OCR and regex matching.
   * Founder reimbursement tracking (`Director Reimbursements Payable - Code 2105`).
   * Section 40A(3) Income Tax Act violation alerts for single-day cash transactions $> ₹10,000$.
4. **3-Tier Bank Reconciliation Engine:**
   * **Tier 1:** Deterministic match on exact UTR / Cheque reference.
   * **Tier 2:** Fuzzy heuristic match within $[-2, +5]$ days date window ($> 85\%$ score).
   * **Tier 3:** Suspense allocation routing unmatched inflows/outflows to `Code 2099`.
5. **Class-3 Hardware USB DSC Token Signer:**
   * Direct communication with authentic HyperPKI HYP2003 / ePass2003 tokens via local PKCS#11 bridge (`http://127.0.0.1:28045`).
   * Private cryptographic keys never leave the physical smart card chip.
   * Official MCA Board Minutes compiled with Section 173 Secretarial Standards (SS-1/SS-2).
6. **Encrypted Legal Locker & Auditor Export:**
   * Multi-bucket MinIO S3 document repository with SHA-256 integrity verification.
   * One-click generation of structured Auditor ZIP packages for statutory CAs.

---

## 🧪 Automated Verification Suite

Run the full battery of 76 zero-mock automated tests:

```bash
# 12-Pillar General Ledger & Accounting Invariant Audit
docker exec b00k5_api pytest /app/tests/accounting_core

# End-to-End Master Directive Journeys
docker exec b00k5_api pytest /app/tests/integration/test_master_directive_audit.py

# Multi-Tenancy Row-Level Security (RLS) Invariants
docker exec b00k5_api pytest /app/tests/integration/test_multi_tenancy_rls.py

# Bank Reconciliation Zero-Drift Tests
docker exec b00k5_api pytest /app/tests/integration/test_bank_reconciliation.py
```

---

## 🤝 Contributing

We welcome community contributions! Please review our **[Contributing Guidelines](CONTRIBUTING.md)** and **[Open-Source Strategy](docs/OPEN_SOURCE_STRATEGY.md)** before opening pull requests.

All commits must include a Developer Certificate of Origin (DCO) sign-off (`git commit -s`).

---

## 📄 License

b00k5 is licensed under the **[Apache License, Version 2.0](LICENSE)**. See [NOTICE](NOTICE) for third-party acknowledgments.
