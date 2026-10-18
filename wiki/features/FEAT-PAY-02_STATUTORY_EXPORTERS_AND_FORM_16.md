# FEAT-PAY-02: Statutory Portals Exporter Suite & Section 192 Form 16 Engine

**Feature ID:** `FEAT-PAY-02`  
**Status:** Implemented (Verified via 17/17 payroll test suites)  
**Owner:** Engineering & Architecture  
**Statutory Basis:**
- **Income Tax Act, 1961:** Section 192 (Tax deduction at source from salaries), Section 203 (Requirement to furnish certificate of tax deducted - Form 16 Part A and Part B), Section 115BAC (New Tax Regime as amended by Finance Act 2024).
- **Employees' Provident Funds and Miscellaneous Provisions Act, 1952:** Section 6, EPF Scheme 1952 Paragraph 38 (Monthly Electronic Challan cum Return / ECR 2.0 electronic text return).
- **Employees' State Insurance Act, 1948:** Section 39, 40, 44 & Regulation 26 (Monthly IP portal return data file).
- **State Professional Tax Acts:** Karnataka Tax on Professions, Trades, Callings and Employments Act 1976 (Form 5 Monthly Return) and corresponding State Acts (Maharashtra Form III-B).

---

## 1. Scope & Objective

Enable 1-click generation and export of official statutory filing artifacts directly from calculated and locked payroll runs:

1. **EPFO Unified Portal ECR 2.0 Text File Exporter:**
   - Format: Official `#~#` pipe-delimited format matching EPFO Shram Suvidha / Unified Member Portal specifications.
   - 11 fields per record: UAN, Member Name, Gross Wages, EPF Wages (capped at ₹15,000), EPS Wages (capped at ₹15,000; 0 for age > 58), EDLI Wages (capped at ₹15,000), EE Share (12%), EPS Share (8.33%, max ₹1,250), ER Share (3.67%), NCP (Non-Contributing Days / LOP), Refund of Advances.
2. **ESIC Monthly Return Portal Exporter:**
   - Format: Standard CSV upload for the ESIC Insurance Person (IP) Portal.
   - Fields: 10-digit IP Number, IP Name, Working Days for which wages were paid, Total Gross Monthly Wages, Reason Code for zero wages (if any), Last Working Day.
3. **State Professional Tax (PT) Form 5 Return Summary:**
   - Aggregate monthly PT deductions by state (Karnataka Form 5, Maharashtra Form III-B) with wage slab distribution, employee headcounts, and total liability.
4. **Section 192 Form 16 Part A/B Digital Certificate Generator:**
   - Detailed annual salary and tax computation engine:
     - Part A: Employer TAN/PAN, Employee PAN, Period of Employment, Quarterly TDS deposit verification.
     - Part B: Gross salary breakdown under Section 17(1), standard deduction (₹75,000 for New Regime, ₹50,000 for Old Regime), Chapter VI-A deductions (80C, 80D, 24b), total taxable income, tax calculation, Section 87A rebate, 4% Health & Education Cess, and net tax deducted.
   - Certified PDF generation with professional typography and digital signature placement.

---

## 2. Acceptance Criteria

- [x] EPFO ECR text format strictly follows `#~#` delimiter rules with 11 fields per active contributing employee.
- [x] Wage ceiling rules correctly applied: EPF, EPS, and EDLI wages capped at ₹15,000 unless `is_pf_capped=False`.
- [x] EPS share capped at ₹1,250 prorated for paid days; ER share calculated as `EE Share - EPS Share`.
- [x] ESIC export CSV adheres to the ESIC portal template with 10-digit IP numbers.
- [x] Form 16 Part A/B computes precise annualized tax matching `PayrollService.calculate_statutory_tds_192` with zero rounding drift.
- [x] PDF generation is byte-exact, readable, and downloads with appropriate `Content-Disposition` headers.
- [x] All exporter routes protected with Tenant Row-Level Security (`tenant_id = app.current_company_id`) and role access control (`require_ca_or_owner`).
- [x] Full automated test suite passes with zero regressions (4/4 statutory tests passing).
