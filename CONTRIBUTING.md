# Contributing to b00k5

Thank you for your interest in contributing to **b00k5**! We welcome bug fixes, documentation improvements, new statutory compliance rules, and performance optimizations.

---

## 1. Code of Conduct & Core Architectural Tenets

When writing code for b00k5, all contributors must observe these non-negotiable principles:
1. **Mathematical Invariant:** Never introduce floating-point math into accounting pipelines. Always use `Decimal` with `ROUND_HALF_EVEN`. At no point may $\sum \text{Debits} \ne \sum \text{Credits}$.
2. **Transaction Immutability:** Posted transactions must never be modified or deleted via SQL `UPDATE` or `DELETE`. Adjustments must occur via reversing entries or credit notes.
3. **Multi-Tenant Security:** Never bypass PostgreSQL Row-Level Security (RLS). All database queries must run through the session dependency injecting `app.current_tenant_id`.

---

## 2. Developer Certificate of Origin (DCO)

All commits submitted to b00k5 must include a Developer Certificate of Origin (DCO) sign-off line, certifying that you have the right to submit the work under the Apache License 2.0.

Use the `-s` flag when committing:
```bash
git commit -s -m "feat(ledger): add Schedule III cash flow generator"
```
This appends the standard sign-off:
```
Signed-off-by: Your Name <your.email@example.com>
```

---

## 3. Local Development Setup

### 3.1 Prerequisites
* Docker & Docker Compose v2
* Python 3.11+
* Node.js 20+

### 3.2 Starting Local Environment
```bash
git clone https://github.com/your-org/b00k5.git
cd b00k5
./install.sh
```

### 3.3 Running the Test Suite
Before opening a pull request, verify that all accounting core and integration tests pass:
```bash
# Run full 12-Pillar General Ledger invariant test suite
docker exec b00k5_api pytest /app/tests/accounting_core

# Run master integration audit journeys
docker exec b00k5_api pytest /app/tests/integration/test_master_directive_audit.py

# Run web typechecking
npm --prefix apps/web run build
```

---

## 4. Branching & Commit Conventions

* **Branches:**
  * Feature branches: `feat/feature-name`
  * Bug fixes: `fix/bug-description`
  * Documentation: `docs/topic-name`
* **Conventional Commits:** Follow the Conventional Commits specification:
  * `feat(invoices): add support for SEZ zero-rated GST invoices`
  * `fix(reconcile): resolve bank charges duplicate matching`
  * `test(audit): add compound journal entry tests`
  * `docs(api): document multi-currency endpoints`

---

## 5. Submitting a Pull Request (PR)

1. Fork the repository and create your branch from `main`.
2. Ensure new features are accompanied by automated tests in `tests/accounting_core/` or `tests/integration/`.
3. Verify all tests pass with zero drift.
4. Submit your PR with a detailed description of the business rationale and test evidence.
