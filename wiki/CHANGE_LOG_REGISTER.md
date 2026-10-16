# b00k5 Change Log & Architecture Decision Register

This log provides an auditable, chronological record of all architectural modifications, statutory enhancements, defect remediations, and pull requests in `b00k5`.

---

## 📅 Chronological Change Register

### [2026-10-16] — Release `v1.0.4-ga`: Repository Public Readiness, PR Template & ARYIX Ecosystem
- **PR / Milestone:** `v1.0.4-ga`
- **Category:** `feat` / `chore` / `governance`
- **Author:** Sovereign Architecture & Product Engineering Working Group
- **Key Deliverables:**
  1. **Strict PR Protocol Established:** Direct pushes and merges to `main` prohibited. Enforced feature branching, [`.github/pull_request_template.md`](../.github/pull_request_template.md), and wiki traceability.
  2. **Branch Deploy Automation:** Implemented [`scripts/branch_deploy.sh`](../scripts/branch_deploy.sh) for safely deploying, testing, and verifying any branch against clean or isolated Docker stacks.
  3. **Engineering Wiki:** Established `wiki/` directory with `README.md`, `DEFECT_TRACKER.md` (DEF-01 to DEF-21), `FEATURE_REGISTRY.md`, and `DEVELOPMENT_WORKFLOW.md`.
  4. **Open-Source Secret & PII Sanitization:** Sanitized legacy CA firm names, membership numbers, and non-synthetic MCA SRNs into generic synthetic placeholders.
  5. **ARYIX Branding & Founder Manifesto:** Implemented interactive `AboutModal.tsx` featuring the Sovereign Accounting Manifesto by Adithya Khamithkar and the Community vs Enterprise support matrix.
  6. **Statutory Document Neutrality:** Certified that customer invoices, receipts, and MCA board minutes have zero third-party vendor watermarks.
  7. **Clean Database Reset:** Destroyed legacy dirty state (`docker compose down -v`) and initialized pristine environment from `init_schema.sql`.

---

### [2026-10-15] — Release `v1.0.3`: Statutory Backup Policy & Disaster Recovery
- **PR / Milestone:** `v1.0.3`
- **Category:** `feat` / `sre`
- **Key Deliverables:**
  1. Authoring and formalization of [`docs/BACKUP_AND_DISASTER_RECOVERY_POLICY.md`](../docs/BACKUP_AND_DISASTER_RECOVERY_POLICY.md) (10-year retention under CA 2013 §128(5), IT Act §44AA/§149, CGST Act §36).
  2. Automated disaster recovery verification script (`scripts/dr_drill.py`) verifying RTO < 30s and zero ledger drift.
  3. Head-to-head competitive benchmark documentation [`docs/COMPETITIVE_BENCHMARK.md`](../docs/COMPETITIVE_BENCHMARK.md) against Tally, Zoho, QuickBooks, and ClearTax.

---

### [2026-10-14] — Release `v1.0.2`: Tab & FY Desynchronization Audit Remediations
- **PR / Milestone:** `v1.0.2`
- **Category:** `fix` / `ui`
- **Key Deliverables:**
  1. Fixed governance and yearbook tab desynchronization upon financial year switching.
  2. Vault segregation into Permanent Legal Anchors and Annual Statutory Documents.
  3. Deduplication of INC-20A Commencement of Business records.
  4. Expanded multi-line service item description box on invoices.
  5. Multi-tenant IAM profile penetration testing with Selenium (`test_selenium_iam_multitenant_profiles.py`).

---

### [2026-10-12] — Release `v1.0.1`: Core MCA Secretarial Governance & Hardened Ledger
- **PR / Milestone:** `v1.0.1`
- **Category:** `feat` / `statutory`
- **Key Deliverables:**
  1. 120-Day Board Meeting Interval Watchdog under Companies Act Section 173(1) and ICSI SS-1.
  2. Form DPT-3 loan declaration generator for director reimbursements.
  3. Hardware PKCS#11 DSC signing bridge integration on port 28045.
  4. Schedule III Division I statutory financial statements export with Banker's Rounding.
