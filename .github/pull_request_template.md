<!--
  =============================================================================
  b00k5 PULL REQUEST TEMPLATE
  =============================================================================
  All changes must be submitted via a Pull Request against a feature/fix branch.
  DIRECT MERGES AND DIRECT COMMITS TO MAIN ARE STRICTLY PROHIBITED.
-->

## 📌 Change Summary & Motivation
<!-- Brief summary of what this PR introduces and the business or statutory rationale. -->

## 🔗 Wiki & Defect Tracker Traceability
- **Wiki Feature ID:** <!-- e.g., FEAT-LEDGER-01, FEAT-VAULT-04 (see wiki/FEATURE_REGISTRY.md) -->
- **Defect Tracker ID:** <!-- e.g., DEF-15, TAB-FY-03 (see wiki/DEFECT_TRACKER.md) or N/A -->
- **Change Log Entry:** <!-- Linked entry in wiki/CHANGE_LOG_REGISTER.md -->

## 🏷️ PR Type
- [ ] 🚀 `feat`: New feature or statutory capability
- [ ] 🐛 `fix`: Bug or defect remediation
- [ ] ♻️ `refactor`: Architectural cleanup / performance enhancement
- [ ] 📚 `docs`: Documentation, wiki, or OpenAPI update
- [ ] 🧪 `test`: New zero-mock integration or Selenium test
- [ ] 🛠️ `chore`: Build, dependency, or SRE deployment script

---

## 🏛️ Statutory Accounting Invariants Checklist
- [ ] **Ledger Mathematical Invariant:** $\left\vert{}\sum \text{Debits} - \sum \text{Credits}\right\vert{} \equiv 0.00$ enforced across all posted transactions.
- [ ] **Multi-Tenancy RLS:** Session-level PostgreSQL Row-Level Security (`SET LOCAL app.current_tenant` and `SET LOCAL app.current_user_role`) verified.
- [ ] **Indian Date Standard:** `dayfirst=True` (`DD/MM/YYYY`) format respected across all parsers, UI pickers, and statements.
- [ ] **Authentic Source Preservation:** Authentic binary uploads (PDFs, bank statements, ITRs) preserved in MinIO; zero synthetic overwrites.
- [ ] **Statutory Document Neutrality:** Customer-facing tax invoices, receipts, and MCA board minutes have **0 vendor watermarks** (tenant-owned).

---

## 🛡️ Open-Source Security & PII Protection Checklist
- [ ] **Zero Secret Leakage:** No private API keys, database passwords, JWT secrets, or cloud tokens committed.
- [ ] **Zero Founder PII:** No real PAN, Aadhaar, personal phone numbers, personal bank accounts, or residential addresses in code or tests.
- [ ] **Sanitized Synthetic Fixtures:** All tests use fictitious entities (e.g., `Apex Global Technologies Pvt Ltd`, `Acme Technologies Pvt Ltd`) with synthetic dummy PANs (`AABCA...`), CINs, and DINs.
- [ ] **Licensing Hygiene:** All third-party packages in `requirements.txt` or `package.json` are SPDX Apache 2.0 / MIT / BSD compatible.

---

## 🧪 Zero-Mock Verification Evidence
<!-- Provide the exact test command and proof of passing verification. -->
- **Test Command Executed:** `pytest <test_file_path> -v -s` or `./scripts/branch_deploy.sh <branch> --test`
- **Output Summary:**
```
[Paste terminal test summary here]
```
- **UI Screenshots / Artifacts (if UI affected):**
<!-- Link or attach screenshots verifying zero visual overlap, correct FY sync, and clutter-free design. -->

---

## 🎨 Quality of Life (QoL) & UI/UX Standards
- [ ] Interface is clean, intuitive, clutter-free, and adheres to staff ergonomics.
- [ ] Zero overlapping or clipped typography across different resolutions.
- [ ] Bidirectional FY synchronization verified across tabs.
- [ ] Error boundaries active with graceful recovery states.
