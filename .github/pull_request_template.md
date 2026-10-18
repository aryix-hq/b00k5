<!--
  PULL REQUEST TEMPLATE
  MANDATORY: No code may be merged directly to main without this PR template
  filled, automated preview tests passed, and explicit Engineering Manager (EM) approval.
-->

## 1. Ticket & Summary
- **Wiki Ticket**: `[FEAT-XXX | DEF-XXX]` (e.g. `wiki/features/FEAT-042.md`)
- **Title**: `feat(scope): Description` or `fix(scope): Description`
- **Summary of Changes**:
  [Provide a concise explanation of what this PR does and why.]

---

## 2. Model & Execution Tier
- [ ] **Implementation Tier**: Ran on lightweight models (`flash` / local Ollama)
- [ ] **Review Gates**:
  - [ ] System Architect sign-off (`pro` model) — *Required if schemas/contracts changed*
  - [ ] CISO / Security sign-off (`pro` model) — *Required if auth/network/PII touched*

---

## 3. Automated Preview & Live Testing Evidence
- [ ] **Local Syntax Check**: Passed (`node --check` / `tsc --noEmit` / `python -m py_compile`)
- [ ] **Preview Deploy Script Executed**: `./bin/deploy-preview.sh <branch> <port>`
- **Live Test Results**:
  ```text
  [Paste zero-mock test run output / HTTP healthcheck response here]
  ```

---

## 4. Documentation & Standards Checklist
- [ ] `CHANGELOG.md` updated under `[Unreleased]` with Keep a Changelog syntax
- [ ] Relevant `wiki/` documentation (specs, ADRs, or defect records) updated
- [ ] Zero secrets, unmasked PII, or credentials committed
- [ ] No floating-point math introduced into financial ledgers

---

## 5. Engineering Manager (EM) Approval Gate
> **NOTICE**: Direct pushes or merges to `main` are strictly forbidden. Merging is blocked until the EM signs off below.

- [ ] **Engineering Manager Peer Review Sign-Off**:
  - **Reviewer**: `@engineering-manager`
  - **Verdict**: `APPROVED`
  - **Approval Date**: `YYYY-MM-DD`
  - **Notes / Conditions**: [None]
