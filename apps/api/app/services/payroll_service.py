from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import json
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.payroll import Employee, SalaryStructure, PayrollRun, Payslip, EmployeeTaxDeclaration
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService


def round_curr(val: Any) -> Decimal:
    """Rounds an amount to 2 decimal places using Banker's Rounding (ROUND_HALF_EVEN)."""
    d = Decimal(str(val or 0.0))
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


class PayrollService:

    @staticmethod
    def calculate_statutory_tds_192(
        projected_annual_gross: Decimal,
        regime: str = "new_115bac",
        verified_80c: Decimal = Decimal("0.00"),
        verified_80d: Decimal = Decimal("0.00"),
        verified_24b: Decimal = Decimal("0.00")
    ) -> Decimal:
        """
        Calculates annual TDS on Salaries under Section 192 of Income Tax Act, 1961.
        Returns the annualized tax amount (including 4% Health & Education Cess).
        """
        if regime == "new_115bac":
            # New Tax Regime (Section 115BAC as per Budget 2024 / FY 2025-26 & 2026-27)
            # Standard Deduction: Rs 75,000
            std_deduction = Decimal("75000.00")
            taxable_income = max(Decimal("0.00"), projected_annual_gross - std_deduction)

            # Section 87A Full Rebate if taxable income <= 7,00,000
            if taxable_income <= Decimal("700000.00"):
                return Decimal("0.00")

            # Progressive Slabs:
            # 0 - 3,00,000: Nil
            # 3,00,001 - 7,00,000: 5%
            # 7,00,001 - 10,00,000: 10%
            # 10,00,001 - 12,00,000: 15%
            # 12,00,001 - 15,00,000: 20%
            # Above 15,00,000: 30%
            tax = Decimal("0.00")
            if taxable_income > Decimal("1500000.00"):
                tax += (taxable_income - Decimal("1500000.00")) * Decimal("0.30")
                taxable_income = Decimal("1500000.00")
            if taxable_income > Decimal("1200000.00"):
                tax += (taxable_income - Decimal("1200000.00")) * Decimal("0.20")
                taxable_income = Decimal("1200000.00")
            if taxable_income > Decimal("1000000.00"):
                tax += (taxable_income - Decimal("1000000.00")) * Decimal("0.15")
                taxable_income = Decimal("1000000.00")
            if taxable_income > Decimal("700000.00"):
                tax += (taxable_income - Decimal("700000.00")) * Decimal("0.10")
                taxable_income = Decimal("700000.00")
            if taxable_income > Decimal("300000.00"):
                tax += (taxable_income - Decimal("300000.00")) * Decimal("0.05")

            # 4% Health & Education Cess
            tax_with_cess = tax * Decimal("1.04")
            return round_curr(tax_with_cess)

        else:
            # Old Tax Regime
            std_deduction = Decimal("50000.00")
            ded_80c = min(verified_80c, Decimal("150000.00"))
            ded_80d = min(verified_80d, Decimal("25000.00"))
            ded_24b = min(verified_24b, Decimal("200000.00"))
            total_deductions = std_deduction + ded_80c + ded_80d + ded_24b

            taxable_income = max(Decimal("0.00"), projected_annual_gross - total_deductions)

            # Section 87A rebate if taxable income <= 5,00,000
            if taxable_income <= Decimal("500000.00"):
                return Decimal("0.00")

            tax = Decimal("0.00")
            if taxable_income > Decimal("1000000.00"):
                tax += (taxable_income - Decimal("1000000.00")) * Decimal("0.30")
                taxable_income = Decimal("1000000.00")
            if taxable_income > Decimal("500000.00"):
                tax += (taxable_income - Decimal("500000.00")) * Decimal("0.20")
                taxable_income = Decimal("500000.00")
            if taxable_income > Decimal("250000.00"):
                tax += (taxable_income - Decimal("250000.00")) * Decimal("0.05")

            tax_with_cess = tax * Decimal("1.04")
            return round_curr(tax_with_cess)

    @staticmethod
    def calculate_professional_tax(gross_earnings: Decimal, state: str = "Karnataka", month: int = 4) -> Decimal:
        """
        Calculates State-Specific Professional Tax (PT).
        """
        state_clean = (state or "Karnataka").strip().lower()
        if "karnataka" in state_clean:
            # Karnataka: Gross >= Rs 25,000 -> Rs 200/mo, else Nil
            return Decimal("200.00") if gross_earnings >= Decimal("25000.00") else Decimal("0.00")
        elif "maharashtra" in state_clean:
            # Maharashtra: >10k -> 200/mo (300 in Feb), >7.5k -> 175/mo
            if gross_earnings > Decimal("10000.00"):
                return Decimal("300.00") if month == 2 else Decimal("200.00")
            elif gross_earnings > Decimal("7500.00"):
                return Decimal("175.00")
            return Decimal("0.00")
        elif "delhi" in state_clean or "haryana" in state_clean or "rajasthan" in state_clean:
            return Decimal("0.00")
        else:
            # Default fallback (Rs 200 if gross >= 25,000)
            return Decimal("200.00") if gross_earnings >= Decimal("25000.00") else Decimal("0.00")

    @staticmethod
    def calculate_employee_payslip(
        employee: Employee,
        structure: SalaryStructure,
        total_days: int = 30,
        paid_days: Decimal = Decimal("30.00"),
        loss_of_pay_days: Decimal = Decimal("0.00"),
        month: int = 4,
        year: int = 2026,
        tax_declaration: Optional[EmployeeTaxDeclaration] = None
    ) -> Dict[str, Decimal]:
        """
        Calculates itemized payslip components with proration, EPF, ESI, PT, and Section 192 TDS.
        """
        proration = Decimal(str(paid_days)) / Decimal(str(total_days))

        # 1. Earned Components
        basic_earned = round_curr(structure.monthly_basic * proration)
        hra_earned = round_curr(structure.monthly_hra * proration)
        da_earned = round_curr(structure.monthly_da * proration)
        conveyance_earned = round_curr(structure.monthly_conveyance * proration)
        med_earned = round_curr(structure.monthly_medical_allowance * proration)
        special_allowance_earned = round_curr(structure.monthly_special_allowance * proration)

        gross_earnings = basic_earned + hra_earned + da_earned + conveyance_earned + med_earned + special_allowance_earned

        # 2. Provident Fund (EPF Act, 1952)
        pf_wages = basic_earned + da_earned
        if employee.pf_opt_out:
            emp_pf = Decimal("0.00")
            empr_pf = Decimal("0.00")
            empr_eps = Decimal("0.00")
            empr_edli = Decimal("0.00")
        else:
            if employee.is_pf_capped:
                effective_pf_wage = min(pf_wages, round_curr(Decimal("15000.00") * proration))
            else:
                effective_pf_wage = pf_wages

            emp_pf = round_curr(effective_pf_wage * Decimal("0.12"))
            
            # EPS: 8.33% capped at Rs 1,250 * proration
            eps_limit = round_curr(Decimal("1250.00") * proration)
            empr_eps = min(round_curr(effective_pf_wage * Decimal("0.0833")), eps_limit)
            
            # Employer EPF: 3.67% + excess above EPS cap
            empr_pf = emp_pf - empr_eps
            
            # EDLI: 0.50% capped at Rs 75 * proration
            edli_limit = round_curr(Decimal("75.00") * proration)
            empr_edli = min(round_curr(effective_pf_wage * Decimal("0.005")), edli_limit)

        # 3. Employee State Insurance (ESI Act, 1948)
        # Wage ceiling is Rs 21,000 monthly gross
        if employee.is_esi_eligible or gross_earnings <= Decimal("21000.00"):
            emp_esi = round_curr(gross_earnings * Decimal("0.0075"))
            empr_esi = round_curr(gross_earnings * Decimal("0.0325"))
        else:
            emp_esi = Decimal("0.00")
            empr_esi = Decimal("0.00")

        # 4. Professional Tax
        pt = PayrollService.calculate_professional_tax(gross_earnings, employee.pt_state, month)

        # 5. TDS Section 192
        projected_annual_gross = gross_earnings * Decimal("12")
        v_80c = tax_declaration.sec_80c_total_verified if tax_declaration else Decimal("0.00")
        v_80d = (tax_declaration.sec_80d_self_family + tax_declaration.sec_80d_parents) if tax_declaration else Decimal("0.00")
        v_24b = tax_declaration.sec_24b_home_loan_interest if tax_declaration else Decimal("0.00")

        annual_tds = PayrollService.calculate_statutory_tds_192(
            projected_annual_gross=projected_annual_gross,
            regime=employee.tax_regime,
            verified_80c=v_80c,
            verified_80d=v_80d,
            verified_24b=v_24b
        )
        monthly_tds = round_curr(annual_tds / Decimal("12"))

        # 6. Deductions & Net Pay
        lwf = Decimal("0.00")
        other_deductions = Decimal("0.00")
        total_deductions = emp_pf + emp_esi + pt + monthly_tds + lwf + other_deductions
        net_salary = gross_earnings - total_deductions

        return {
            "basic_earned": basic_earned,
            "hra_earned": hra_earned,
            "da_earned": da_earned,
            "conveyance_earned": conveyance_earned,
            "special_allowance_earned": special_allowance_earned,
            "bonus_or_arrears": Decimal("0.00"),
            "gross_earnings": gross_earnings,
            "employee_pf": emp_pf,
            "employee_esi": emp_esi,
            "professional_tax": pt,
            "tds_deducted": monthly_tds,
            "lwf_deducted": lwf,
            "other_deductions": other_deductions,
            "total_deductions": total_deductions,
            "net_salary": net_salary,
            "employer_pf": empr_pf,
            "employer_eps": empr_eps,
            "employer_esi": empr_esi,
            "employer_edli": empr_edli,
            "paid_days": paid_days,
            "loss_of_pay_days": loss_of_pay_days,
            "total_days": Decimal(str(total_days))
        }

    @staticmethod
    async def calculate_payroll_run(session: AsyncSession, run_id: uuid.UUID) -> PayrollRun:
        """
        Executes monthly payroll computation for all active employees and generates itemized payslips.
        """
        stmt = select(PayrollRun).where(PayrollRun.id == run_id)
        res = await session.execute(stmt)
        run = res.scalar_one_or_none()
        if not run:
            raise ValueError(f"PayrollRun with ID {run_id} not found.")

        if run.status in ["locked", "disbursed", "sealed"]:
            raise ValueError(f"Cannot recalculate payroll run in '{run.status}' state.")

        # Load active employees for tenant
        emp_stmt = select(Employee).where(
            and_(
                Employee.tenant_id == run.tenant_id,
                Employee.status.in_(["active", "on_notice"])
            )
        )
        emp_res = await session.execute(emp_stmt)
        employees = emp_res.scalars().all()

        # Clean existing payslips for draft run
        existing_payslips_stmt = select(Payslip).where(Payslip.payroll_run_id == run.id)
        existing_payslips = (await session.execute(existing_payslips_stmt)).scalars().all()
        for p in existing_payslips:
            await session.delete(p)
        await session.flush()

        tot_employees = 0
        tot_gross = Decimal("0.00")
        tot_deductions = Decimal("0.00")
        tot_net = Decimal("0.00")
        tot_empr_pf = Decimal("0.00")
        tot_empr_esi = Decimal("0.00")
        tot_tds = Decimal("0.00")
        tot_pt = Decimal("0.00")

        # Determine total days in month
        import calendar
        _, total_days = calendar.monthrange(run.year, run.month)

        for emp in employees:
            # Fetch active salary structure
            struct_stmt = select(SalaryStructure).where(
                and_(
                    SalaryStructure.employee_id == emp.id,
                    SalaryStructure.is_active == True
                )
            ).order_by(SalaryStructure.effective_from.desc())
            struct_res = await session.execute(struct_stmt)
            structure = struct_res.scalars().first()
            if not structure:
                continue

            # Fetch tax declaration if exists
            tax_stmt = select(EmployeeTaxDeclaration).where(
                and_(
                    EmployeeTaxDeclaration.employee_id == emp.id,
                    EmployeeTaxDeclaration.fiscal_year == run.fiscal_year
                )
            )
            tax_decl = (await session.execute(tax_stmt)).scalars().first()

            # Default full month (30/31 days) unless LOP specified
            paid_days = Decimal(str(total_days))
            comp = PayrollService.calculate_employee_payslip(
                employee=emp,
                structure=structure,
                total_days=total_days,
                paid_days=paid_days,
                loss_of_pay_days=Decimal("0.00"),
                month=run.month,
                year=run.year,
                tax_declaration=tax_decl
            )

            payslip = Payslip(
                id=uuid.uuid4(),
                tenant_id=run.tenant_id,
                payroll_run_id=run.id,
                employee_id=emp.id,
                payslip_number=f"SLIP-{run.run_number}-{emp.employee_code}",
                total_days=total_days,
                paid_days=comp["paid_days"],
                loss_of_pay_days=comp["loss_of_pay_days"],
                basic_earned=comp["basic_earned"],
                hra_earned=comp["hra_earned"],
                da_earned=comp["da_earned"],
                conveyance_earned=comp["conveyance_earned"],
                special_allowance_earned=comp["special_allowance_earned"],
                bonus_or_arrears=comp["bonus_or_arrears"],
                gross_earnings=comp["gross_earnings"],
                employee_pf=comp["employee_pf"],
                employee_esi=comp["employee_esi"],
                professional_tax=comp["professional_tax"],
                tds_deducted=comp["tds_deducted"],
                lwf_deducted=comp["lwf_deducted"],
                other_deductions=comp["other_deductions"],
                total_deductions=comp["total_deductions"],
                net_salary=comp["net_salary"],
                employer_pf=comp["employer_pf"],
                employer_eps=comp["employer_eps"],
                employer_esi=comp["employer_esi"],
                employer_edli=comp["employer_edli"],
                payout_status="unpaid"
            )
            session.add(payslip)

            tot_employees += 1
            tot_gross += comp["gross_earnings"]
            tot_deductions += comp["total_deductions"]
            tot_net += comp["net_salary"]
            tot_empr_pf += (comp["employer_pf"] + comp["employer_eps"] + comp["employer_edli"])
            tot_empr_esi += comp["employer_esi"]
            tot_tds += comp["tds_deducted"]
            tot_pt += comp["professional_tax"]

        run.total_employees = tot_employees
        run.total_gross_pay = tot_gross
        run.total_deductions = tot_deductions
        run.total_net_pay = tot_net
        run.total_employer_pf = tot_empr_pf
        run.total_employer_esi = tot_empr_esi
        run.total_tds_192 = tot_tds
        run.total_pt = tot_pt
        run.status = "calculated"

        await session.flush()
        return run

    @staticmethod
    async def post_accrual_journal(
        session: AsyncSession,
        run_id: uuid.UUID,
        created_by_user_id: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Posts Leg 1 (Month-End Salary Accrual) Journal Voucher to the General Ledger.
        Dr. 4020 Salaries & Wages Expense
        Dr. 4021 Employer Contribution to PF
        Dr. 4022 Employer Contribution to ESI
        Cr. 2070 Salaries & Wages Payable (Net Pay)
        Cr. 2071 Employee PF Payable
        Cr. 2072 Employer PF Payable
        Cr. 2073 Employee ESI Payable
        Cr. 2074 Employer ESI Payable
        Cr. 2075 Professional Tax Payable
        Cr. 2076 TDS Payable u/s 192 (Salaries)
        """
        stmt = select(PayrollRun).where(PayrollRun.id == run_id)
        res = await session.execute(stmt)
        run = res.scalar_one_or_none()
        if not run:
            raise ValueError(f"PayrollRun with ID {run_id} not found.")

        if run.accrual_journal_id:
            raise ValueError(f"PayrollRun {run.run_number} already has posted accrual journal {run.accrual_journal_id}.")

        tenant_id = run.tenant_id

        # 1. Provision Accounts
        exp_salaries = await LedgerService.ensure_account(
            session, tenant_id, "4020", "Salaries, Wages & Allowances", "expense", "payroll", "debit"
        )
        exp_pf = await LedgerService.ensure_account(
            session, tenant_id, "4021", "Employer Contribution to Provident Fund", "expense", "payroll", "debit"
        )
        exp_esi = await LedgerService.ensure_account(
            session, tenant_id, "4022", "Employer Contribution to ESI", "expense", "payroll", "debit"
        )

        liab_net_salary = await LedgerService.ensure_account(
            session, tenant_id, "2070", "Salaries & Wages Payable", "liability", "current_liability", "credit"
        )
        liab_emp_pf = await LedgerService.ensure_account(
            session, tenant_id, "2071", "Employee Provident Fund (EPF) Payable", "liability", "tax_liability", "credit"
        )
        liab_empr_pf = await LedgerService.ensure_account(
            session, tenant_id, "2072", "Employer Provident Fund (EPF) Payable", "liability", "tax_liability", "credit"
        )
        liab_emp_esi = await LedgerService.ensure_account(
            session, tenant_id, "2073", "Employee State Insurance (ESIC) Payable", "liability", "tax_liability", "credit"
        )
        liab_empr_esi = await LedgerService.ensure_account(
            session, tenant_id, "2074", "Employer State Insurance (ESIC) Payable", "liability", "tax_liability", "credit"
        )
        liab_pt = await LedgerService.ensure_account(
            session, tenant_id, "2075", "Professional Tax (PT) Payable", "liability", "tax_liability", "credit"
        )
        liab_tds = await LedgerService.ensure_account(
            session, tenant_id, "2076", "TDS Payable u/s 192 (Salaries)", "liability", "tax_liability", "credit"
        )

        # Calculate aggregations from payslips to avoid float discrepancies
        payslips_stmt = select(Payslip).where(Payslip.payroll_run_id == run.id)
        payslips = (await session.execute(payslips_stmt)).scalars().all()

        sum_gross = sum(p.gross_earnings for p in payslips)
        sum_net = sum(p.net_salary for p in payslips)
        sum_emp_pf = sum(p.employee_pf for p in payslips)
        sum_empr_pf = sum(p.employer_pf + p.employer_eps + p.employer_edli for p in payslips)
        sum_emp_esi = sum(p.employee_esi for p in payslips)
        sum_empr_esi = sum(p.employer_esi for p in payslips)
        sum_pt = sum(p.professional_tax for p in payslips)
        sum_tds = sum(p.tds_deducted for p in payslips)

        # Create Journal Entry header
        import calendar
        _, last_day = calendar.monthrange(run.year, run.month)
        accrual_date = date(run.year, run.month, last_day)

        entry = JournalEntry(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entry_number=f"JV-PAYROLL-{run.run_number}",
            entry_date=accrual_date,
            reference_type="payroll_run",
            reference_id=run.id,
            narration=f"Monthly Salary Accrual for {run.run_number} ({run.total_employees} employees)",
            status="posted",
            is_posted=True,
            created_by=created_by_user_id
        )
        session.add(entry)
        await session.flush()

        lines: List[JournalLine] = []

        # Debits
        lines.append(JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=exp_salaries.id,
            debit_amount=sum_gross,
            credit_amount=Decimal("0.00"),
            description=f"Gross Salaries & Allowances for {run.run_number}"
        ))

        if sum_empr_pf > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=exp_pf.id,
                debit_amount=sum_empr_pf,
                credit_amount=Decimal("0.00"),
                description=f"Employer PF/EPS/EDLI Expense for {run.run_number}"
            ))

        if sum_empr_esi > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=exp_esi.id,
                debit_amount=sum_empr_esi,
                credit_amount=Decimal("0.00"),
                description=f"Employer ESI Expense for {run.run_number}"
            ))

        # Credits
        lines.append(JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=liab_net_salary.id,
            debit_amount=Decimal("0.00"),
            credit_amount=sum_net,
            description=f"Net Salaries Payable for {run.run_number}"
        ))

        if sum_emp_pf > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=liab_emp_pf.id,
                debit_amount=Decimal("0.00"),
                credit_amount=sum_emp_pf,
                description=f"Employee PF Withheld for {run.run_number}"
            ))

        if sum_empr_pf > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=liab_empr_pf.id,
                debit_amount=Decimal("0.00"),
                credit_amount=sum_empr_pf,
                description=f"Employer PF Payable for {run.run_number}"
            ))

        if sum_emp_esi > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=liab_emp_esi.id,
                debit_amount=Decimal("0.00"),
                credit_amount=sum_emp_esi,
                description=f"Employee ESI Withheld for {run.run_number}"
            ))

        if sum_empr_esi > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=liab_empr_esi.id,
                debit_amount=Decimal("0.00"),
                credit_amount=sum_empr_esi,
                description=f"Employer ESI Payable for {run.run_number}"
            ))

        if sum_pt > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=liab_pt.id,
                debit_amount=Decimal("0.00"),
                credit_amount=sum_pt,
                description=f"Professional Tax Withheld for {run.run_number}"
            ))

        if sum_tds > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=liab_tds.id,
                debit_amount=Decimal("0.00"),
                credit_amount=sum_tds,
                description=f"TDS u/s 192 Withheld for {run.run_number}"
            ))

        # Enforce strict double-entry balance invariant
        total_debits = sum(line.debit_amount for line in lines)
        total_credits = sum(line.credit_amount for line in lines)
        diff = abs(total_debits - total_credits)
        if diff != Decimal("0.00"):
            raise ValueError(
                f"Double-Entry Imbalance in Payroll Accrual! Debits={total_debits}, Credits={total_credits}, Diff={diff}"
            )

        session.add_all(lines)

        # Update run status and link journal
        run.accrual_journal_id = entry.id
        run.status = "locked"
        run.sealed_at = datetime.utcnow()
        run.sealed_by = created_by_user_id

        # Cryptographic audit hash
        audit_payload = f"{run.id}:{run.run_number}:{total_debits}:{total_credits}:{run.sealed_at.isoformat()}"
        run.sha256_audit_hash = hashlib.sha256(audit_payload.encode()).hexdigest()

        await session.flush()
        return entry

    @staticmethod
    async def post_disbursement_journal(
        session: AsyncSession,
        run_id: uuid.UUID,
        bank_account_code: str = "1010",
        payout_utr: Optional[str] = None,
        disbursement_date: Optional[date] = None,
        created_by_user_id: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Posts Leg 2 (Salary Disbursement) Journal Voucher to the General Ledger.
        Dr. 2070 Salaries & Wages Payable = Net Pay
        Cr. 1010 Bank Current Account    = Net Pay
        """
        stmt = select(PayrollRun).where(PayrollRun.id == run_id)
        res = await session.execute(stmt)
        run = res.scalar_one_or_none()
        if not run:
            raise ValueError(f"PayrollRun with ID {run_id} not found.")

        if run.disbursement_journal_id:
            raise ValueError(f"PayrollRun {run.run_number} already has posted disbursement journal {run.disbursement_journal_id}.")

        if run.status != "locked":
            raise ValueError(f"PayrollRun must be in 'locked' status before disbursement (current status: '{run.status}').")

        tenant_id = run.tenant_id

        liab_net_salary = await LedgerService.ensure_account(
            session, tenant_id, "2070", "Salaries & Wages Payable", "liability", "current_liability", "credit"
        )
        bank_account = await LedgerService.ensure_account(
            session, tenant_id, bank_account_code, "Bank Current Account", "asset", "bank", "debit"
        )

        pay_date = disbursement_date or date.today()
        disburse_amount = run.total_net_pay

        entry = JournalEntry(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entry_number=f"JV-DISBURSE-{run.run_number}",
            entry_date=pay_date,
            reference_type="payroll_disbursement",
            reference_id=run.id,
            narration=f"Salary Disbursement for {run.run_number} via Bank {bank_account_code} (UTR: {payout_utr or 'BATCH-CMS'})",
            status="posted",
            is_posted=True,
            created_by=created_by_user_id
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=liab_net_salary.id,
                debit_amount=disburse_amount,
                credit_amount=Decimal("0.00"),
                description=f"Clear Salaries Payable for {run.run_number}"
            ),
            JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=bank_account.id,
                debit_amount=Decimal("0.00"),
                credit_amount=disburse_amount,
                description=f"Bank Disbursement for {run.run_number}"
            )
        ]

        total_debits = sum(line.debit_amount for line in lines)
        total_credits = sum(line.credit_amount for line in lines)
        if total_debits != total_credits:
            raise ValueError(f"Imbalanced Disbursement Entry! Debits={total_debits}, Credits={total_credits}")

        session.add_all(lines)

        # Mark payslips as paid
        payslips_stmt = select(Payslip).where(Payslip.payroll_run_id == run.id)
        payslips = (await session.execute(payslips_stmt)).scalars().all()
        for p in payslips:
            p.payout_status = "paid"
            p.payout_date = pay_date
            if payout_utr:
                p.payout_utr = payout_utr

        run.disbursement_journal_id = entry.id
        run.status = "disbursed"

        await session.flush()
        return entry

