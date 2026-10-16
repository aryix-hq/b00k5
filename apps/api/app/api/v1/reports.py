from typing import Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.iam import require_ca_or_owner, IAMContext
from app.services.schedule_iii_service import ScheduleIIIService
from app.services.financial_reporting_service import FinancialReportingService
from app.services.ledger_service import LedgerService

router = APIRouter()

@router.get("/schedule-iii-balance-sheet")
async def get_schedule_iii_report(
    as_of_date: Optional[date] = None,
    fy: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    (CA / Auditor & Company Owner only)
    Fetches the statutory Schedule III Division I Balance Sheet, Profit & Loss statement,
    Notes 1-19, and Mandatory Accounting Ratios computed 100% from live General Ledger entries.
    """
    summary = await ScheduleIIIService.get_schedule_iii_summary(
        session=db,
        tenant=ctx.tenant,
        as_of_date=as_of_date,
        fy=fy
    )
    return summary

@router.get("/trial-balance")
async def get_trial_balance_report(
    as_of_date: Optional[date] = None,
    fy: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (CA / Auditor & Company Owner only)
    Computes an auditor-verified Trial Balance ensuring Sum(Debits) - Sum(Credits) == 0.00.
    """
    report = await LedgerService.get_trial_balance(db, ctx.tenant.id, as_of_date=as_of_date, fy=fy)
    return report

@router.get("/balance-sheet")
async def get_balance_sheet_report(
    as_of_date: Optional[date] = None,
    fy: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (CA / Auditor & Company Owner only)
    Standard Balance Sheet report (Assets, Liabilities, Equity).
    """
    return await FinancialReportingService.generate_balance_sheet(
        session=db,
        tenant_id=ctx.tenant.id,
        as_of_date=as_of_date,
        fy=fy
    )

@router.get("/profit-and-loss")
async def get_profit_and_loss_report(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    fy: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (CA / Auditor & Company Owner only)
    Standard Profit & Loss report (Operating Revenue, Cost of Goods, Operating Expenses, Net Profit).
    """
    if fy and fy.lower() != "all":
        from app.core.fiscal_year import get_fy_date_bounds
        try:
            fy_start, fy_end = get_fy_date_bounds(fy)
            from_date = from_date or fy_start
            to_date = to_date or fy_end
        except Exception:
            pass

    return await FinancialReportingService.generate_profit_and_loss(
        session=db,
        tenant_id=ctx.tenant.id,
        from_date=from_date,
        to_date=to_date
    )

@router.get("/cash-flow")
async def get_cash_flow_report(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    fy: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (CA / Auditor & Company Owner only)
    Standard Cash Flow statement.
    """
    if fy and fy.lower() != "all":
        from app.core.fiscal_year import get_fy_date_bounds
        try:
            fy_start, fy_end = get_fy_date_bounds(fy)
            from_date = from_date or fy_start
            to_date = to_date or fy_end
        except Exception:
            pass

    return await FinancialReportingService.generate_cash_flow(
        session=db,
        tenant_id=ctx.tenant.id,
        from_date=from_date,
        to_date=to_date
    )

