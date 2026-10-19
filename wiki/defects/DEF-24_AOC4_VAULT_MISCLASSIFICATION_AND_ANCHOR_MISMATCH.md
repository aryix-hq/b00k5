# DEF-24: Form AOC-4 Vault Misclassification, SRN Truncation & Statutory Anchor Discrepancy

**Defect ID:** `DEF-24`  
**Module:** `vault` / `statutory_anchor` / `schedule_iii` / `yearbook`  
**Severity:** 🔴 Critical  
**Status:** **FIXED**  
**Resolution Verification:** `tests/test_roc_compliance_and_esign.py::test_authentic_aoc4_schedule_iii_extraction_and_equilibrium`, UI Verification Screenshots

---

## 1. Problem Description
A discrepancy was identified between uploaded authentic MCA Form AOC-4 documents in the Document Vault and the figures rendered in Year Book Schedule III Financial Statements:
1. **Misclassification of Auditor Report Extract as Form AOC-4**:
   - Uploaded standalone Auditor's Report extract documents were misclassified as `aoc_4` because their cover declaration page contained the statutory caption `"ATTACHED WITH FORM AOC-4"`.
   - The smart-ingest de-duplication logic overwrote the authentic filed Form AOC-4 financial statement record in `DocumentVault`.
2. **Synthetic Fallback Due to Missing Line Items**:
   - Because the standalone Auditor's Report extract contained no balance sheet line-item tables, the system fell back to synthetic dummy values:
     - Tangible Assets / Property, Plant & Equipment (`1050`): Omitted / Zero
     - Cash and Bank Balances (`1010`): Omitted / Zero
     - Long-Term Borrowings (`2030`): Injected synthetic plug
     - Other Current Liabilities (`2050`): Omitted / Zero
     - P&L line-item breakdown (Finance Costs `4020`, Depreciation `4030`, Other Expenses `4040`): Collapsed or unpopulated
3. **MCA V3 SRN Truncation**:
   - MCA V3 11-digit alphanumeric Service Request Numbers were truncated due to an aggressive prefix-stripping rule.
4. **Single-Bucket MinIO Scope**:
   - Storage manager sync routines only inspected general vault buckets, omitting statutory e-filing buckets.

---

## 2. Head-by-Head Structural Extraction Comparison

| Schedule III Head / Metadata | Authentic Form AOC-4 Source | Previous System State | Remediated Status |
| :--- | :--- | :--- | :--- |
| **Service Request Number (SRN)** | Authentic MCA V3 SRN | Truncated digits | **Full 11-digit MCA V3 SRN Preserved** |
| **Filing Date** | Extracted from eForm Filing Date | Default / Ingestion Date | **Authentic Government Filing Date** |
| **Share Capital (`2010`)** | Extracted from Part I (BS) | Default value | **Authentic Filed Figure** |
| **Reserves & Surplus (`2020`)** | Extracted from Part I (BS) | Default value | **Authentic Filed Figure** |
| **Long-Term Borrowings (`2030`)** | Extracted from Non-Current Liab | Synthetic balancing plug | **Authentic Filed Figure** |
| **Other Current Liabilities (`2050`)** | Extracted from Current Liab | Omitted / Zero | **Authentic Filed Figure** |
| **Property, Plant & Equip (`1050`)** | Extracted from Non-Current Assets | Omitted / Zero | **Authentic Filed Figure** |
| **Cash & Cash Equivalents (`1010`)** | Extracted from Current Assets | Omitted / Zero | **Authentic Filed Figure** |
| **Other Income (`3020`)** | Extracted from Part II (P&L) | Omitted / Zero | **Authentic Filed Figure** |
| **Finance Costs (`4020`)** | Extracted from Part II (P&L) | Omitted / Zero | **Authentic Filed Figure** |
| **Depreciation & Amortisation (`4030`)** | Extracted from Part II (P&L) | Omitted / Zero | **Authentic Filed Figure** |
| **Other Expenses (`4040`)** | Extracted from Part II (P&L) | Lump-sum fallback | **Authentic Filed Figure** |
| **Balance Sheet Drift** | $|\text{Assets} - \text{Liabilities}| \equiv 0.00$ | Unbalanced / Distorted | **Zero Mathematical Drift Verified** |

---

## 3. Root Cause Analysis
1. **Classification Heuristics**:
   - `StatutoryVaultEngine.classify_statutory_filing` checked for `"FORM AOC-4"` without negative lookaheads for `"EXTRACT OF AUDITOR"`.
   - Auditors attach a cover sheet stating `"ATTACHED WITH FORM AOC-4"`, which triggered a false-positive classification.
2. **MCA V3 SRN Parsing**:
   - V3 MCA SRNs carry the structure `1-XXXXXXXXXXX`. An erroneous `.replace("1-2", "")` string manipulation stripped valid characters.
3. **Multi-Bucket Architecture**:
   - MinIO maintains segregated buckets: general documents and statutory e-forms. Probing only the general bucket failed to locate newly ingested MCA filings.
4. **Permanent Account Roll-Forward**:
   - `ScheduleIIIService` roll-forward logic accounted for borrowings and reserves but omitted `other_current_liabilities`, creating roll-forward imbalances when prior years carried statutory payables.

---

## 4. Remediations Implemented
1. **`apps/api/app/services/statutory_vault_engine.py`**:
   - Added negative lookahead excluding `EXTRACT OF AUDITOR` from matching `aoc_4`.
   - Preserved full MCA V3 SRNs without character stripping.
   - Extracted authentic eForm filing date (`DD/MM/YYYY`).
   - Upgraded regex patterns for all Schedule III balance sheet and P&L line heads (handling hyphenation, parenthesized numbering, and multi-line formatting).
2. **`apps/api/app/services/statutory_anchor_service.py`**:
   - Implemented dual-bucket search across both statutory and general vault buckets.
   - Enhanced deduplication to prioritize complete authentic AOC-4 forms over auditor extracts.
   - Automatically updated anchors when authentic payloads with full Schedule III lines are parsed.
3. **`apps/api/app/services/schedule_iii_service.py`**:
   - Added `other_current_liabilities` to permanent account roll-forward.
4. **Database Calibration**:
   - Updated document vault taxonomy and titles to distinguish Form AOC-4 from Independent Auditor's Report Extracts.
   - Re-anchored statutory baseline with complete line-item coverage.

---

## 5. Verification & Mathematical Invariants
- **Automated Test Suite**:
  - `apps/api/tests/test_roc_compliance_and_esign.py::test_authentic_aoc4_schedule_iii_extraction_and_equilibrium` validates parser accuracy and mathematical equilibrium.
  - Full API regression suite: **51 passed, 4 skipped, 0 failed**.
- **Double-Entry Equilibrium Invariant**:
  $$\left|\text{Total Assets} - \text{Total Equity \& Liabilities}\right| \equiv 0.00$$
  - Historical Baseline Period: $\text{Drift} \equiv 0.00$
  - Current Operating Period: $\text{Drift} \equiv 0.00$
  - Comparative Balance Sheet Columns: $\text{Drift} \equiv 0.00$
- **Visual Verification**:
  - Confirmed UI rendering in Year Book Schedule III viewer and Document Vault annual filings repository.
