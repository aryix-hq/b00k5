import pytest
from decimal import Decimal
import uuid
from datetime import date

from app.models.payroll import Employee, SalaryStructure, PayrollRun, Payslip
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.payroll_service import PayrollService, round_curr


def test_statutory_tds_192_calculation():
    """Verifies Income Tax Section 192 withholding under Finance Act 2024."""
    # 1. New Tax Regime: Taxable income <= 7L is exempt via Section 87A rebate
    # Annual gross of 7,75,000 - 75,000 std deduction = 7,00,000 taxable -> Nil tax
    tax_775k = PayrollService.calculate_statutory_tds_192(
        projected_annual_gross=Decimal("775000.00"),
        regime="new_115bac"
    )
    assert tax_775k == Decimal("0.00")

    # 2. New Tax Regime: Annual gross 12,75,000
    # Standard deduction = 75,000 -> Taxable = 12,00,000
    # Slabs:
    # 0 - 3L: 0
    # 3L - 7L: 4L * 5% = 20,000
    # 7L - 10L: 3L * 10% = 30,000
    # 10L - 12L: 2L * 15% = 30,000
    # Total tax = 80,000 + 4% cess = 83,200
    tax_1275k = PayrollService.calculate_statutory_tds_192(
        projected_annual_gross=Decimal("1275000.00"),
        regime="new_115bac"
    )
    assert tax_1275k == Decimal("83200.00")

    # 3. Old Tax Regime with 80C, 80D, 24b deductions
    # Gross = 12,00,000; Std Ded = 50,000; 80C = 1,50,000; 80D = 25,000; 24b = 2,00,000
    # Taxable = 12,00,000 - 4,25,000 = 7,75,000
    # Slabs:
    # 0 - 2.5L: 0
    # 2.5L - 5L: 2.5L * 5% = 12,500
    # 5L - 7.75L: 2.75L * 20% = 55,000
    # Total = 67,500 + 4% cess = 70,200
    tax_old = PayrollService.calculate_statutory_tds_192(
        projected_annual_gross=Decimal("1200000.00"),
        regime="old_regime",
        verified_80c=Decimal("150000.00"),
        verified_80d=Decimal("25000.00"),
        verified_24b=Decimal("200000.00")
    )
    assert tax_old == Decimal("70200.00")


def test_professional_tax_state_rules():
    """Verifies state-specific Professional Tax (PT) calculations."""
    # Karnataka: Gross >= 25,000 -> 200, else Nil
    assert PayrollService.calculate_professional_tax(Decimal("24999.00"), "Karnataka") == Decimal("0.00")
    assert PayrollService.calculate_professional_tax(Decimal("25000.00"), "Karnataka") == Decimal("200.00")
    assert PayrollService.calculate_professional_tax(Decimal("80000.00"), "Karnataka") == Decimal("200.00")

    # Maharashtra: Regular months = 200, February = 300
    assert PayrollService.calculate_professional_tax(Decimal("50000.00"), "Maharashtra", month=4) == Decimal("200.00")
    assert PayrollService.calculate_professional_tax(Decimal("50000.00"), "Maharashtra", month=2) == Decimal("300.00")

    # Delhi: Zero PT
    assert PayrollService.calculate_professional_tax(Decimal("100000.00"), "Delhi") == Decimal("0.00")


def test_epf_act_1952_capping_and_uncapping():
    """Verifies EPF statutory capping at Rs 15,000 vs voluntary uncapped contributions."""
    emp_capped = Employee(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        employee_code="EMP-001",
        first_name="Rohan",
        last_name="Sharma",
        email="rohan@example.com",
        date_of_birth=date(1992, 5, 14),
        date_of_joining=date(2025, 4, 1),
        designation="Software Engineer",
        pan_number="ABCDE1234F",
        bank_account_number="912010023456789",
        bank_ifsc_code="HDFC0000123",
        bank_name="HDFC Bank",
        is_pf_capped=True,
        pf_opt_out=False,
        is_esi_eligible=False
    )

    struct = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=emp_capped.tenant_id,
        employee_id=emp_capped.id,
        effective_from=date(2025, 4, 1),
        annual_ctc=Decimal("1200000.00"),
        monthly_basic=Decimal("50000.00"),
        monthly_hra=Decimal("25000.00"),
        monthly_da=Decimal("0.00"),
        monthly_conveyance=Decimal("5000.00"),
        monthly_medical_allowance=Decimal("0.00"),
        monthly_special_allowance=Decimal("20000.00"),
        employer_pf_monthly=Decimal("1800.00"),
        employer_esi_monthly=Decimal("0.00"),
        is_active=True
    )

    # 1. Capped test: Basic is 50k, but PF wage must be capped at 15,000
    res_capped = PayrollService.calculate_employee_payslip(
        employee=emp_capped,
        structure=struct,
        total_days=30,
        paid_days=Decimal("30.00"),
        month=4,
        year=2026
    )

    assert res_capped["gross_earnings"] == Decimal("100000.00")
    # Employee 12% of 15,000 = 1,800
    assert res_capped["employee_pf"] == Decimal("1800.00")
    # EPS = 8.33% of 15,000 capped at 1,250
    assert res_capped["employer_eps"] == Decimal("1249.50") # 15000 * 0.0833
    # Remainder goes to Employer PF
    assert res_capped["employer_pf"] == Decimal("550.50")
    # Total employer PF (PF + EPS) = 1,800
    assert res_capped["employer_pf"] + res_capped["employer_eps"] == Decimal("1800.00")

    # 2. Uncapped test: Basic is 50k, 12% on actual Basic
    emp_uncapped = Employee(
        id=uuid.uuid4(),
        tenant_id=emp_capped.tenant_id,
        employee_code="EMP-002",
        first_name="Pooja",
        last_name="Iyer",
        email="pooja@example.com",
        date_of_birth=date(1994, 8, 20),
        date_of_joining=date(2025, 4, 1),
        designation="Product Manager",
        pan_number="AAACA5678K",
        bank_account_number="912010098765432",
        bank_ifsc_code="ICIC0000456",
        bank_name="ICICI Bank",
        is_pf_capped=False,
        pf_opt_out=False,
        is_esi_eligible=False
    )

    res_uncapped = PayrollService.calculate_employee_payslip(
        employee=emp_uncapped,
        structure=struct,
        total_days=30,
        paid_days=Decimal("30.00"),
        month=4,
        year=2026
    )

    # 12% of 50,000 = 6,000
    assert res_uncapped["employee_pf"] == Decimal("6000.00")
    # EPS capped at 1,250
    assert res_uncapped["employer_eps"] == Decimal("1250.00")
    # Remainder 6000 - 1250 = 4750
    assert res_uncapped["employer_pf"] == Decimal("4750.00")


def test_esi_threshold_and_contributions():
    """Verifies ESI Act 1948 Rs 21,000 gross ceiling rule."""
    emp_low_wage = Employee(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        employee_code="EMP-003",
        first_name="Suresh",
        last_name="Kumar",
        email="suresh@example.com",
        date_of_birth=date(1998, 1, 10),
        date_of_joining=date(2025, 4, 1),
        designation="Junior Support",
        pan_number="AABCA9012P",
        bank_account_number="912010011223344",
        bank_ifsc_code="SBIN0001234",
        bank_name="SBI",
        is_pf_capped=True,
        pf_opt_out=False,
        is_esi_eligible=True
    )

    struct_low = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=emp_low_wage.tenant_id,
        employee_id=emp_low_wage.id,
        effective_from=date(2025, 4, 1),
        annual_ctc=Decimal("240000.00"),
        monthly_basic=Decimal("12000.00"),
        monthly_hra=Decimal("4000.00"),
        monthly_da=Decimal("0.00"),
        monthly_conveyance=Decimal("2000.00"),
        monthly_medical_allowance=Decimal("0.00"),
        monthly_special_allowance=Decimal("2000.00"), # Gross = 20,000 <= 21,000
        employer_pf_monthly=Decimal("1440.00"),
        employer_esi_monthly=Decimal("650.00"),
        is_active=True
    )

    res = PayrollService.calculate_employee_payslip(
        employee=emp_low_wage,
        structure=struct_low,
        total_days=30,
        paid_days=Decimal("30.00"),
        month=4,
        year=2026
    )

    assert res["gross_earnings"] == Decimal("20000.00")
    # Employee 0.75% of 20,000 = 150
    assert res["employee_esi"] == Decimal("150.00")
    # Employer 3.25% of 20,000 = 650
    assert res["employer_esi"] == Decimal("650.00")


def test_loss_of_pay_proration():
    """Verifies exact Banker's Rounding proration when employee takes 5 days unpaid leave."""
    emp = Employee(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        employee_code="EMP-004",
        first_name="Deepa",
        last_name="Nair",
        email="deepa@example.com",
        date_of_birth=date(1995, 3, 22),
        date_of_joining=date(2025, 4, 1),
        designation="QA Engineer",
        pan_number="AABCS3456V",
        bank_account_number="912010055667788",
        bank_ifsc_code="HDFC0000789",
        bank_name="HDFC Bank",
        is_pf_capped=True,
        pf_opt_out=False,
        is_esi_eligible=False
    )

    struct = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=emp.tenant_id,
        employee_id=emp.id,
        effective_from=date(2025, 4, 1),
        annual_ctc=Decimal("600000.00"),
        monthly_basic=Decimal("25000.00"),
        monthly_hra=Decimal("12500.00"),
        monthly_da=Decimal("0.00"),
        monthly_conveyance=Decimal("2500.00"),
        monthly_medical_allowance=Decimal("0.00"),
        monthly_special_allowance=Decimal("10000.00"), # Gross = 50,000
        employer_pf_monthly=Decimal("1800.00"),
        employer_esi_monthly=Decimal("0.00"),
        is_active=True
    )

    # 30 days total, 25 paid (5 days LOP) -> factor = 25/30 = 0.8333333333...
    res = PayrollService.calculate_employee_payslip(
        employee=emp,
        structure=struct,
        total_days=30,
        paid_days=Decimal("25.00"),
        loss_of_pay_days=Decimal("5.00"),
        month=4,
        year=2026
    )

    # Basic: 25000 * 25 / 30 = 20833.33
    assert res["basic_earned"] == Decimal("20833.33")
    # Gross: sum of prorated components = 41666.66
    assert res["gross_earnings"] == Decimal("41666.66")
    # Net Pay = Gross - Deductions
    assert res["net_salary"] == res["gross_earnings"] - res["total_deductions"]
    assert res["paid_days"] == Decimal("25.00")
    assert res["loss_of_pay_days"] == Decimal("5.00")


@pytest.mark.asyncio
async def test_payroll_e2e_ledger_lifecycle_and_invariance():
    """
    End-to-end integration test against PostgreSQL 16:
    1. Provisions isolated test tenant and seeds Chart of Accounts.
    2. Onboards 2 employees with CTC structures.
    3. Calculates April 2026 payroll run.
    4. Posts Leg 1 (Accrual Journal) -> Verifies exact double-entry balance and SHA-256 seal.
    5. Posts Leg 2 (Disbursement Journal) -> Verifies bank debit and payslip 'paid' status.
    6. Verifies RLS tenant boundary isolation.
    """
    from app.core.database import AsyncSessionLocal, set_tenant_context
    from app.models.tenant import Tenant, User
    from sqlalchemy import select, and_, text

    async with AsyncSessionLocal() as session:
        # 1. Create Tenant
        tenant_id = uuid.uuid4()
        tenant = Tenant(
            id=tenant_id,
            legal_name="Payroll Test Labs Pvt Ltd",
            trade_name="Payroll Labs",
            cin=f"U72200KA2026PTC{tenant_id.hex[:6].upper()}",
            gstin=f"29ABCDE{tenant_id.hex[:4].upper()}1Z5",
            pan=f"ABCDE{tenant_id.hex[:4].upper()}",
            state_code="29",
            registered_office="Koramangala, Bengaluru, Karnataka 560034"
        )
        session.add(tenant)
        await session.flush()

        # Seed COA
        await session.execute(text(f"SELECT seed_tenant_chart_of_accounts('{tenant_id}')"))
        await session.flush()

        # Set RLS Context
        await set_tenant_context(session, tenant_id)

        # 2. Onboard Employee 1 (Senior Engineer)
        emp1 = Employee(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            employee_code="EMP-101",
            first_name="Vikram",
            last_name="Aditya",
            email="vikram@example.com",
            date_of_birth=date(1990, 8, 15),
            date_of_joining=date(2025, 4, 1),
            designation="Principal Engineer",
            pan_number="AABCA1234D",
            bank_account_number="10002000300040",
            bank_ifsc_code="HDFC0000100",
            bank_name="HDFC Bank",
            tax_regime="new_115bac",
            pt_state="Karnataka",
            is_pf_capped=True,
            is_esi_eligible=False
        )
        session.add(emp1)
        await session.flush()

        struct1 = SalaryStructure(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            employee_id=emp1.id,
            effective_from=date(2025, 4, 1),
            annual_ctc=Decimal("1500000.00"),
            monthly_basic=Decimal("60000.00"),
            monthly_hra=Decimal("30000.00"),
            monthly_da=Decimal("0.00"),
            monthly_conveyance=Decimal("5000.00"),
            monthly_medical_allowance=Decimal("0.00"),
            monthly_special_allowance=Decimal("30000.00"), # Gross = 125,000
            employer_pf_monthly=Decimal("1800.00"),
            employer_esi_monthly=Decimal("0.00"),
            is_active=True
        )
        session.add(struct1)

        # Onboard Employee 2 (Associate with ESI)
        emp2 = Employee(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            employee_code="EMP-102",
            first_name="Anjali",
            last_name="Menon",
            email="anjali@example.com",
            date_of_birth=date(1997, 11, 25),
            date_of_joining=date(2025, 4, 1),
            designation="Operations Associate",
            pan_number="AABCK5678E",
            bank_account_number="50006000700080",
            bank_ifsc_code="ICIC0000200",
            bank_name="ICICI Bank",
            tax_regime="new_115bac",
            pt_state="Karnataka",
            is_pf_capped=True,
            is_esi_eligible=True
        )
        session.add(emp2)
        await session.flush()

        struct2 = SalaryStructure(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            employee_id=emp2.id,
            effective_from=date(2025, 4, 1),
            annual_ctc=Decimal("240000.00"),
            monthly_basic=Decimal("10000.00"),
            monthly_hra=Decimal("5000.00"),
            monthly_da=Decimal("0.00"),
            monthly_conveyance=Decimal("2000.00"),
            monthly_medical_allowance=Decimal("0.00"),
            monthly_special_allowance=Decimal("3000.00"), # Gross = 20,000 <= 21,000
            employer_pf_monthly=Decimal("1200.00"),
            employer_esi_monthly=Decimal("650.00"),
            is_active=True
        )
        session.add(struct2)
        await session.flush()

        # 3. Initialize & Calculate Payroll Run for April 2026
        run_id = uuid.uuid4()
        run = PayrollRun(
            id=run_id,
            tenant_id=tenant_id,
            run_number="PR-2026-04",
            month=4,
            year=2026,
            fiscal_year="2026-2027",
            status="draft"
        )
        session.add(run)
        await session.flush()

        calculated_run = await PayrollService.calculate_payroll_run(session, run_id)
        assert calculated_run.total_employees == 2
        assert calculated_run.status == "calculated"
        assert calculated_run.total_gross_pay == Decimal("145000.00") # 125,000 + 20,000
        assert calculated_run.total_net_pay > Decimal("0.00")
        assert calculated_run.total_deductions > Decimal("0.00")
        # Net + Deductions must strictly equal Gross
        assert calculated_run.total_net_pay + calculated_run.total_deductions == calculated_run.total_gross_pay

        # 4. Post Leg 1: Month-End Accrual Journal Voucher
        accrual_entry = await PayrollService.post_accrual_journal(session, run_id)
        assert accrual_entry is not None
        assert calculated_run.status == "locked"
        assert calculated_run.sha256_audit_hash is not None
        assert len(calculated_run.sha256_audit_hash) == 64

        # Verify Journal Lines and Strict Double-Entry Balance
        lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == accrual_entry.id)
        accrual_lines = (await session.execute(lines_stmt)).scalars().all()
        assert len(accrual_lines) >= 6

        total_debits = sum(line.debit_amount for line in accrual_lines)
        total_credits = sum(line.credit_amount for line in accrual_lines)
        diff = abs(total_debits - total_credits)
        assert diff == Decimal("0.00"), f"Leg 1 Double-Entry Imbalance! Debits={total_debits}, Credits={total_credits}"

        # 5. Post Leg 2: Salary Disbursement Journal Voucher
        disbursement_entry = await PayrollService.post_disbursement_journal(
            session=session,
            run_id=run_id,
            bank_account_code="1010",
            payout_utr="HDFCR5202604300001928"
        )
        assert disbursement_entry is not None
        assert calculated_run.status == "disbursed"

        # Verify Disbursement Double-Entry Balance
        disb_lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == disbursement_entry.id)
        disb_lines = (await session.execute(disb_lines_stmt)).scalars().all()
        assert len(disb_lines) == 2
        disb_debits = sum(line.debit_amount for line in disb_lines)
        disb_credits = sum(line.credit_amount for line in disb_lines)
        assert disb_debits == disb_credits == calculated_run.total_net_pay

        # Verify Payslips are marked 'paid'
        slips_stmt = select(Payslip).where(Payslip.payroll_run_id == run_id)
        slips = (await session.execute(slips_stmt)).scalars().all()
        for s in slips:
            assert s.payout_status == "paid"
            assert s.payout_utr == "HDFCR5202604300001928"

        # 6. Verify RLS Boundary Isolation
        foreign_tenant_id = uuid.uuid4()
        await set_tenant_context(session, foreign_tenant_id)

        foreign_emp_stmt = select(Employee).where(Employee.tenant_id == tenant_id)
        foreign_emps = (await session.execute(foreign_emp_stmt)).scalars().all()
        assert len(foreign_emps) == 0, "RLS Breach! Foreign tenant accessed private employee records."

        foreign_run_stmt = select(PayrollRun).where(PayrollRun.tenant_id == tenant_id)
        foreign_runs = (await session.execute(foreign_run_stmt)).scalars().all()
        assert len(foreign_runs) == 0, "RLS Breach! Foreign tenant accessed private payroll run."

        # Clean rollback test transaction
        await session.rollback()

