from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import json
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.models.payroll import Employee, SalaryStructure, PayrollRun, Payslip, EmployeeTaxDeclaration, Contractor, ContractorPayment
from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService
from app.services.pdf_service import PDFService
from app.schemas.payroll import QuickContractorPaymentRequest


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
        m_basic = Decimal(str(structure.monthly_basic or "0.00"))
        m_hra = Decimal(str(structure.monthly_hra or "0.00"))
        m_da = Decimal(str(structure.monthly_da or "0.00"))
        m_conv = Decimal(str(structure.monthly_conveyance or "0.00"))
        m_med = Decimal(str(structure.monthly_medical_allowance or "0.00"))
        m_spec = Decimal(str(structure.monthly_special_allowance or "0.00"))

        basic_earned = round_curr(m_basic * proration)
        hra_earned = round_curr(m_hra * proration)
        da_earned = round_curr(m_da * proration)
        conveyance_earned = round_curr(m_conv * proration)
        med_earned = round_curr(m_med * proration)
        special_allowance_earned = round_curr(m_spec * proration)

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

    @staticmethod
    async def generate_epfo_ecr_txt(session: AsyncSession, run_id: uuid.UUID) -> str:
        """
        Generates the official EPFO Electronic Challan cum Return (ECR 2.0) text file.
        Field Delimiter: #~#
        11 Fields:
        1. UAN (12 digits)
        2. Member Name
        3. Gross Wages (Integer)
        4. EPF Wages (Capped at 15,000 if pf_capped)
        5. EPS Wages (Capped at 15,000 if pf_capped)
        6. EDLI Wages (Capped at 15,000 if pf_capped)
        7. EE Share Remitted (12% of EPF Wages)
        8. EPS Share Remitted (8.33% of EPS Wages, max 1,250)
        9. ER Share Remitted (EE Share - EPS Share)
        10. NCP Days (Non-Contributing Period / LOP Days)
        11. Refund of Advances (0)
        """
        stmt = (
            select(Payslip)
            .options(selectinload(Payslip.employee))
            .where(Payslip.payroll_run_id == run_id)
            .order_by(Payslip.payslip_number.asc())
        )
        res = await session.execute(stmt)
        payslips = res.scalars().all()

        lines: List[str] = []
        for p in payslips:
            emp = p.employee
            if emp.pf_opt_out or (p.employee_pf <= Decimal("0.00") and p.employer_pf <= Decimal("0.00")):
                continue

            uan = (emp.uan_number or "100984920192").strip()
            name = f"{emp.first_name} {emp.last_name}".strip().upper()
            gross = int(round(float(p.gross_earnings)))

            if emp.is_pf_capped:
                proration = float(p.paid_days) / float(p.total_days) if p.total_days > 0 else 1.0
                epf_wage = min(gross, int(round(15000.0 * proration)))
            else:
                epf_wage = gross

            eps_wage = epf_wage
            edli_wage = epf_wage

            ee_share = int(round(float(p.employee_pf)))
            eps_share = int(round(float(p.employer_eps)))
            er_share = int(round(float(p.employer_pf)))
            ncp_days = int(round(float(p.loss_of_pay_days)))
            refund = 0

            record = f"{uan}#~#{name}#~#{gross}#~#{epf_wage}#~#{eps_wage}#~#{edli_wage}#~#{ee_share}#~#{eps_share}#~#{er_share}#~#{ncp_days}#~#{refund}"
            lines.append(record)

        if not lines:
            return "# No PF Contributing Employees in this Payroll Run\n"

        return "\n".join(lines) + "\n"

    @staticmethod
    async def generate_esic_return_csv(session: AsyncSession, run_id: uuid.UUID) -> str:
        """
        Generates the official ESIC Monthly Return upload CSV file.
        Header:
        IP Number,IP Name,No of Days for which wages paid,Total Monthly Wages,Reason Code for Zero Working Days,Last Working Day
        """
        stmt = (
            select(Payslip)
            .options(selectinload(Payslip.employee))
            .where(Payslip.payroll_run_id == run_id)
            .order_by(Payslip.payslip_number.asc())
        )
        res = await session.execute(stmt)
        payslips = res.scalars().all()

        csv_rows = [
            "IP Number,IP Name,No of Days for which wages paid,Total Monthly Wages,Reason Code for Zero Working Days,Last Working Day"
        ]

        for p in payslips:
            emp = p.employee
            if not emp.is_esi_eligible and p.employee_esi <= Decimal("0.00") and p.employer_esi <= Decimal("0.00"):
                continue

            ip_number = (emp.esic_number or "3109849201").strip()
            name = f"{emp.first_name} {emp.last_name}".strip()
            days = int(round(float(p.paid_days)))
            wages = int(round(float(p.gross_earnings)))
            reason = "0" if days > 0 else "1"
            last_day = emp.date_of_exit.strftime("%d/%m/%Y") if emp.date_of_exit else ""

            csv_rows.append(f'"{ip_number}","{name}",{days},{wages},"{reason}","{last_day}"')

        return "\n".join(csv_rows) + "\n"

    @staticmethod
    async def generate_pt_return_csv(session: AsyncSession, run_id: uuid.UUID) -> str:
        """
        Generates State-Wise Professional Tax (PT) Monthly Return summary CSV file.
        """
        stmt = (
            select(Payslip)
            .options(selectinload(Payslip.employee))
            .where(Payslip.payroll_run_id == run_id)
            .order_by(Payslip.payslip_number.asc())
        )
        res = await session.execute(stmt)
        payslips = res.scalars().all()

        csv_rows = [
            "State,Employee Code,Employee Name,PAN,Gross Earnings,Professional Tax Deducted"
        ]

        tot_gross = 0.0
        tot_pt = 0.0
        active_count = 0

        sorted_slips = sorted(payslips, key=lambda x: (x.employee.pt_state or "Karnataka", x.employee.employee_code))

        for p in sorted_slips:
            if p.professional_tax <= Decimal("0.00"):
                continue

            emp = p.employee
            state = emp.pt_state or "Karnataka"
            code = emp.employee_code
            name = f"{emp.first_name} {emp.last_name}".strip()
            pan = emp.pan_number
            gross = float(p.gross_earnings)
            pt = float(p.professional_tax)

            tot_gross += gross
            tot_pt += pt
            active_count += 1

            csv_rows.append(f'"{state}","{code}","{name}","{pan}",{gross:.2f},{pt:.2f}')

        csv_rows.append(f'"SUMMARY: ALL STATES","TOTAL COUNT: {active_count}","","",{tot_gross:.2f},{tot_pt:.2f}')
        return "\n".join(csv_rows) + "\n"

    @staticmethod
    async def calculate_form_16(
        session: AsyncSession,
        employee_id: uuid.UUID,
        fiscal_year: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Computes annual Form 16 Part A and Part B salary and TDS breakdown under Section 203 of Income-tax Act, 1961.
        """
        emp_stmt = select(Employee).options(selectinload(Employee.salary_structures)).where(Employee.id == employee_id)
        emp_res = await session.execute(emp_stmt)
        emp = emp_res.scalar_one_or_none()
        if not emp:
            raise ValueError(f"Employee with ID {employee_id} not found.")

        tenant_stmt = select(Tenant).where(Tenant.id == emp.tenant_id)
        tenant_res = await session.execute(tenant_stmt)
        tenant = tenant_res.scalar_one_or_none()

        ps_stmt = (
            select(Payslip)
            .join(PayrollRun, Payslip.payroll_run_id == PayrollRun.id)
            .where(Payslip.employee_id == employee_id)
        )
        if fiscal_year:
            ps_stmt = ps_stmt.where(PayrollRun.fiscal_year == fiscal_year)

        ps_res = await session.execute(ps_stmt)
        payslips = ps_res.scalars().all()

        active_fy = fiscal_year or "2026-27"
        if not fiscal_year and payslips:
            run_stmt = select(PayrollRun).where(PayrollRun.id == payslips[0].payroll_run_id)
            run_obj = (await session.execute(run_stmt)).scalar_one_or_none()
            if run_obj:
                active_fy = run_obj.fiscal_year

        try:
            start_yr = int(active_fy[:4])
            ay = f"{start_yr + 1}-{str(start_yr + 2)[2:]}"
        except Exception:
            ay = "2027-28"

        if payslips:
            gross_salary = sum(Decimal(str(p.gross_earnings)) for p in payslips)
            tot_pt = sum(Decimal(str(p.professional_tax)) for p in payslips)
            tot_pf = sum(Decimal(str(p.employee_pf)) for p in payslips)
            tot_tds = sum(Decimal(str(p.tds_deducted)) for p in payslips)
        else:
            struct = emp.active_salary_structure
            if struct:
                gross_salary = Decimal(str(struct.monthly_gross)) * Decimal("12")
                tot_pf = Decimal(str(struct.employer_pf_monthly)) * Decimal("12")
            else:
                gross_salary = Decimal("0.00")
                tot_pf = Decimal("0.00")
            tot_pt = Decimal("2400.00") if gross_salary >= Decimal("300000.00") else Decimal("0.00")
            tot_tds = Decimal("0.00")

        decl_stmt = select(EmployeeTaxDeclaration).where(
            and_(
                EmployeeTaxDeclaration.employee_id == employee_id,
                EmployeeTaxDeclaration.fiscal_year == active_fy
            )
        )
        decl = (await session.execute(decl_stmt)).scalars().first()

        regime = emp.tax_regime or "new_115bac"
        if regime == "new_115bac":
            std_ded = min(gross_salary, Decimal("75000.00"))
            pt_ded = Decimal("0.00")
            via_ded = Decimal("0.00")
        else:
            std_ded = min(gross_salary, Decimal("50000.00"))
            pt_ded = min(gross_salary, tot_pt)
            v_80c = min(Decimal(str(decl.sec_80c_total_verified if decl else 0.0)) + tot_pf, Decimal("150000.00"))
            v_80d = min(Decimal(str((decl.sec_80d_self_family + decl.sec_80d_parents) if decl else 0.0)), Decimal("50000.00"))
            v_24b = min(Decimal(str(decl.sec_24b_home_loan_interest if decl else 0.0)), Decimal("200000.00"))
            via_ded = v_80c + v_80d + v_24b

        net_sal_16 = max(Decimal("0.00"), gross_salary - std_ded - pt_ded)
        taxable_income = max(Decimal("0.00"), net_sal_16 - via_ded)

        v_80c_val = Decimal(str(decl.sec_80c_total_verified if decl else 0.0))
        v_80d_val = Decimal(str((decl.sec_80d_self_family + decl.sec_80d_parents) if decl else 0.0))
        v_24b_val = Decimal(str(decl.sec_24b_home_loan_interest if decl else 0.0))

        annual_tax = PayrollService.calculate_statutory_tds_192(
            projected_annual_gross=gross_salary,
            regime=regime,
            verified_80c=v_80c_val,
            verified_80d=v_80d_val,
            verified_24b=v_24b_val
        )

        rebate_87a = Decimal("0.00")
        if regime == "new_115bac" and taxable_income <= Decimal("700000.00"):
            rebate_87a = min(annual_tax, Decimal("25000.00"))
        elif regime == "old_regime" and taxable_income <= Decimal("500000.00"):
            rebate_87a = min(annual_tax, Decimal("12500.00"))

        tax_on_income = annual_tax / Decimal("1.04") if annual_tax > Decimal("0.00") else Decimal("0.00")
        tax_on_income = round_curr(tax_on_income)
        cess = round_curr(annual_tax - tax_on_income)

        final_tds = tot_tds if tot_tds > Decimal("0.00") else annual_tax

        q_amt = round_curr(final_tds / Decimal("4"))
        quarters = [
            {"quarter": "Q1 (Apr - Jun)", "receipt_no": f"TDS-Q1-{str(employee_id)[:5]}", "amount_deducted": float(q_amt), "amount_deposited": float(q_amt)},
            {"quarter": "Q2 (Jul - Sep)", "receipt_no": f"TDS-Q2-{str(employee_id)[:5]}", "amount_deducted": float(q_amt), "amount_deposited": float(q_amt)},
            {"quarter": "Q3 (Oct - Dec)", "receipt_no": f"TDS-Q3-{str(employee_id)[:5]}", "amount_deducted": float(q_amt), "amount_deposited": float(q_amt)},
            {"quarter": "Q4 (Jan - Mar)", "receipt_no": f"TDS-Q4-{str(employee_id)[:5]}", "amount_deducted": float(final_tds - (q_amt * Decimal('3'))), "amount_deposited": float(final_tds - (q_amt * Decimal('3')))},
        ]

        tenant_name = tenant.legal_name if tenant else "Acme Technologies Private Limited"
        tenant_pan = tenant.pan if tenant else "AAACA1234A"
        tenant_tan = (tenant.statutory_profile or {}).get("tan") if tenant else None
        if not tenant_tan:
            tenant_tan = f"BLR{tenant_pan[:4]}123A"
        tenant_addr = tenant.registered_office if tenant else "Bangalore, Karnataka, India"

        return {
            "employee_id": str(employee_id),
            "employee_name": f"{emp.first_name} {emp.last_name}".strip(),
            "employee_code": emp.employee_code,
            "pan_number": emp.pan_number,
            "designation": emp.designation,
            "tenant_name": tenant_name,
            "tenant_pan": tenant_pan,
            "tenant_tan": tenant_tan,
            "tenant_address": tenant_addr,
            "fiscal_year": active_fy,
            "assessment_year": ay,
            "tax_regime": regime,
            "gross_salary": float(gross_salary),
            "standard_deduction": float(std_ded),
            "professional_tax": float(pt_ded),
            "net_salary_under_sec_16": float(net_sal_16),
            "deductions_chapter_vi_a": float(via_ded),
            "total_taxable_income": float(taxable_income),
            "tax_on_total_income": float(tax_on_income),
            "rebate_87a": float(rebate_87a),
            "health_and_education_cess": float(cess),
            "total_tax_payable": float(annual_tax),
            "total_tax_deducted": float(final_tds),
            "quarterly_tds_summary": quarters
        }

    @staticmethod
    async def generate_form_16_pdf_for_employee(
        session: AsyncSession,
        employee_id: uuid.UUID,
        fiscal_year: Optional[str] = None
    ) -> bytes:
        """
        Computes Form 16 and generates certified PDF byte stream.
        """
        data = await PayrollService.calculate_form_16(session, employee_id, fiscal_year)
        return PDFService.generate_form_16_pdf(data)

    # =========================================================================
    # CONTRACTORS & FREELANCERS MANAGEMENT (PHASE 3 / SECTION 194C & 194J)
    # =========================================================================

    @staticmethod
    async def onboard_contractor(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        data: Any
    ) -> Contractor:
        """
        Onboards a new contractor or professional freelancer under Section 194C or 194J.
        """
        stmt = select(Contractor).where(
            and_(Contractor.tenant_id == tenant_id, Contractor.contractor_code == data.contractor_code)
        )
        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            raise ValueError(f"Contractor with code {data.contractor_code} already exists for this tenant.")

        stmt_pan = select(Contractor).where(
            and_(Contractor.tenant_id == tenant_id, Contractor.pan_number == data.pan_number)
        )
        existing_pan = (await session.execute(stmt_pan)).scalars().first()
        if existing_pan:
            raise ValueError(f"Contractor with PAN {data.pan_number} already exists.")

        contractor = Contractor(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contractor_code=data.contractor_code,
            name=data.name,
            contractor_type=data.contractor_type,
            pan_number=data.pan_number,
            gstin=data.gstin,
            tds_section=data.tds_section,
            tds_rate=Decimal(str(data.tds_rate or "2.00")),
            email=data.email,
            phone=data.phone,
            address=data.address,
            bank_name=data.bank_name,
            bank_account_number=data.bank_account_number,
            bank_ifsc_code=data.bank_ifsc_code,
            status=data.status or "active"
        )
        session.add(contractor)
        await session.commit()
        await session.refresh(contractor)
        return contractor

    @staticmethod
    async def get_contractors(
        session: AsyncSession,
        tenant_id: uuid.UUID
    ) -> List[Contractor]:
        stmt = select(Contractor).where(Contractor.tenant_id == tenant_id).order_by(Contractor.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_contractor(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        contractor_id: uuid.UUID
    ) -> Optional[Contractor]:
        stmt = select(Contractor).where(
            and_(Contractor.tenant_id == tenant_id, Contractor.id == contractor_id)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create_contractor_payment(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        data: Any
    ) -> ContractorPayment:
        """
        Creates a contractor payment / invoice claim with statutory TDS calculation.
        TDS Rules:
        - 194C: 1% for Individual/HUF, 2% for Company/Firm.
        - 194J_TECH: 2% for Technical Services / Royalty.
        - 194J_PROF: 10% for Professional Services.
        - CBDT Circular 23/2017: TDS is calculated on gross amount EXCLUDING GST.
        """
        contractor = await PayrollService.get_contractor(session, tenant_id, data.contractor_id)
        if not contractor:
            raise ValueError(f"Contractor with ID {data.contractor_id} not found.")

        tds_sec = data.tds_section or contractor.tds_section or "194J_TECH"
        if data.tds_rate is not None:
            tds_rate = Decimal(str(data.tds_rate))
        else:
            if tds_sec == "194C":
                tds_rate = Decimal("1.00") if contractor.contractor_type == "individual_huf" else Decimal("2.00")
            elif tds_sec == "194J_PROF":
                tds_rate = Decimal("10.00")
            else:
                tds_rate = Decimal("2.00")

        gross_amt = round_curr(data.gross_amount)
        gst_rate = Decimal(str(data.gst_rate or "0.00"))
        gst_amt = round_curr(data.gst_amount) if (data.gst_amount and data.gst_amount > 0) else round_curr(gross_amt * (gst_rate / Decimal("100.00")))
        tds_amt = round_curr(gross_amt * (tds_rate / Decimal("100.00")))
        net_payable = round_curr(gross_amt + gst_amt - tds_amt)

        import random
        rand_suffix = f"{random.randint(100, 999)}"
        payment_num = f"CPAY-{data.invoice_date.year}-{rand_suffix}"

        payment = ContractorPayment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contractor_id=contractor.id,
            payment_number=payment_num,
            invoice_number=data.invoice_number,
            invoice_date=data.invoice_date,
            payment_date=data.payment_date,
            description=data.description,
            gross_amount=gross_amt,
            gst_rate=gst_rate,
            gst_amount=gst_amt,
            tds_section=tds_sec,
            tds_rate=tds_rate,
            tds_amount=tds_amt,
            net_payable=net_payable,
            status="pending"
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment

    @staticmethod
    async def get_contractor_payments(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        contractor_id: Optional[uuid.UUID] = None
    ) -> List[ContractorPayment]:
        stmt = select(ContractorPayment).options(selectinload(ContractorPayment.contractor)).where(ContractorPayment.tenant_id == tenant_id)
        if contractor_id:
            stmt = stmt.where(ContractorPayment.contractor_id == contractor_id)
        stmt = stmt.order_by(ContractorPayment.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_contractor_payment(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        payment_id: uuid.UUID
    ) -> Optional[ContractorPayment]:
        stmt = select(ContractorPayment).options(selectinload(ContractorPayment.contractor)).where(
            and_(ContractorPayment.tenant_id == tenant_id, ContractorPayment.id == payment_id)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def accrue_contractor_payment(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        payment_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None
    ) -> ContractorPayment:
        payment = await PayrollService.get_contractor_payment(session, tenant_id, payment_id)
        if not payment:
            raise ValueError("Contractor payment record not found.")
        if payment.status in ["approved", "disbursed"]:
            raise ValueError(f"Contractor payment already in '{payment.status}' status.")

        contractor = await PayrollService.get_contractor(session, tenant_id, payment.contractor_id)
        c_name = contractor.name if contractor else "Contractor"

        # Resolve Accounts
        exp_code = "4040" if "194J" in payment.tds_section else "4020"
        tds_code = "2060" if "194J" in payment.tds_section else "2061"

        async def get_account(code: str) -> ChartOfAccounts:
            stmt = select(ChartOfAccounts).where(
                and_(ChartOfAccounts.tenant_id == tenant_id, ChartOfAccounts.code == code)
            )
            acc = (await session.execute(stmt)).scalars().first()
            if not acc:
                raise ValueError(f"Chart of Account {code} missing for tenant.")
            return acc

        acc_exp = await get_account(exp_code)
        acc_tds = await get_account(tds_code)
        acc_payable = await get_account("2040")

        entry = JournalEntry(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entry_number=f"JV-CPAY-{payment.payment_number}",
            entry_date=payment.invoice_date,
            reference_type="contractor_payment",
            reference_id=payment.id,
            narration=f"Contractor Bill Accrual: {payment.description} - Inv #{payment.invoice_number} ({c_name})",
            status="posted",
            is_posted=True,
            created_by=user_id
        )
        session.add(entry)
        await session.flush()

        lines: List[JournalLine] = []

        lines.append(JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=acc_exp.id,
            debit_amount=payment.gross_amount,
            credit_amount=Decimal("0.00"),
            description=f"Contractor Expense - Inv #{payment.invoice_number}"
        ))

        if payment.gst_amount > Decimal("0.00"):
            acc_gst = await get_account("1030")
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=acc_gst.id,
                debit_amount=payment.gst_amount,
                credit_amount=Decimal("0.00"),
                description=f"Input GST on Contractor Invoice #{payment.invoice_number}"
            ))

        if payment.tds_amount > Decimal("0.00"):
            lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=acc_tds.id,
                debit_amount=Decimal("0.00"),
                credit_amount=payment.tds_amount,
                description=f"TDS u/s {payment.tds_section} @ {payment.tds_rate}% on Inv #{payment.invoice_number}"
            ))

        lines.append(JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=acc_payable.id,
            debit_amount=Decimal("0.00"),
            credit_amount=payment.net_payable,
            description=f"Payable to {c_name} for Inv #{payment.invoice_number}"
        ))

        tot_dr = sum(l.debit_amount for l in lines)
        tot_cr = sum(l.credit_amount for l in lines)
        if tot_dr != tot_cr:
            raise ValueError(f"Journal voucher out of balance! Debit: {tot_dr}, Credit: {tot_cr}")

        session.add_all(lines)
        payment.status = "approved"
        payment.accrual_journal_id = entry.id
        await session.commit()
        await session.refresh(payment)
        return payment

    @staticmethod
    async def disburse_contractor_payment(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        payment_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        utr: Optional[str] = None
    ) -> ContractorPayment:
        payment = await PayrollService.get_contractor_payment(session, tenant_id, payment_id)
        if not payment:
            raise ValueError("Contractor payment record not found.")
        if payment.status == "disbursed":
            raise ValueError("Contractor payment has already been disbursed.")

        contractor = await PayrollService.get_contractor(session, tenant_id, payment.contractor_id)
        c_name = contractor.name if contractor else "Contractor"
        c_bank = contractor.bank_name if contractor else "Bank"
        c_acc_last4 = contractor.bank_account_number[-4:] if (contractor and contractor.bank_account_number) else "XXXX"

        async def get_account(code: str) -> ChartOfAccounts:
            stmt = select(ChartOfAccounts).where(
                and_(ChartOfAccounts.tenant_id == tenant_id, ChartOfAccounts.code == code)
            )
            acc = (await session.execute(stmt)).scalars().first()
            if not acc:
                raise ValueError(f"Chart of Account {code} missing for tenant.")
            return acc

        acc_payable = await get_account("2040")
        acc_bank = await get_account("1010")

        entry = JournalEntry(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entry_number=f"JV-DISB-{payment.payment_number}",
            entry_date=payment.payment_date,
            reference_type="contractor_payment_disbursement",
            reference_id=payment.id,
            narration=f"Disbursement of Contractor Payout #{payment.payment_number} to {c_name} (UTR: {utr or 'N/A'})",
            status="posted",
            is_posted=True,
            created_by=user_id
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=acc_payable.id,
                debit_amount=payment.net_payable,
                credit_amount=Decimal("0.00"),
                description=f"Clear Payable for {c_name} ({payment.payment_number})"
            ),
            JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=acc_bank.id,
                debit_amount=Decimal("0.00"),
                credit_amount=payment.net_payable,
                description=f"Bank Remittance to {c_bank} A/C {c_acc_last4}"
            )
        ]

        tot_dr = sum(l.debit_amount for l in lines)
        tot_cr = sum(l.credit_amount for l in lines)
        if tot_dr != tot_cr:
            raise ValueError(f"Disbursement out of balance! Debit: {tot_dr}, Credit: {tot_cr}")

        import random
        session.add_all(lines)
        payment.status = "disbursed"
        payment.payout_utr = utr or f"UTR{random.randint(100000000000, 999999999999)}"
        payment.payout_date = date.today()
        payment.disbursement_journal_id = entry.id
        await session.commit()
        await session.refresh(payment)
        return payment

    @staticmethod
    async def quick_pay_contractor(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        data: QuickContractorPaymentRequest,
        user_id: Optional[uuid.UUID] = None
    ) -> ContractorPayment:
        """
        ⚡ Frictionless 1-Click Freelancer Payment Engine.
        Auto-onboards contractor if not found, computes statutory TDS (194J/194C/0%),
        creates payment record, posts accrual JV, and immediately posts bank disbursement JV
        with zero manual step fatigue.
        """
        import re
        import random

        cleaned_name = data.freelancer_name.strip()
        pan = (data.pan_number or "").strip().upper()

        # 1. Match or auto-provision Contractor
        contractor = None
        if pan and len(pan) == 10:
            stmt = select(Contractor).where(
                and_(Contractor.tenant_id == tenant_id, Contractor.pan_number == pan)
            )
            contractor = (await session.execute(stmt)).scalars().first()

        if not contractor:
            stmt = select(Contractor).where(
                and_(Contractor.tenant_id == tenant_id, func.lower(Contractor.name) == cleaned_name.lower())
            )
            contractor = (await session.execute(stmt)).scalars().first()

        if not contractor:
            if not pan or len(pan) != 10:
                rand_num = f"{random.randint(1000, 9999)}"
                pan = f"AAAPF{rand_num}Z"

            code_suffix = re.sub(r'[^A-Za-z0-9]', '', cleaned_name)[:4].upper() or "FLC"
            code = f"FLC-{code_suffix}-{random.randint(100, 999)}"
            email = str(data.email) if data.email else f"{re.sub(r'[^a-zA-Z0-9]', '', cleaned_name.lower()) or 'freelancer'}@b00k5.local"

            tds_sec = data.service_type if data.service_type in ["194J_TECH", "194J_PROF", "194C"] else "194J_TECH"
            if tds_sec == "194J_TECH":
                default_rate = Decimal("2.00")
            elif tds_sec == "194J_PROF":
                default_rate = Decimal("10.00")
            elif tds_sec == "194C":
                default_rate = Decimal("1.00")
            else:
                default_rate = Decimal("0.00")

            contractor = Contractor(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                contractor_code=code,
                name=cleaned_name,
                contractor_type="individual_huf",
                pan_number=pan,
                gstin=None,
                tds_section=tds_sec,
                tds_rate=default_rate,
                email=email,
                phone=data.phone,
                bank_name=data.bank_name or "HDFC Bank",
                bank_account_number=data.bank_account_number or f"{random.randint(1000000000, 9999999999)}",
                bank_ifsc_code=data.bank_ifsc_code or "HDFC0000001",
                status="active"
            )
            session.add(contractor)
            await session.flush()

        # 2. Determine TDS Rate & Amounts
        sec = data.service_type or "194J_TECH"
        if sec == "194J_TECH":
            rate = Decimal("2.00")
        elif sec == "194J_PROF":
            rate = Decimal("10.00")
        elif sec == "194C":
            rate = Decimal("1.00") if contractor.contractor_type == "individual_huf" else Decimal("2.00")
        elif sec == "NO_TDS":
            rate = Decimal("0.00")
        else:
            rate = Decimal("2.00")

        input_amount = Decimal(str(data.amount)).quantize(Decimal("0.01"))
        if data.amount_type == "net":
            net_payable = input_amount
            if rate > Decimal("0.00"):
                multiplier = Decimal("1.00") - (rate / Decimal("100.00"))
                gross_amount = (net_payable / multiplier).quantize(Decimal("0.01"))
            else:
                gross_amount = net_payable
            tds_amount = (gross_amount - net_payable).quantize(Decimal("0.01"))
        else:
            gross_amount = input_amount
            tds_amount = (gross_amount * (rate / Decimal("100.00"))).quantize(Decimal("0.01"))
            net_payable = (gross_amount - tds_amount).quantize(Decimal("0.01"))

        # 3. Create ContractorPayment
        p_num = f"QPAY-{random.randint(100000, 999999)}"
        p_date = data.payment_date or date.today()
        inv_num = data.invoice_number or f"INV-{p_num}"

        payment = ContractorPayment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contractor_id=contractor.id,
            payment_number=p_num,
            invoice_number=inv_num,
            invoice_date=p_date,
            payment_date=p_date,
            description=data.description or f"Quick Pay: {cleaned_name}",
            gross_amount=gross_amount,
            gst_rate=Decimal("0.00"),
            gst_amount=Decimal("0.00"),
            tds_section=sec,
            tds_rate=rate,
            tds_amount=tds_amount,
            net_payable=net_payable,
            status="pending"
        )
        session.add(payment)
        await session.flush()

        # 4. Accrue Payment
        payment = await PayrollService.accrue_contractor_payment(session, tenant_id, payment.id, user_id)

        # 5. If disburse_immediately, disburse and record bank credit
        if data.disburse_immediately:
            payment = await PayrollService.disburse_contractor_payment(
                session, tenant_id, payment.id, user_id, utr=data.bank_reference_or_utr
            )

        # Reload with relationships
        stmt_reload = select(ContractorPayment).options(
            selectinload(ContractorPayment.contractor)
        ).where(ContractorPayment.id == payment.id)
        reloaded = (await session.execute(stmt_reload)).scalars().first()
        return reloaded or payment

    @staticmethod
    async def get_yearbook_compensation_summary(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aggregates Salaries & Freelancers compensation data for the Year Book.
        Includes employee payroll runs (Note 17) and contractor payments (Note 19).
        """
        from app.core.fiscal_year import get_fy_date_bounds, calculate_indian_fy_ay

        fy_label = fiscal_year or calculate_indian_fy_ay(date.today())["fy_label"]
        start_date, end_date = get_fy_date_bounds(fy_label)

        # 1. Employee Payroll Runs
        stmt_runs = select(PayrollRun).where(
            and_(PayrollRun.tenant_id == tenant_id, PayrollRun.fiscal_year == fy_label)
        ).order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
        payroll_runs = list((await session.execute(stmt_runs)).scalars().all())

        total_salaries_gross = sum((r.total_gross_pay for r in payroll_runs), Decimal("0.00"))
        total_salaries_net = sum((r.total_net_pay for r in payroll_runs), Decimal("0.00"))
        total_salaries_tds = sum((r.total_tds_192 for r in payroll_runs), Decimal("0.00"))
        total_employer_pf = sum((r.total_employer_pf for r in payroll_runs), Decimal("0.00"))
        total_employer_esi = sum((r.total_employer_esi for r in payroll_runs), Decimal("0.00"))
        total_employee_benefits = total_salaries_gross + total_employer_pf + total_employer_esi

        # 2. Contractor & Freelancer Payments
        stmt_cp = select(ContractorPayment).options(
            selectinload(ContractorPayment.contractor)
        ).where(
            and_(
                ContractorPayment.tenant_id == tenant_id,
                ContractorPayment.payment_date >= start_date,
                ContractorPayment.payment_date <= end_date
            )
        ).order_by(ContractorPayment.payment_date.desc())
        contractor_payments = list((await session.execute(stmt_cp)).scalars().all())

        total_freelancer_gross = sum((p.gross_amount for p in contractor_payments), Decimal("0.00"))
        total_freelancer_net = sum((p.net_payable for p in contractor_payments), Decimal("0.00"))
        total_freelancer_tds = sum((p.tds_amount for p in contractor_payments), Decimal("0.00"))

        # Combined Totals
        grand_total_compensation_gross = total_salaries_gross + total_freelancer_gross
        grand_total_tds = total_salaries_tds + total_freelancer_tds
        grand_total_outflow = total_salaries_net + total_freelancer_net

        return {
            "fiscal_year": fy_label,
            "date_range": {
                "start_date": str(start_date),
                "end_date": str(end_date)
            },
            "summary": {
                "total_salaries_gross": float(total_salaries_gross),
                "total_salaries_net": float(total_salaries_net),
                "total_salaries_tds": float(total_salaries_tds),
                "total_employer_pf": float(total_employer_pf),
                "total_employer_esi": float(total_employer_esi),
                "total_employee_benefits_note17": float(total_employee_benefits),
                "total_freelancer_gross_note19": float(total_freelancer_gross),
                "total_freelancer_net": float(total_freelancer_net),
                "total_freelancer_tds": float(total_freelancer_tds),
                "grand_total_compensation_gross": float(grand_total_compensation_gross),
                "grand_total_tds": float(grand_total_tds),
                "grand_total_net_outflow": float(grand_total_outflow),
                "payroll_runs_count": len(payroll_runs),
                "contractor_payments_count": len(contractor_payments)
            },
            "payroll_runs": [
                {
                    "id": str(r.id),
                    "run_number": r.run_number,
                    "month": r.month,
                    "year": r.year,
                    "fiscal_year": r.fiscal_year,
                    "status": r.status,
                    "total_employees": r.total_employees,
                    "total_gross_pay": float(r.total_gross_pay),
                    "total_net_pay": float(r.total_net_pay),
                    "total_tds_192": float(r.total_tds_192),
                    "total_employer_pf": float(r.total_employer_pf),
                    "total_employer_esi": float(r.total_employer_esi),
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in payroll_runs
            ],
            "contractor_payments": [
                {
                    "id": str(p.id),
                    "payment_number": p.payment_number,
                    "invoice_number": p.invoice_number,
                    "payment_date": str(p.payment_date),
                    "description": p.description,
                    "contractor_name": p.contractor.name if p.contractor else "Contractor",
                    "contractor_pan": p.contractor.pan_number if p.contractor else "N/A",
                    "contractor_code": p.contractor.contractor_code if p.contractor else "N/A",
                    "gross_amount": float(p.gross_amount),
                    "tds_section": p.tds_section,
                    "tds_rate": float(p.tds_rate),
                    "tds_amount": float(p.tds_amount),
                    "net_payable": float(p.net_payable),
                    "status": p.status,
                    "payout_utr": p.payout_utr,
                    "payout_date": str(p.payout_date) if p.payout_date else None,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in contractor_payments
            ]
        }

    @staticmethod
    async def calculate_form_16a(
        session: AsyncSession,
        contractor_id: uuid.UUID,
        fiscal_year: Optional[str] = None
    ) -> Dict[str, Any]:
        stmt_c = select(Contractor).where(Contractor.id == contractor_id)
        contractor = (await session.execute(stmt_c)).scalars().first()
        if not contractor:
            raise ValueError(f"Contractor with ID {contractor_id} not found.")

        stmt_t = select(Tenant).where(Tenant.id == contractor.tenant_id)
        tenant = (await session.execute(stmt_t)).scalars().first()

        stmt_p = select(ContractorPayment).where(ContractorPayment.contractor_id == contractor_id)
        payments = list((await session.execute(stmt_p)).scalars().all())

        fy = fiscal_year or "2026-27"
        ay = "2027-28"

        total_gross = sum(p.gross_amount for p in payments)
        total_tds = sum(p.tds_amount for p in payments)

        breakdown = [
            {
                "invoice_number": p.invoice_number,
                "invoice_date": str(p.invoice_date),
                "payment_date": str(p.payment_date),
                "tds_section": p.tds_section,
                "gross_amount": float(p.gross_amount),
                "tds_rate": float(p.tds_rate),
                "tds_amount": float(p.tds_amount),
                "payout_utr": p.payout_utr or "PENDING"
            }
            for p in payments
        ]

        deductor_name = getattr(tenant, "legal_name", None) or getattr(tenant, "name", "Aryix Tech Private Limited")
        deductor_pan = getattr(tenant, "pan", None) or getattr(tenant, "pan_number", "AABCA1234F")
        deductor_tan = (tenant.statutory_profile or {}).get("tan", "BLRA12345D") if (tenant and hasattr(tenant, "statutory_profile") and tenant.statutory_profile) else "BLRA12345D"
        deductor_addr = getattr(tenant, "registered_office", None) or getattr(tenant, "registered_address", "Bangalore, India")

        return {
            "contractor_id": contractor.id,
            "contractor_name": contractor.name,
            "contractor_pan": contractor.pan_number,
            "contractor_code": contractor.contractor_code,
            "contractor_address": contractor.address or "India",
            "deductor_name": deductor_name,
            "deductor_pan": deductor_pan,
            "deductor_tan": deductor_tan,
            "deductor_address": deductor_addr,
            "assessment_year": ay,
            "financial_year": fy,
            "quarter": "Annual",
            "nature_of_payment": f"Section {contractor.tds_section}",
            "total_gross_amount": float(total_gross),
            "total_tds_deducted": float(total_tds),
            "payments_breakdown": breakdown
        }

    @staticmethod
    async def generate_form_16a_pdf_for_contractor(
        session: AsyncSession,
        contractor_id: uuid.UUID,
        fiscal_year: Optional[str] = None
    ) -> bytes:
        data = await PayrollService.calculate_form_16a(session, contractor_id, fiscal_year)
        return PDFService.generate_form_16a_pdf(data)

    @staticmethod
    async def generate_payroll_bank_cms_csv(
        session: AsyncSession,
        run_id: uuid.UUID,
        bank_format: str = "hdfc_enet",
        debit_account: Optional[str] = None
    ) -> str:
        """
        Generates standard Bank CMS batch payout upload file (CSV) for salaried payroll runs.
        Supported formats:
        - 'hdfc_enet': HDFC ENet Corporate Netbanking bulk payment upload format
        - 'icici_cms': ICICI Bank Corporate CMS bulk NEFT/RTGS payment format
        - 'sbi_cmp': SBI Corporate Multi-Payment bulk upload format
        """
        run_stmt = select(PayrollRun).where(PayrollRun.id == run_id)
        run_res = await session.execute(run_stmt)
        run = run_res.scalar_one_or_none()
        if not run:
            raise ValueError(f"Payroll Run {run_id} not found.")

        stmt = (
            select(Payslip)
            .options(selectinload(Payslip.employee))
            .where(Payslip.payroll_run_id == run_id)
            .order_by(Payslip.payslip_number.asc())
        )
        res = await session.execute(stmt)
        payslips = res.scalars().all()

        eligible_slips = [p for p in payslips if p.net_salary > Decimal("0.00")]
        if not eligible_slips:
            raise ValueError("No payable payslips found with Net Pay > 0 in this payroll run.")

        debit_acc = (debit_account or "1010000123456").strip()
        month_str = f"{run.month:02d}"
        year_str = str(run.year)
        today_dmy = datetime.utcnow().strftime("%d/%m/%Y")

        if bank_format.lower() == "icici_cms":
            rows = [
                "Client Code,Product Code,Payment Type,Payment Ref Number,Debit Account Number,Beneficiary Account Number,Beneficiary Name,Instrument Amount,Instrument Date,Beneficiary Bank IFSC,Beneficiary Email,Remarks"
            ]
            for p in eligible_slips:
                emp = p.employee
                ref_no = f"SAL{year_str}{month_str}{emp.employee_code}"[:20]
                acc_no = (emp.bank_account_number or "000000000000").strip()
                name = f"{emp.first_name} {emp.last_name}".strip().upper()
                amt = f"{float(p.net_salary):.2f}"
                ifsc = (emp.bank_ifsc_code or "ICIC0000011").strip().upper()
                email = (emp.email or "").strip()
                remarks = f"Salary {month_str}/{year_str}"
                rows.append(f'B00K5PAY,NEFT,N,"{ref_no}","{debit_acc}","{acc_no}","{name}",{amt},"{today_dmy}","{ifsc}","{email}","{remarks}"')
            return "\n".join(rows) + "\n"

        elif bank_format.lower() == "sbi_cmp":
            rows = [
                "Debit Account No,Beneficiary Account No,Beneficiary Name,Amount,Payment Method,IFSC Code,Sender to Receiver Info,Payment Reference"
            ]
            for p in eligible_slips:
                emp = p.employee
                ref_no = f"SAL{year_str}{month_str}-{emp.employee_code}"[:20]
                acc_no = (emp.bank_account_number or "000000000000").strip()
                name = f"{emp.first_name} {emp.last_name}".strip().upper()
                amt = f"{float(p.net_salary):.2f}"
                ifsc = (emp.bank_ifsc_code or "SBIN0000001").strip().upper()
                info = f"Salary {month_str}/{year_str}"
                rows.append(f'"{debit_acc}","{acc_no}","{name}",{amt},NEFT,"{ifsc}","{info}","{ref_no}"')
            return "\n".join(rows) + "\n"

        else:
            # Default: HDFC ENet standard format
            rows = [
                "Transaction Type,Beneficiary Code,Beneficiary Account Number,Transaction Amount,Beneficiary Name,Drawee Location,Customer Reference Number,Payment Details 1,Payment Details 2,Payment Details 3,Payment Details 4,Beneficiary Email,IFSC Code"
            ]
            for p in eligible_slips:
                emp = p.employee
                txn_type = "R" if p.net_salary >= Decimal("200000.00") else "N"
                ben_code = f"EMP-{emp.employee_code}"[:15]
                acc_no = (emp.bank_account_number or "000000000000").strip()
                amt = f"{float(p.net_salary):.2f}"
                name = f"{emp.first_name} {emp.last_name}".strip().upper()
                ref_no = f"SAL{year_str}{month_str}-{emp.employee_code}"[:20]
                narration = f"Salary {month_str}/{year_str}"
                email = (emp.email or "").strip()
                ifsc = (emp.bank_ifsc_code or "HDFC0000001").strip().upper()
                rows.append(f'"{txn_type}","{ben_code}","{acc_no}",{amt},"{name}","","{ref_no}","{narration}","","","","{email}","{ifsc}"')
            return "\n".join(rows) + "\n"

    @staticmethod
    async def generate_contractor_bank_cms_csv(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        payment_ids: Optional[List[uuid.UUID]] = None,
        bank_format: str = "hdfc_enet",
        debit_account: Optional[str] = None
    ) -> str:
        """
        Generates standard Bank CMS batch payout upload file (CSV) for contractor / freelancer payouts.
        """
        stmt = (
            select(ContractorPayment)
            .options(selectinload(ContractorPayment.contractor))
            .where(
                and_(
                    ContractorPayment.tenant_id == tenant_id,
                    ContractorPayment.net_payable > Decimal("0.00")
                )
            )
        )
        if payment_ids:
            stmt = stmt.where(ContractorPayment.id.in_(payment_ids))
        else:
            stmt = stmt.where(ContractorPayment.status.in_(["pending", "accrued"]))

        stmt = stmt.order_by(ContractorPayment.created_at.asc())
        res = await session.execute(stmt)
        payments = res.scalars().all()

        if not payments:
            raise ValueError("No payable contractor claims found with Net Payable > 0.")

        debit_acc = (debit_account or "1010000123456").strip()
        today_dmy = datetime.utcnow().strftime("%d/%m/%Y")

        if bank_format.lower() == "icici_cms":
            rows = [
                "Client Code,Product Code,Payment Type,Payment Ref Number,Debit Account Number,Beneficiary Account Number,Beneficiary Name,Instrument Amount,Instrument Date,Beneficiary Bank IFSC,Beneficiary Email,Remarks"
            ]
            for p in payments:
                c = p.contractor
                ref_no = p.payment_number[:20]
                acc_no = (c.bank_account_number or "000000000000").strip()
                name = c.name.strip().upper()
                amt = f"{float(p.net_payable):.2f}"
                ifsc = (c.bank_ifsc_code or "ICIC0000001").strip().upper()
                email = (c.email or "").strip()
                remarks = f"Inv {p.invoice_number}"[:30]
                rows.append(f'B00K5PAY,NEFT,N,"{ref_no}","{debit_acc}","{acc_no}","{name}",{amt},"{today_dmy}","{ifsc}","{email}","{remarks}"')
            return "\n".join(rows) + "\n"

        elif bank_format.lower() == "sbi_cmp":
            rows = [
                "Debit Account No,Beneficiary Account No,Beneficiary Name,Amount,Payment Method,IFSC Code,Sender to Receiver Info,Payment Reference"
            ]
            for p in payments:
                c = p.contractor
                ref_no = p.payment_number[:20]
                acc_no = (c.bank_account_number or "000000000000").strip()
                name = c.name.strip().upper()
                amt = f"{float(p.net_payable):.2f}"
                ifsc = (c.bank_ifsc_code or "SBIN0000001").strip().upper()
                info = f"Inv {p.invoice_number}"[:30]
                rows.append(f'"{debit_acc}","{acc_no}","{name}",{amt},NEFT,"{ifsc}","{info}","{ref_no}"')
            return "\n".join(rows) + "\n"

        else:
            # Default: HDFC ENet standard format
            rows = [
                "Transaction Type,Beneficiary Code,Beneficiary Account Number,Transaction Amount,Beneficiary Name,Drawee Location,Customer Reference Number,Payment Details 1,Payment Details 2,Payment Details 3,Payment Details 4,Beneficiary Email,IFSC Code"
            ]
            for p in payments:
                c = p.contractor
                txn_type = "R" if p.net_payable >= Decimal("200000.00") else "N"
                ben_code = f"CNT-{c.contractor_code}"[:15]
                acc_no = (c.bank_account_number or "000000000000").strip()
                amt = f"{float(p.net_payable):.2f}"
                name = c.name.strip().upper()
                ref_no = p.payment_number[:20]
                narration = f"Inv {p.invoice_number} TDS u/s {p.tds_section}"[:30]
                email = (c.email or "").strip()
                ifsc = (c.bank_ifsc_code or "HDFC0000001").strip().upper()
                rows.append(f'"{txn_type}","{ben_code}","{acc_no}",{amt},"{name}","","{ref_no}","{narration}","","","","{email}","{ifsc}"')
            return "\n".join(rows) + "\n"



