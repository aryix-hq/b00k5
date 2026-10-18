# FEAT-PAY-01: Sovereign Native Payroll & Double-Entry Ledger Integration

**Feature ID:** `FEAT-PAY-01`  
**Status:** Implemented (Verified via CI test suite)  
**Owner:** Engineering & Architecture  
**Statutory Basis:**
- **Companies Act, 2013:** Schedule III Division I (Statement of Profit & Loss Note 17: *Employee Benefits Expense*, Balance Sheet Note 7: *Other Current Liabilities*).
- **Accounting Standard 15 / Ind AS 19:** Employee Benefits (recognition of short-term employee benefits on accrual basis).
- **Income Tax Act, 1961:** Section 192 (Withholding tax on salaries under Finance Act 2024 New & Old regimes).
- **Employees' Provident Funds Act, 1952:** Section 6 (Statutory 12% contribution, EPS 8.33% capped at ₹1,250).
- **Employees' State Insurance Act, 1948:** Section 39 (0.75% employee, 3.25% employer contributions).

---

## 1. Scope & Objective

Implement an embedded, sovereign payroll module in `b00k5` that enables:
1. Management of employees with CTC structures (Basic, HRA, DA, Special Allowance, PF, ESI).
2. Calculation of monthly payroll runs with Loss of Pay (LOP) proration and statutory withholdings.
3. Automated posting of the 3-Leg General Ledger Journal Vouchers:
   - **Leg 1: Month-End Accrual:** Dr. Salaries (4020), Dr. Employer PF (4021), Dr. Employer ESI (4022) vs Cr. Net Salary Payable (2070), Cr. Employee PF (2071), Cr. Employer PF (2072), Cr. Employee ESI (2073), Cr. Employer ESI (2074), Cr. PT (2075), Cr. TDS 192 (2076).
   - **Leg 2: Bank Disbursement:** Dr. Net Salary Payable (2070) vs Cr. Bank Account (1010).
   - **Leg 3: Statutory Remittance:** Dr. Statutory Liabilities (2071-2076) vs Cr. Bank Account (1010).
4. Direct reflection in `ScheduleIIIService` (Note 17 P&L and Note 7 Balance Sheet).

---

## 2. Acceptance Criteria

- [x] Mathematical Double-Entry Invariant: $\left\vert\sum \text{Debits} - \sum \text{Credits}\right\vert \equiv 0.00$ on all generated payroll journal entries.
- [x] Fixed-point decimal math using `Decimal(15, 2)` and Banker's Rounding (`ROUND_HALF_EVEN`). Zero floating point representation.
- [x] PostgreSQL 16 Row-Level Security (RLS) isolation on all payroll tables (`tenant_id = app.current_company_id`).
- [x] P&L Statement Note 17 automatically groups `4020` (Salaries & Wages), `4021` & `4022` (Contribution to Provident and Other Funds), and `4023` (Staff Welfare).
- [x] Unpaid salaries in `2070` and statutory taxes in `2071-2076` automatically reflect in Schedule III Balance Sheet Current Liabilities (Note 7).
- [x] Zero third-party vendor watermarks on payslips.
- [x] Comprehensive unit and integration regression test suite (passed 6/6 tests).
