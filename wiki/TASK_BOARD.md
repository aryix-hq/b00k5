# Sprint & Feature Task Board

> **Sprint Status:** Active Sprint — Offline Corporate Financial OS  
> **Working Branch:** `feat/sovereign-payroll-core-and-ledger`  
> **Last Updated:** 2026-10-18  

---

## 1. Active In Progress (Option A - Verification & Review)
*All Option A engineering deliverables completed; awaiting preview merge approval.*

---

## 2. Deferred / Documented Backlog
- [ ] `FEAT-AUDIT-01` (Option B): **MCA Rule 3(1) Audit Trail & Air-Gapped Local Encrypted Backup**:
  - *Specification:* [`docs/RESEARCH_OPTION_B_AUDIT_TRAIL_AND_BACKUP.md`](file:///Users/adithya/Code/b00k5/docs/RESEARCH_OPTION_B_AUDIT_TRAIL_AND_BACKUP.md).
  - Kernel-level triggers on journal vouchers and invoices writing to append-only `accounting_audit_trail`.
  - AES-256 encrypted single-click database & MinIO backup/restore utility.
- [ ] `FEAT-SC-01` (Option C): **Supply Chain 3-Way PO Matching & Ind AS 2 Perpetual FIFO Inventory**:
  - *Specification:* [`docs/RESEARCH_OPTION_C_SUPPLY_CHAIN_AND_INVENTORY.md`](file:///Users/adithya/Code/b00k5/docs/RESEARCH_OPTION_C_SUPPLY_CHAIN_AND_INVENTORY.md).
  - Purchase Orders $\leftrightarrow$ Goods Inward Notes $\leftrightarrow$ Vendor Bills matching with tolerance rules and landed cost allocation.
  - Real-time COGS debit/credit vouchers and Section 17(5)(h) ITC reversal triggers.

---

## 3. Ready for Review / Preview Deploy
- [x] `FEAT-BANK-04` (Option A): **Bank CMS Batch Payout Rails**:
  - Offline bulk payout file generation (`.csv`) for **HDFC ENet**, **ICICI CMS**, and **SBI CMP**.
  - 1-click batch download for monthly salaried payroll runs (Tabs 1 & 3) and contractor payout claims (Tab 5).
  - Fully tested across all three formats.
- [x] `FEAT-GST-01` (Option A): **GSTR-1 Portal-Ready JSON Exporter**:
  - Official GSTN offline tool schema (`b2b`, `b2cl`, `b2cs`, `cdnr`, `exp`, `hsn`, `doc_issue`).
  - 1-click upload to `gst.gov.in` without ClearTax or third-party cloud GSPs.
  - UI modal on `/invoices` with Year/Month selector and direct download trigger.
- [x] `FEAT-PAY-05`: **Contractors, Freelancers & Section 194C/194J Statutory TDS**:
  - Form 16A PDF certificate generator and 5th UI tab on `/payroll`.
  - Two-legged accounting lifecycle (Leg 1 Accrual, Leg 2 Disbursement).

---

## 4. Completed (Verified & Tested)
- [x] `FEAT-PAY-01`: **Core Salaried Payroll & Double-Entry Ledger Engine** (53/53 tests passing).
- [x] `FEAT-PAY-02`: **Statutory Exporters & Form 16 Part B Engine** (EPFO ECR `#~#`, ESIC `.xlsx`, PT Form 5, Form 16 PDF).
- [x] **UI Neutrality**: 100% Sovereign badges and labels removed across sidebar and `/payroll`.
- [x] **User Operations Manual**: Workflows 10, 11, 12, & 13 documented in `docs/USER_GUIDE.md`.
