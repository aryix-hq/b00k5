# Stage 2: Product Feature Spec — Stakeholder-Centric Auditor Dossier & Dual-Plane BCP/DR Backup Hierarchy
**Feature ID**: FEAT-OPS-06  
**Module**: Storage, Auditing, Corporate Governance, Disaster Recovery  
**Status**: Ready for Planning  
**RICE Score**: Reach: 100% | Impact: Massive (5) | Confidence: 95% | Effort: 3 Sprints = High Priority  

---

## 1. Feature Overview
Restructures both the standalone **Auditor Dossier Export** (.zip) and the off-site **Cloud Backup Engine** (Cloudflare R2, AWS S3, Google Drive, MinIO) into a role-aligned, 9-section statutory hierarchy catering to:
1. **Founders & Managing Directors**: Instant due diligence packages, KYC readiness, and compliance scorecards.
2. **CFOs**: Audited financials, cash flows, BRS banking reconciliations, and vendor ageing.
3. **Chartered Accountants (CAs)**: Schedule III Balance Sheet, P&L, Notes 1–22, Trial Balance, GSTR-9/3B reconciliations, and Form 26AS/AIS.
4. **Company Secretaries (CS)**: Secretarial Standards SS-1 (Board Meetings), SS-2 (AGM), MCA Annual Filings (AOC-4, MGT-7/7A with SRN challans), and statutory registers.
5. **External Auditors**: CARO 2020 verification, sales and purchase vouching with ITC registers, Section 128 audit trail proofs, and cryptographic SHA-256 manifests.
6. **SRE / DevOps**: Atomic machine-readable checkpoints (`checkpoints/CP-{TIMESTAMP}/`) guaranteeing $RTO < 10 \text{ min}$ with zero broken object keys.

---

## 2. User Stories & Acceptance Criteria

### User Story 1 (Auditor Dossier Zip Structure)
- *As an external auditor, CA, or CS*, when I download the Auditor Dossier for a Financial Year from the Year Book or Settings console, I must receive a `.zip` file organized into 9 numbered top-level folders reflecting statutory personas.
- **Acceptance Criteria**:
  1. `00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/` contains corporate identity, executive briefing, compliance health scorecard, and permanent registrations (COI, MOA, AOA, PAN, TAN, GST REG-06, ADT-1).
  2. `01_STATUTORY_FINANCIAL_STATEMENTS_SCHEDULE_III/` contains Schedule III Balance Sheet, P&L, Cash Flow, Notes 1–22, Audited Trial Balance, and CARO 2020 report.
  3. `02_CORPORATE_GOVERNANCE_AND_SECRETARIAL_MCA/` contains SS-1 Board Minutes, SS-2 AGM Minutes, AOC-4, MGT-7/7A, and CA2013 statutory registers.
  4. `03_TAX_COMPLIANCE_AND_STATUTORY_RETURNS/` contains GST (GSTR-1, 3B, 9), Direct Tax (ITR-6, 26AS, AIS/TIS, Advance Tax), and TDS (24Q, 26Q, 16, 16A).
  5. `04_BANKING_CASH_AND_TREASURY_RECONCILIATION/` contains all bank statements, BRS statements, and CMS payment logs.
  6. `05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/` contains monthly outward tax invoices and debtors ageing.
  7. `06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/` contains monthly inward bills, expense vouchers, ITC registers, and creditors ageing.
  8. `07_PAYROLL_PERSONNEL_AND_LABOR_LAW_COMPLIANCE/` contains monthly salary registers, EPFO ECR challans, ESIC challans, and contractor 194J/194C summaries.
  9. `08_AUDIT_TRAIL_AND_CRYPTOGRAPHIC_INTEGRITY/` contains the Section 128 Audit Trail Certificate, MCA statutory checklist, and `AUDIT_AUTHENTICITY_MANIFEST_SHA256.txt`.

### User Story 2 (Dual-Plane Cloud Storage & BCP Mirror)
- *As a DevOps engineer / SRE*, when cloud sync executes to Cloudflare R2 / AWS S3:
  1. Machine-Plane: The backup worker writes atomic checkpoints into `checkpoints/CP-{TIMESTAMP}/` containing `postgres_state.dump.enc`, `minio_raw_storage.tar.gz`, and `CHECKPOINT_MANIFEST.json`.
  2. Human-Plane: The backup worker mirrors files into `{Tenant_Legal_Name}_({CIN_or_PAN})/` using the canonical `FY {YYYY}-{YY} (AY {YYYY+1}-{YY+1})` and 9-stakeholder layout.
  3. Retention policy: Automatically purges old checkpoints per policy without mutating statutory audit or tax folders.

---

## 3. Scope Boundaries
- In-scope:
  - `apps/api/app/services/auditor_dossier_service.py`
  - `apps/api/app/api/v1/storage.py`
  - `apps/api/app/services/s3_mirror_client.py`
  - `apps/api/app/services/gdrive_virtualizer.py`
  - Unit and integration tests in `apps/api/tests/test_storage_and_sync.py` and `test_s3_remote_mirror.py`
- Out-of-scope:
  - Direct modifications to live production database or MinIO volume storage outside the tenant isolation boundary.

