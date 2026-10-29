# FEAT-GST-04: GSTR-1 Table 13 Document Summary, UQC Goods/Services Validation, and Advance Tax §234B/C Warning Gauges

> **Lifecycle Stage**: Stage 2 (Product Requirements & RICE Prioritization)  
> **Status**: Approved  
> **Author**: Product Manager (`@product-manager`)  
> **Target Branch**: `feat/FEAT-GST-04-gstr1-tab13-uqc-advtax`  
> **Source Research Note**: [`wiki/research/RES-GST-04.md`](../research/)  
> **Phased Implementation Plan**: [`wiki/plans/PLAN-004_GSTR1_TAB13_UQC_ADVTAX_GAUGES.md`](../plans/PLAN-004_GSTR1_TAB13_UQC_ADVTAX_GAUGES.md)  

---

## 1. Executive Summary & Problem Statement

### 1.1 User Problem
1. **GSTR-1 Portal Table 13 Rejection**:
   - Currently, `apps/api/app/services/gstr1_export_service.py` lumps all invoices into a single monolithic range in Table 13 (`Invoices for outward supply`).
   - If a business issues credit notes, debit notes, receipt vouchers, or delivery challans, or runs disjoint numbering series (e.g., `INV/2026/001` vs `CN/2026/001`), the GST portal flags discrepancy errors between Table 4/9B and Table 13, blocking GSTR-1 submission.
2. **UQC Invalidation on Services & Missing Unit Standards**:
   - `apps/web/src/app/invoices/new/page.tsx` lacks a standardized Unique Quantity Code (`UQC`) selector.
   - For services under Chapter 99 (e.g. `998314` software consulting), GSTN rules strictly require UQC to be `"NA"`. Any other unit causes portal rejection.
   - For goods, arbitrary text units (e.g., "boxes", "pkt") fail GSTN schema validation which requires standard 3-letter codes (`BOX`, `PAC`, `KGS`, `NOS`).
3. **Passive Advance Tax Calendar & Blind Penalty Exposure**:
   - In `apps/web/src/app/yearbook/page.tsx`, the Advance Tax calendar displays static text (`15% Adv Tax`, `45% Adv Tax`).
   - Corporate founders and accountants are not warned when installments fall short of safe-harbor thresholds (12% in Q1, 36% in Q2), leading to surprise Section 234C (deferment) and Section 234B (shortfall) interest penalties at 1% per month.

### 1.2 Proposed Solution
- **Automated GSTR-1 Table 13 Generation**: Auto-categorize active ledger documents by nature (`doc_num: 1` Outward Invoices, `4` Debit Notes, `5` Credit Notes, `6` Receipt Vouchers, `12` Delivery Challans) and compute prefix-aware serial ranges (`from`, `to`), total issued, cancelled, and net issued.
- **Strict UQC Enforcement in InvoiceForm**: Interactive unit selection adhering to 44+ GSTN UQC standards, with automatic lock to `"NA"` and quantity `1` when a Chapter 99 service HSN is selected.
- **Dynamic Advance Tax §234B/C Penalty Gauges**: Interactive gauges in Year Book calendar integrating with `/api/v1/compliance/advance-tax/forecast`, displaying target vs deposited amounts, safe-harbor compliance badges, and real-time interest penalty warnings.

---

## 2. RICE Prioritization & Scoring

$$\text{RICE Score} = \frac{\text{Reach} \times \text{Impact} \times \text{Confidence}}{\text{Effort}}$$

| Factor | Value | Rationale |
| :--- | :---: | :--- |
| **Reach (R)** | **500** | All monthly GSTR-1 filings and quarterly corporate tax installments across active tenant entities. |
| **Impact (I)** | **3.0 (Massive)** | Eliminates portal filing schema rejections and protects companies from statutory 12% to 24% p.a. interest penalties. |
| **Confidence (C)** | **95%** | GSTN JSON v3.x schema and Income Tax Act §208/234B/234C algorithms are fully verified and backed by existing service models. |
| **Effort (E)** | **1.5 Person-Weeks** | Phased across 4 milestones (Backend Table 13, Frontend UQC, Advance Tax Gauges, End-to-End Verification). |
| **TOTAL SCORE** | **950.0** | **Highest Priority statutory compliance initiative for sprint.** |

---

## 3. User Acceptance Criteria (UAC)

- [ ] **UAC-01 (Table 13 Nature of Document Grouping)**: Given an active ledger with 10 outward invoices, 2 credit notes, and 1 cancelled invoice, when GSTR-1 JSON is exported, then Table 13 (`doc_issue`) contains separate entries for `doc_num: 1` and `doc_num: 5`, each with exact serial ranges, cancelled counts, and net issued counts.
- [ ] **UAC-02 (Multi-Series Range Isolation)**: Given outward invoices using two different prefix series (`INV/2026/001` to `INV/2026/010` and `EXP/2026/001` to `EXP/2026/005`), Table 13 must emit two separate rows within `doc_num: 1` rather than an invalid concatenated range.
- [ ] **UAC-03 (Service HSN UQC Auto-Lock)**: When an invoice line item HSN/SAC is set to `998314` (or any `99xxxx`), the unit field automatically locks to `"NA"`, disables manual override, and displays a tooltip explaining GSTN Chapter 99 rules.
- [ ] **UAC-04 (Goods Standard UQC Dropdown)**: When an invoice line item HSN is set to goods (e.g., `84713010`), the unit dropdown offers searchable official GSTN codes (`NOS`, `BOX`, `KGS`, etc.) and disallows `"NA"`.
- [ ] **UAC-05 (Advance Tax Gauge Visualization)**: In the Year Book calendar, clicking June, September, December, or March displays a dynamic gauge showing Estimated Annual Tax, Cumulative Target, Actual Paid Challans, and Safe Harbor status.
- [ ] **UAC-06 (Section 234C/234B Penalty Warning)**: If advance tax deposited by September 15 is < 36% of estimated tax, the calendar card turns amber/red with badge `⚠ §234C Interest Accruing: ₹X` and provides an action to record challan ITNS 280.

---

## 4. Definition of Done (DoD)
- [x] Stage 2 Feature Spec approved
- [ ] Stage 3 Phased Implementation Plan co-authored with Planning Trio (`wiki/plans/PLAN-004_GSTR1_TAB13_UQC_ADVTAX_GAUGES.md`)
- [ ] Phased development on `feat/FEAT-GST-04-gstr1-tab13-uqc-advtax`
- [ ] Automated regression tests pass (100% green)
- [ ] Linter and TypeScript checks clean
- [ ] Ephemeral preview test verified via `bin/deploy-preview.sh`
- [ ] PR reviewed & approved by Engineering Manager (`@engineering-manager`)

