import uuid
from typing import Optional, List, Any, Dict
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.api.deps import get_db
from app.core.iam import require_any_employee, require_ca_or_owner, IAMContext
from app.schemas.tds import (
    TDSCalculateRequest,
    TDSCalculateResponse,
    TDSDeductionCreate,
    TDSDeductionResponse,
    TDSChallanCreate,
    TDSChallanResponse,
    TDSSummaryResponse
)
from app.services.tds_service import TDSService
from app.models.tds import TDSDeduction, TDSChallan


router = APIRouter()


@router.post("/calculate", response_model=TDSCalculateResponse)
async def calculate_tds(
    payload: TDSCalculateRequest,
    ctx: IAMContext = Depends(require_any_employee)
):
    """
    Calculates statutory Indian TDS withholding according to Income Tax rules:
    - Section 194C, 194J, 194I, 194Q
    - Section 206AA penal rate for invalid or missing PAN
    """
    try:
        res = TDSService.calculate_tds(
            gross_amount=payload.gross_amount,
            section=payload.section,
            deductee_type=payload.deductee_type,
            pan=payload.pan,
            is_lower_deduction=payload.is_lower_deduction,
            lower_deduction_rate=payload.lower_deduction_rate
        )
        return TDSCalculateResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/deductions", response_model=TDSDeductionResponse)
async def create_tds_deduction(
    payload: TDSDeductionCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Records a TDS deduction entry linked to a vendor bill or standalone voucher.
    """
    try:
        ded = await TDSService.record_tds_deduction(
            db=db,
            tenant_id=ctx.tenant.id,
            deductee_name=payload.deductee_name,
            deductee_pan=payload.deductee_pan,
            section=payload.section,
            gross_amount=payload.gross_amount,
            expense_id=payload.expense_id,
            rate_percentage=payload.rate_percentage,
            deduction_date=payload.deduction_date,
            deductee_type=payload.deductee_type
        )
        await db.commit()
        await db.refresh(ded)
        return ded
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/deductions", response_model=List[TDSDeductionResponse])
async def list_tds_deductions(
    fiscal_year: Optional[str] = Query(None, description="e.g. 2026-27"),
    quarter: Optional[str] = Query(None, description="Q1, Q2, Q3, Q4"),
    section: Optional[str] = Query(None, description="194C, 194J, etc."),
    status: Optional[str] = Query(None, description="PENDING_DEPOSIT, DEPOSITED"),
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves all recorded TDS deductions for the tenant with optional statutory filters.
    """
    query = select(TDSDeduction).where(TDSDeduction.tenant_id == ctx.tenant.id)
    if fiscal_year:
        query = query.where(TDSDeduction.fiscal_year == fiscal_year)
    if quarter:
        query = query.where(TDSDeduction.quarter == quarter.upper())
    if section:
        query = query.where(TDSDeduction.section == section.upper())
    if status:
        query = query.where(TDSDeduction.status == status.upper())

    query = query.order_by(desc(TDSDeduction.deduction_date), desc(TDSDeduction.created_at))
    res = await db.execute(query)
    return list(res.scalars().all())


@router.post("/record-challan", response_model=Dict[str, Any])
async def record_tds_challan(
    payload: TDSChallanCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Records a Challan ITNS 281 tax deposit, updates linked deductions to DEPOSITED,
    and automatically posts a balanced Journal Entry (DR TDS Payable, CR Bank).
    """
    try:
        res = await TDSService.record_challan_itns281(
            db=db,
            tenant_id=ctx.tenant.id,
            fiscal_year=payload.fiscal_year,
            quarter=payload.quarter,
            section=payload.section,
            bsr_code=payload.bsr_code,
            challan_serial_no=payload.challan_serial_no,
            payment_date=payload.payment_date,
            tds_amount=payload.tds_amount,
            surcharge_amount=payload.surcharge_amount,
            cess_amount=payload.cess_amount,
            interest_amount=payload.interest_amount,
            fee_amount=payload.fee_amount,
            cin=payload.cin,
            minor_head=payload.minor_head,
            deduction_ids=payload.deduction_ids,
            auto_post_jv=True,
            created_by=ctx.user.id
        )
        return res
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/challans", response_model=List[TDSChallanResponse])
async def list_tds_challans(
    fiscal_year: Optional[str] = Query(None),
    quarter: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists recorded Challan ITNS 281 payments for the organization.
    """
    query = select(TDSChallan).where(TDSChallan.tenant_id == ctx.tenant.id)
    if fiscal_year:
        query = query.where(TDSChallan.fiscal_year == fiscal_year)
    if quarter:
        query = query.where(TDSChallan.quarter == quarter.upper())

    query = query.order_by(desc(TDSChallan.payment_date))
    res = await db.execute(query)
    challans = res.scalars().all()

    output = []
    for c in challans:
        output.append(TDSChallanResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            fiscal_year=c.fiscal_year,
            quarter=c.quarter,
            section=c.section,
            bsr_code=c.bsr_code,
            challan_serial_no=c.challan_serial_no,
            payment_date=c.payment_date,
            tds_amount=c.tds_amount,
            total_amount=c.total_amount,
            cin=c.cin,
            minor_head=c.minor_head,
            created_at=c.created_at,
            deductions_count=len(c.deductions) if c.deductions else 0
        ))
    return output


@router.get("/summary", response_model=TDSSummaryResponse)
async def get_tds_summary(
    fiscal_year: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves high-level TDS summary radar: Total Deducted, Deposited, Pending, and Next Due Date.
    """
    summary = await TDSService.get_tds_summary(
        db=db,
        tenant_id=ctx.tenant.id,
        fiscal_year=fiscal_year
    )
    return TDSSummaryResponse(**summary)


@router.get("/form26q-export", response_class=PlainTextResponse)
async def export_form26q(
    fiscal_year: str = Query(..., description="e.g. 2026-27"),
    quarter: str = Query(..., description="Q1, Q2, Q3, Q4"),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates official NSDL / Protean e-Gov compliant ASCII text file for quarterly Form 26Q e-TDS return.
    """
    try:
        content = await TDSService.generate_form26q_text_file(
            db=db,
            tenant_id=ctx.tenant.id,
            fiscal_year=fiscal_year,
            quarter=quarter.upper()
        )
        filename = f"FORM26Q_{fiscal_year}_{quarter.upper()}.txt"
        return PlainTextResponse(
            content=content,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

