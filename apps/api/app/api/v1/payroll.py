from typing import List, Optional, Any, Dict
import uuid
from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_user, get_current_tenant
from app.models.tenant import User, Tenant
from app.models.payroll import Employee, SalaryStructure, PayrollRun, Payslip, EmployeeTaxDeclaration, Contractor, ContractorPayment
from app.models.ledger import JournalEntry
from app.schemas.payroll import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    SalaryStructureCreate, SalaryStructureResponse,
    PayrollRunCreate, PayrollRunResponse, PayrollRunDetailResponse,
    PayslipResponse,
    EmployeeTaxDeclarationCreate, EmployeeTaxDeclarationResponse,
    Form16Response,
    ContractorCreate, ContractorUpdate, ContractorResponse,
    ContractorPaymentCreate, ContractorPaymentResponse,
    Form16AResponse
)
from app.services.payroll_service import PayrollService
from app.core.iam import require_owner, require_ca_or_owner, IAMContext
from app.core.fiscal_year import get_or_create_fiscal_year

router = APIRouter()


# ============================================================================
# 1. EMPLOYEES CRUD
# ============================================================================

@router.get("/employees", response_model=List[EmployeeResponse])
async def list_employees(
    status_filter: Optional[str] = Query(None, alias="status"),
    department: Optional[str] = None,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """List all employees for active tenant with optional status and department filters."""
    query = select(Employee).options(
        selectinload(Employee.salary_structures)
    ).where(Employee.tenant_id == ctx.tenant.id)

    if status_filter:
        query = query.where(Employee.status == status_filter)
    if department:
        query = query.where(Employee.department == department)

    query = query.order_by(Employee.employee_code.asc())
    res = await db.execute(query)
    return res.scalars().all()


@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Onboard a new employee with optional initial salary structure."""
    # Check duplicate employee code
    dup_code_stmt = select(Employee).where(
        and_(
            Employee.tenant_id == ctx.tenant.id,
            Employee.employee_code == payload.employee_code.strip()
        )
    )
    if (await db.execute(dup_code_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee code '{payload.employee_code}' already exists for this tenant."
        )

    # Check duplicate PAN
    dup_pan_stmt = select(Employee).where(
        and_(
            Employee.tenant_id == ctx.tenant.id,
            Employee.pan_number == payload.pan_number.strip().upper()
        )
    )
    if (await db.execute(dup_pan_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"PAN '{payload.pan_number}' already registered with another employee in this tenant."
        )

    emp = Employee(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant.id,
        employee_code=payload.employee_code.strip(),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=payload.email,
        phone=payload.phone,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        date_of_joining=payload.date_of_joining,
        date_of_exit=payload.date_of_exit,
        status=payload.status,
        employment_type=payload.employment_type,
        department=payload.department,
        designation=payload.designation.strip(),
        pan_number=payload.pan_number.strip().upper(),
        aadhaar_ref_id=payload.aadhaar_ref_id,
        uan_number=payload.uan_number,
        esic_number=payload.esic_number,
        bank_account_number=payload.bank_account_number.strip(),
        bank_ifsc_code=payload.bank_ifsc_code.strip().upper(),
        bank_name=payload.bank_name.strip(),
        tax_regime=payload.tax_regime,
        pt_state=payload.pt_state,
        pf_opt_out=payload.pf_opt_out,
        is_pf_capped=payload.is_pf_capped,
        is_esi_eligible=payload.is_esi_eligible
    )
    db.add(emp)
    await db.flush()

    if payload.initial_salary_structure:
        struct = SalaryStructure(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant.id,
            employee_id=emp.id,
            effective_from=payload.initial_salary_structure.effective_from,
            effective_to=payload.initial_salary_structure.effective_to,
            annual_ctc=payload.initial_salary_structure.annual_ctc,
            monthly_basic=payload.initial_salary_structure.monthly_basic,
            monthly_hra=payload.initial_salary_structure.monthly_hra,
            monthly_da=payload.initial_salary_structure.monthly_da,
            monthly_conveyance=payload.initial_salary_structure.monthly_conveyance,
            monthly_medical_allowance=payload.initial_salary_structure.monthly_medical_allowance,
            monthly_special_allowance=payload.initial_salary_structure.monthly_special_allowance,
            employer_pf_monthly=payload.initial_salary_structure.employer_pf_monthly,
            employer_esi_monthly=payload.initial_salary_structure.employer_esi_monthly,
            is_active=True
        )
        db.add(struct)
        await db.flush()

    await db.commit()

    # Re-fetch with salary structures loaded
    emp_reload = (await db.execute(
        select(Employee).options(selectinload(Employee.salary_structures)).where(Employee.id == emp.id)
    )).scalar_one()

    return emp_reload


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full employee details and salary structures."""
    stmt = select(Employee).options(
        selectinload(Employee.salary_structures)
    ).where(
        and_(
            Employee.id == employee_id,
            Employee.tenant_id == ctx.tenant.id
        )
    )
    emp = (await db.execute(stmt)).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
    return emp


@router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Update employee demographic, bank, or tax preferences."""
    stmt = select(Employee).options(
        selectinload(Employee.salary_structures)
    ).where(
        and_(
            Employee.id == employee_id,
            Employee.tenant_id == ctx.tenant.id
        )
    )
    emp = (await db.execute(stmt)).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    for k, v in payload.dict(exclude_unset=True).items():
        setattr(emp, k, v)

    await db.commit()
    return emp


@router.post("/salary-structures", response_model=SalaryStructureResponse, status_code=status.HTTP_201_CREATED)
async def create_salary_structure(
    payload: SalaryStructureCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Assign salary structure to an employee via top-level endpoint."""
    if not payload.employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="employee_id is required in payload.")
    return await add_salary_structure(payload.employee_id, payload, ctx, db)


@router.post("/employees/{employee_id}/salary-structure", response_model=SalaryStructureResponse, status_code=status.HTTP_201_CREATED)
async def add_salary_structure(
    employee_id: uuid.UUID,
    payload: SalaryStructureCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Assign a new salary structure revision to an employee, deactivating older active structures."""
    emp_stmt = select(Employee).where(
        and_(
            Employee.id == employee_id,
            Employee.tenant_id == ctx.tenant.id
        )
    )
    emp = (await db.execute(emp_stmt)).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    # Deactivate existing active structures
    old_structs_stmt = select(SalaryStructure).where(
        and_(
            SalaryStructure.employee_id == emp.id,
            SalaryStructure.is_active == True
        )
    )
    old_structs = (await db.execute(old_structs_stmt)).scalars().all()
    for s in old_structs:
        s.is_active = False

    new_struct = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant.id,
        employee_id=emp.id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        annual_ctc=payload.annual_ctc,
        monthly_basic=payload.monthly_basic,
        monthly_hra=payload.monthly_hra,
        monthly_da=payload.monthly_da,
        monthly_conveyance=payload.monthly_conveyance,
        monthly_medical_allowance=payload.monthly_medical_allowance,
        monthly_special_allowance=payload.monthly_special_allowance,
        employer_pf_monthly=payload.employer_pf_monthly,
        employer_esi_monthly=payload.employer_esi_monthly,
        is_active=True
    )
    db.add(new_struct)
    await db.commit()
    return new_struct


# ============================================================================
# 2. PAYROLL RUNS & GL INTEGRATION
# ============================================================================

@router.get("/runs", response_model=List[PayrollRunResponse])
async def list_payroll_runs(
    year: Optional[int] = None,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """List historical payroll runs for the tenant."""
    query = select(PayrollRun).where(PayrollRun.tenant_id == ctx.tenant.id)
    if year:
        query = query.where(PayrollRun.year == year)
    query = query.order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
    res = await db.execute(query)
    return res.scalars().all()


@router.post("/runs", response_model=PayrollRunResponse, status_code=status.HTTP_201_CREATED)
async def initialize_payroll_run(
    payload: PayrollRunCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Initialize a new monthly payroll run batch."""
    # Check duplicate run for month/year
    dup_stmt = select(PayrollRun).where(
        and_(
            PayrollRun.tenant_id == ctx.tenant.id,
            PayrollRun.month == payload.month,
            PayrollRun.year == payload.year
        )
    )
    if (await db.execute(dup_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payroll run for month {payload.month}/{payload.year} already exists."
        )

    # Determine fiscal year label
    if payload.month >= 4:
        fy_label = f"{payload.year}-{payload.year + 1}"
    else:
        fy_label = f"{payload.year - 1}-{payload.year}"

    run_number = f"PR-{payload.year}-{payload.month:02d}"

    run = PayrollRun(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant.id,
        run_number=run_number,
        month=payload.month,
        year=payload.year,
        fiscal_year=payload.fiscal_year or fy_label,
        status="draft"
    )
    db.add(run)
    await db.flush()

    # Automatically trigger initial calculation
    run = await PayrollService.calculate_payroll_run(db, run.id)
    await db.commit()
    return run


@router.get("/runs/{run_id}", response_model=PayrollRunDetailResponse)
async def get_payroll_run_detail(
    run_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full payroll run batch details and all itemized payslips."""
    stmt = select(PayrollRun).options(
        selectinload(PayrollRun.payslips)
    ).where(
        and_(
            PayrollRun.id == run_id,
            PayrollRun.tenant_id == ctx.tenant.id
        )
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found.")
    return run


@router.post("/runs/{run_id}/calculate", response_model=PayrollRunDetailResponse)
async def recalculate_payroll_run(
    run_id: uuid.UUID,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Recalculate attendance, gross earnings, withholdings, and net salary for a draft payroll run."""
    try:
        run = await PayrollService.calculate_payroll_run(db, run_id)
        await db.commit()
        # Reload with payslips
        stmt = select(PayrollRun).options(selectinload(PayrollRun.payslips)).where(PayrollRun.id == run.id)
        return (await db.execute(stmt)).scalar_one()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/runs/{run_id}/lock-and-post-accrual")
async def lock_and_post_accrual(
    run_id: uuid.UUID,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Locks the payroll run and posts Leg 1 (Accrual Journal Voucher) to the General Ledger:
    Dr. 4020, 4021, 4022 vs Cr. 2070 (Net Pay) and Cr. 2071-2076 (Statutory Withholdings).
    """
    try:
        entry = await PayrollService.post_accrual_journal(db, run_id, created_by_user_id=ctx.user.id)
        await db.commit()
        # Fetch updated run
        run_stmt = select(PayrollRun).where(PayrollRun.id == run_id)
        updated_run = (await db.execute(run_stmt)).scalar_one()
        return {
            "status": updated_run.status,
            "message": "Payroll accrual voucher posted successfully and run locked.",
            "accrual_journal_id": entry.id,
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date,
            "sha256_audit_hash": updated_run.sha256_audit_hash
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/runs/{run_id}/post-disbursement")
async def post_disbursement(
    run_id: uuid.UUID,
    bank_account_code: str = Query("1010", description="Bank COA code, e.g. 1010"),
    payout_utr: Optional[str] = Query(None, description="Bank Transaction UTR / CMS Batch Ref"),
    disbursement_date: Optional[date] = None,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Posts Leg 2 (Salary Disbursement Journal Voucher) to the General Ledger:
    Dr. 2070 Salaries Payable = Net Pay
    Cr. 1010 Bank Account    = Net Pay
    Marks all payslips as 'paid'.
    """
    try:
        entry = await PayrollService.post_disbursement_journal(
            session=db,
            run_id=run_id,
            bank_account_code=bank_account_code,
            payout_utr=payout_utr,
            disbursement_date=disbursement_date,
            created_by_user_id=ctx.user.id
        )
        await db.commit()
        # Fetch updated run
        run_stmt = select(PayrollRun).where(PayrollRun.id == run_id)
        updated_run = (await db.execute(run_stmt)).scalar_one()
        return {
            "status": updated_run.status,
            "message": "Salary disbursement voucher posted successfully.",
            "disbursement_journal_id": entry.id,
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# 3. PAYSLIPS & TAX DECLARATIONS
# ============================================================================

@router.get("/runs/{run_id}/payslips", response_model=List[PayslipResponse])
async def list_payslips_for_run(
    run_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all itemized payslips for a specific payroll run."""
    stmt = select(Payslip).where(
        and_(
            Payslip.payroll_run_id == run_id,
            Payslip.tenant_id == ctx.tenant.id
        )
    ).order_by(Payslip.payslip_number.asc())
    return (await db.execute(stmt)).scalars().all()


@router.get("/payslips/{payslip_id}", response_model=PayslipResponse)
async def get_payslip(
    payslip_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve individual payslip details."""
    stmt = select(Payslip).where(
        and_(
            Payslip.id == payslip_id,
            Payslip.tenant_id == ctx.tenant.id
        )
    )
    payslip = (await db.execute(stmt)).scalar_one_or_none()
    if not payslip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payslip not found.")
    return payslip


@router.post("/tax-declarations", response_model=EmployeeTaxDeclarationResponse, status_code=status.HTTP_201_CREATED)
async def submit_tax_declaration(
    payload: EmployeeTaxDeclarationCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Submit Chapter VI-A investment declarations for an employee."""
    emp_stmt = select(Employee).where(
        and_(
            Employee.id == payload.employee_id,
            Employee.tenant_id == ctx.tenant.id
        )
    )
    emp = (await db.execute(emp_stmt)).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    # Check existing declaration for FY
    existing_stmt = select(EmployeeTaxDeclaration).where(
        and_(
            EmployeeTaxDeclaration.employee_id == payload.employee_id,
            EmployeeTaxDeclaration.fiscal_year == payload.fiscal_year
        )
    )
    decl = (await db.execute(existing_stmt)).scalar_one_or_none()

    if not decl:
        decl = EmployeeTaxDeclaration(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant.id,
            employee_id=payload.employee_id,
            fiscal_year=payload.fiscal_year
        )
        db.add(decl)

    decl.regime = payload.regime
    decl.sec_80c_lic = payload.sec_80c_lic
    decl.sec_80c_ppf = payload.sec_80c_ppf
    decl.sec_80c_elss = payload.sec_80c_elss
    decl.sec_80c_home_loan_principal = payload.sec_80c_home_loan_principal
    decl.sec_80c_tuition_fees = payload.sec_80c_tuition_fees
    decl.sec_80c_total_claimed = (
        payload.sec_80c_lic + payload.sec_80c_ppf + payload.sec_80c_elss +
        payload.sec_80c_home_loan_principal + payload.sec_80c_tuition_fees
    )
    decl.sec_80c_total_verified = decl.sec_80c_total_claimed # Auto-verified for standard declarations
    decl.sec_80d_self_family = payload.sec_80d_self_family
    decl.sec_80d_parents = payload.sec_80d_parents
    decl.sec_24b_home_loan_interest = payload.sec_24b_home_loan_interest
    decl.lender_pan = payload.lender_pan
    decl.annual_rent_paid = payload.annual_rent_paid
    decl.landlord_pan = payload.landlord_pan
    decl.rental_address = payload.rental_address
    decl.is_metro_city = payload.is_metro_city
    decl.verification_status = "verified"
    decl.verified_by = ctx.user.id
    decl.verified_at = datetime.utcnow()

    await db.commit()
    return decl


# ============================================================================
# 4. STATUTORY EXPORTERS & FORM 16 SUITE
# ============================================================================

@router.get("/runs/{run_id}/export/epfo-ecr")
async def export_epfo_ecr(
    run_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports official EPFO Electronic Challan cum Return (ECR 2.0) text file
    with #~# delimiters for direct upload to EPFO Unified Portal.
    """
    stmt = select(PayrollRun).where(
        and_(PayrollRun.id == run_id, PayrollRun.tenant_id == ctx.tenant.id)
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found.")

    txt_content = await PayrollService.generate_epfo_ecr_txt(db, run_id)
    filename = f"ECR_{run.run_number}_{run.month:02d}_{run.year}.txt"
    return Response(
        content=txt_content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/runs/{run_id}/export/esic")
async def export_esic_return(
    run_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports official ESIC Monthly Return upload CSV formatted for ESIC IP Portal.
    """
    stmt = select(PayrollRun).where(
        and_(PayrollRun.id == run_id, PayrollRun.tenant_id == ctx.tenant.id)
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found.")

    csv_content = await PayrollService.generate_esic_return_csv(db, run_id)
    filename = f"ESIC_{run.run_number}_{run.month:02d}_{run.year}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/runs/{run_id}/export/pt")
async def export_pt_return(
    run_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports State-Wise Professional Tax (PT) Monthly Return summary CSV file.
    """
    stmt = select(PayrollRun).where(
        and_(PayrollRun.id == run_id, PayrollRun.tenant_id == ctx.tenant.id)
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found.")

    csv_content = await PayrollService.generate_pt_return_csv(db, run_id)
    filename = f"PT_Return_{run.run_number}_{run.month:02d}_{run.year}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/employees/{employee_id}/form-16", response_model=Form16Response)
async def get_form_16(
    employee_id: uuid.UUID,
    fiscal_year: Optional[str] = Query(None, alias="financial_year"),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculates annual Form 16 Part A and Part B salary and TDS breakdown under Section 203 of Income-tax Act, 1961.
    """
    emp_stmt = select(Employee).where(
        and_(Employee.id == employee_id, Employee.tenant_id == ctx.tenant.id)
    )
    emp = (await db.execute(emp_stmt)).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    try:
        data = await PayrollService.calculate_form_16(db, employee_id, fiscal_year)
        return data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/employees/{employee_id}/form-16/pdf")
async def download_form_16_pdf(
    employee_id: uuid.UUID,
    fiscal_year: Optional[str] = Query(None, alias="financial_year"),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates and downloads certified Form 16 Part A and Part B PDF certificate.
    """
    emp_stmt = select(Employee).where(
        and_(Employee.id == employee_id, Employee.tenant_id == ctx.tenant.id)
    )
    emp = (await db.execute(emp_stmt)).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    try:
        pdf_bytes = await PayrollService.generate_form_16_pdf_for_employee(db, employee_id, fiscal_year)
        fy_clean = (fiscal_year or "2026-27").replace("/", "-")
        filename = f"Form16_{emp.employee_code}_{fy_clean}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# 8. CONTRACTORS & FREELANCERS (PHASE 3 / SECTION 194C & 194J)
# ============================================================================

@router.post("/contractors", response_model=ContractorResponse, status_code=status.HTTP_201_CREATED)
async def create_contractor(
    payload: ContractorCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Onboard a new contractor or professional freelancer."""
    try:
        return await PayrollService.onboard_contractor(db, ctx.tenant.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/contractors", response_model=List[ContractorResponse])
async def list_contractors(
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """List all contractors and professional freelancers for the active tenant."""
    return await PayrollService.get_contractors(db, ctx.tenant.id)


@router.get("/contractors/{contractor_id}", response_model=ContractorResponse)
async def get_contractor(
    contractor_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve contractor details."""
    contractor = await PayrollService.get_contractor(db, ctx.tenant.id, contractor_id)
    if not contractor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found.")
    return contractor


@router.post("/contractor-payments", response_model=ContractorPaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_contractor_payment(
    payload: ContractorPaymentCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Record an invoice or retainer claim for a contractor with auto-calculated TDS."""
    try:
        payment = await PayrollService.create_contractor_payment(db, ctx.tenant.id, payload)
        contractor = await PayrollService.get_contractor(db, ctx.tenant.id, payment.contractor_id)
        res = ContractorPaymentResponse.model_validate(payment)
        if contractor:
            res.contractor_name = contractor.name
            res.contractor_pan = contractor.pan_number
            res.contractor_code = contractor.contractor_code
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/contractor-payments", response_model=List[ContractorPaymentResponse])
async def list_contractor_payments(
    contractor_id: Optional[uuid.UUID] = None,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """List contractor payment records with TDS breakdowns."""
    payments = await PayrollService.get_contractor_payments(db, ctx.tenant.id, contractor_id)
    results = []
    for p in payments:
        res = ContractorPaymentResponse.model_validate(p)
        if p.contractor:
            res.contractor_name = p.contractor.name
            res.contractor_pan = p.contractor.pan_number
            res.contractor_code = p.contractor.contractor_code
        results.append(res)
    return results


@router.post("/contractor-payments/{payment_id}/accrue", response_model=ContractorPaymentResponse)
async def accrue_contractor_payment(
    payment_id: uuid.UUID,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Leg 1: Post contractor invoice accrual to General Ledger."""
    try:
        payment = await PayrollService.accrue_contractor_payment(db, ctx.tenant.id, payment_id, ctx.user.id)
        contractor = await PayrollService.get_contractor(db, ctx.tenant.id, payment.contractor_id)
        res = ContractorPaymentResponse.model_validate(payment)
        if contractor:
            res.contractor_name = contractor.name
            res.contractor_pan = contractor.pan_number
            res.contractor_code = contractor.contractor_code
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/contractor-payments/{payment_id}/disburse", response_model=ContractorPaymentResponse)
async def disburse_contractor_payment(
    payment_id: uuid.UUID,
    utr: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """Leg 2: Post contractor payment disbursement from bank account to General Ledger."""
    try:
        payment = await PayrollService.disburse_contractor_payment(db, ctx.tenant.id, payment_id, ctx.user.id, utr)
        contractor = await PayrollService.get_contractor(db, ctx.tenant.id, payment.contractor_id)
        res = ContractorPaymentResponse.model_validate(payment)
        if contractor:
            res.contractor_name = contractor.name
            res.contractor_pan = contractor.pan_number
            res.contractor_code = contractor.contractor_code
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/contractors/{contractor_id}/form-16a", response_model=Form16AResponse)
async def get_form_16a(
    contractor_id: uuid.UUID,
    fiscal_year: Optional[str] = Query(None, alias="financial_year"),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """Calculates Form 16A quarterly / annual TDS withholding summary for a contractor."""
    try:
        return await PayrollService.calculate_form_16a(db, contractor_id, fiscal_year)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/contractors/{contractor_id}/form-16a/pdf")
async def download_form_16a_pdf(
    contractor_id: uuid.UUID,
    fiscal_year: Optional[str] = Query(None, alias="financial_year"),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """Generates and downloads certified Form 16A TDS certificate PDF under Section 203."""
    contractor = await PayrollService.get_contractor(db, ctx.tenant.id, contractor_id)
    if not contractor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found.")

    try:
        pdf_bytes = await PayrollService.generate_form_16a_pdf_for_contractor(db, contractor_id, fiscal_year)
        fy_clean = (fiscal_year or "2026-27").replace("/", "-")
        filename = f"Form16A_{contractor.contractor_code}_{fy_clean}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



