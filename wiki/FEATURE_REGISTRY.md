# b00k5 Feature Registry & Statutory Requirements

This registry documents all core business capabilities, statutory compliance engines, and infrastructure subsystems in `b00k5`. Every feature is cross-referenced with its statutory legal foundation under Indian corporate and tax law.

---

## 🏛️ Statutory Legal Citations Key
- **Companies Act, 2013:** Section 10A (INC-20A), Section 12 (INC-22), Section 73 & Rules (DPT-3), Section 92 (MGT-7/7A), Section 128 (Books & 8-Year Retention), Section 134 (Board Report), Section 137 (AOC-4), Section 139 (ADT-1), Section 173 (SS-1 Board Meetings).
- **Central Goods and Services Tax (CGST) Act, 2017:** Section 10 (Composition), Section 12/13 (Time of Supply), Section 16 (Input Tax Credit eligibility), Section 31 (Tax Invoice), Rule 88A (Order of ITC utilization).
- **Income-tax Act, 1961:** Section 37(1) (Business expenses), Section 40A(3) (Cash limits), Section 44AA (Maintenance of accounts), Section 194C/J/I/H (TDS withholding), Section 234B/234C (Advance tax interest).

---

## 📦 Feature Modules

### 1. General Ledger & Double-Entry Accounting
| Feature ID | Feature Name | Statutory Citation | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `FEAT-GL-01` | Double-Entry Integrity Trigger | CA 2013 §128 | $\left\vert{}\sum \text{Debits} - \sum \text{Credits}\right\vert{} \equiv 0.00$ enforced at DB level. |
| `FEAT-GL-02` | Fixed-Point Decimal Arithmetic | CGST Act §31 | Exact `Decimal(15, 2)` calculation with Banker's Rounding (`ROUND_HALF_EVEN`). Zero floats. |
| `FEAT-GL-03` | Immutable Posted Journal Ledger | CA 2013 §128 | Posted entries cannot be updated or deleted; mutations must use reversing journal vouchers. |
| `FEAT-GL-04` | 3-Stage Financial Year Closing | CA 2013 §137 | Active Period -> Audit Review Window -> Permanent Cryptographic Freeze. |

### 2. GST Invoicing & Dynamic Place of Supply
| Feature ID | Feature Name | Statutory Citation | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `FEAT-INV-01` | Dynamic POS Dual GST Netting | CGST Act §12 | Same state code: CGST 9% + SGST 9%. Different state code: IGST 18%. |
| `FEAT-INV-02` | Multi-Item Expandable Invoicing | CGST Act §31 | Multi-line services with flexible descriptions, HSN/SAC codes, and dynamic line totals. |
| `FEAT-INV-03` | Universal Next-Number Auto-Sequencing | CGST Rule 46 | Consecutively sequenced non-colliding invoice identifiers (e.g. `INV-2026-05-001`). |
| `FEAT-INV-04` | Statutory Document Neutrality | Brand Invariant | Invoices and receipts have zero third-party vendor watermarks; strictly tenant-branded. |

### 3. Banking Feeds & 3-Tier Reconciliation
| Feature ID | Feature Name | Statutory Citation | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `FEAT-BANK-01` | Multi-Format Statement Ingestion | IT Act §44AA | Native parsing for HDFC, ICICI, SBI, and Axis bank CSV/PDF statements. |
| `FEAT-BANK-02` | 3-Tier Transaction Matching Engine | Accounting Stds | Tier 1: Exact UTR/RRN. Tier 2: Fuzzy amount + date window. Tier 3: Suspense account flag. |
| `FEAT-BANK-03` | 5-Year Chronological FY Selector | CA 2013 §128 | Seamless switching between 5 financial years with automatic statement partitioning. |

### 4. Smart Expense Scan & Bill Analysis
| Feature ID | Feature Name | Statutory Citation | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `FEAT-EXP-01` | Celery Asynchronous OCR Ingestion | IT Act §37(1) | Background processing of receipts, bills, and tax invoices using OpenCV and Tesseract. |
| `FEAT-EXP-02` | Unvouched Cash Gate & Disallowance | IT Act §40A(3) | Hard block on cash disbursements exceeding ₹10,000; mandatory internal debit self-voucher. |
| `FEAT-EXP-03` | Authentic Source Binary Preservation | MinIO Invariant | Uploaded authentic documents permanently stored in MinIO; zero synthetic overwrite. |

### 5. Corporate Governance & Secretarial Standards
| Feature ID | Feature Name | Statutory Citation | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `FEAT-GOV-01` | ICSI SS-1 120-Day BM Watchdog | CA 2013 §173(1) | Automatic alert and countdown when interval between Board Meetings approaches 120 days. |
| `FEAT-GOV-02` | Form DPT-3 Loan Declarations | CA 2013 §73 | Director non-borrowed fund declaration assembly for director reimbursements. |
| `FEAT-GOV-03` | INC-20A Borrowing Powers Gate | CA 2013 §10A | Commercial borrowing operations locked until INC-20A commencement filing is verified. |
| `FEAT-GOV-04` | Statutory Registers Generator | CA 2013 §88 | Real-time generation of Register of Members (MGT-1), Directors (DIR-12), and Loans. |

### 6. Hardware Cryptography & Document Vault
| Feature ID | Feature Name | Statutory Citation | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `FEAT-CRYP-01` | Class-3 USB PKCS#11 Token Bridge | IT Act 2000 §3 | Localhost loopback bridge (`:28045`) for direct hardware signing without exposing private keys. |
| `FEAT-VAULT-01` | Permanent vs Annual Vault Partitioning | CA 2013 §128 | Permanent anchors (PAN, CIN, COI) stored once; annual returns partitioned by FY tabs. |
| `FEAT-VAULT-02` | MinIO S3 Object Storage with WORM | SRE Invariant | SHA-256 deduplicated, tamper-evident document storage with versioning. |

### 7. IAM & Multi-Tenant Security
| Feature ID | Feature Name | Statutory Citation | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `FEAT-IAM-01` | PostgreSQL Kernel Row-Level Security | Security Top 10 | Session-bound RLS prevents cross-tenant data leakage across all database tables. |
| `FEAT-IAM-02` | Role-Based Access Control (RBAC) | Governance | Distinct scopes for Super Admin, Tenant Owner, Finance Manager, CA Auditor, and Employee. |
| `FEAT-IAM-03` | Target Organization Scope Badge | UI Ergonomics | Unambiguous visual badge displaying active legal entity and CIN when managing IAM. |

### 8. Backup, Disaster Recovery & Telemetry
| Feature ID | Feature Name | Statutory Citation | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `FEAT-DR-01` | AES-256-GCM Dual-Layer Backup | CA 2013 §128(5) | Automated database and S3 backup drills achieving RTO < 30s with zero ledger drift. |
| `FEAT-SRE-01` | Branch Deploy Automation Script | DevOps Invariant | One-command deploy of any git branch to isolated test environment (`scripts/branch_deploy.sh`). |
