import uuid
from typing import Optional, List, Any, Dict
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.api.deps import get_db
from app.core.iam import require_any_employee, require_ca_or_owner, IAMContext
from app.schemas.asset import (
    FixedAssetCreate,
    FixedAssetResponse,
    DepreciationRunCreate,
    DepreciationRunResponse,
    ScheduleIISummaryResponse,
    SCHEDULE_II_CATEGORY_NAMES
)
from app.services.fixed_assets_engine import FixedAssetsEngine
from app.models.asset import FixedAsset, FixedAssetDepreciationRun


router = APIRouter()


@router.post("/register", response_model=FixedAssetResponse)
async def register_fixed_asset(
    payload: FixedAssetCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a capital asset in the Schedule II Fixed Asset Registry.
    Computes 5% statutory salvage value and useful life per Companies Act 2013 if omitted.
    Optionally posts the initial purchase journal entry to the General Ledger.
    """
    try:
        asset = await FixedAssetsEngine.register_asset(
            session=db,
            tenant_id=ctx.tenant.id,
            asset_name=payload.asset_name,
            category=payload.category,
            purchase_date=payload.purchase_date,
            capitalization_date=payload.capitalization_date,
            gross_block=payload.gross_block,
            salvage_value=payload.salvage_value,
            useful_life_years=payload.useful_life_years,
            depreciation_method=payload.depreciation_method,
            location=payload.location,
            serial_number=payload.serial_number,
            auto_post_purchase_jv=payload.auto_post_purchase_jv,
            payment_account_code=payload.payment_account_code,
            created_by=ctx.user.id
        )
        await db.commit()
        await db.refresh(asset)

        return FixedAssetResponse(
            id=asset.id,
            tenant_id=asset.tenant_id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            category=asset.category,
            category_display=SCHEDULE_II_CATEGORY_NAMES.get(asset.category, asset.category),
            purchase_date=asset.purchase_date,
            capitalization_date=asset.capitalization_date,
            gross_block=asset.gross_block,
            salvage_value=asset.salvage_value,
            useful_life_years=asset.useful_life_years,
            depreciation_method=asset.depreciation_method,
            accumulated_depreciation=asset.accumulated_depreciation,
            net_block=asset.net_block,
            location=asset.location,
            serial_number=asset.serial_number,
            status=asset.status,
            purchase_journal_id=asset.purchase_journal_id,
            created_at=asset.created_at
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/registry", response_model=List[FixedAssetResponse])
async def list_fixed_assets(
    status: Optional[str] = Query("ACTIVE", description="ACTIVE, DISPOSED, or leave blank for ALL"),
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the asset registry for the organization.
    """
    assets = await FixedAssetsEngine.list_assets(
        session=db,
        tenant_id=ctx.tenant.id,
        status=status if status and status.upper() != "ALL" else None
    )

    return [
        FixedAssetResponse(
            id=a.id,
            tenant_id=a.tenant_id,
            asset_code=a.asset_code,
            asset_name=a.asset_name,
            category=a.category,
            category_display=SCHEDULE_II_CATEGORY_NAMES.get(a.category, a.category),
            purchase_date=a.purchase_date,
            capitalization_date=a.capitalization_date,
            gross_block=a.gross_block,
            salvage_value=a.salvage_value,
            useful_life_years=a.useful_life_years,
            depreciation_method=a.depreciation_method,
            accumulated_depreciation=a.accumulated_depreciation,
            net_block=a.net_block,
            location=a.location,
            serial_number=a.serial_number,
            status=a.status,
            purchase_journal_id=a.purchase_journal_id,
            created_at=a.created_at
        )
        for a in assets
    ]


@router.get("/schedule-ii-summary", response_model=ScheduleIISummaryResponse)
async def get_schedule_ii_summary(
    fiscal_year: Optional[str] = Query(None, description="e.g. 2026-27"),
    as_of_date: Optional[date] = Query(None),
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates Schedule II Part C category-wise PPE disclosure summary for financial statements.
    """
    summary = await FixedAssetsEngine.get_schedule_ii_summary(
        session=db,
        tenant_id=ctx.tenant.id,
        fiscal_year=fiscal_year,
        as_of_date=as_of_date
    )
    return ScheduleIISummaryResponse(**summary)


@router.post("/run-depreciation", response_model=DepreciationRunResponse)
async def execute_depreciation_run(
    payload: DepreciationRunCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes period-end depreciation run across all active fixed assets according to Companies Act Schedule II.
    Computes exact pro-rata daily depreciation and auto-posts balanced Journal Entry:
    DR 4070 Depreciation & Amortization Expense
    CR 1059 Accumulated Depreciation - Fixed Assets
    """
    try:
        res = await FixedAssetsEngine.execute_period_depreciation_run(
            session=db,
            tenant_id=ctx.tenant.id,
            fiscal_year=payload.fiscal_year,
            period_start=payload.period_start,
            period_end=payload.period_end,
            run_date=payload.run_date,
            auto_post_jv=payload.auto_post_jv,
            created_by=ctx.user.id
        )
        await db.commit()

        return DepreciationRunResponse(
            id=res["depreciation_run_id"],
            tenant_id=ctx.tenant.id,
            fiscal_year=res["fiscal_year"],
            period_start=res["period_start"],
            period_end=res["period_end"],
            run_date=res["run_date"],
            total_depreciation_amount=res["total_depreciation_amount"],
            journal_entry_id=res["journal_entry_id"],
            journal_entry_number=res["journal_entry_number"],
            status=res["status"],
            asset_count=res["asset_count"],
            details=res["details"],
            created_at=datetime.utcnow()
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/depreciation-runs", response_model=List[DepreciationRunResponse])
async def list_depreciation_runs(
    fiscal_year: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists past period-end depreciation runs and linked journal entries.
    """
    query = select(FixedAssetDepreciationRun).where(FixedAssetDepreciationRun.tenant_id == ctx.tenant.id)
    if fiscal_year:
        query = query.where(FixedAssetDepreciationRun.fiscal_year == fiscal_year)
    query = query.order_by(desc(FixedAssetDepreciationRun.run_date), desc(FixedAssetDepreciationRun.created_at))

    res = await db.execute(query)
    runs = res.scalars().all()

    output = []
    for r in runs:
        output.append(DepreciationRunResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            fiscal_year=r.fiscal_year,
            period_start=r.period_start,
            period_end=r.period_end,
            run_date=r.run_date,
            total_depreciation_amount=r.total_depreciation_amount,
            journal_entry_id=r.journal_entry_id,
            journal_entry_number=r.journal_entry.entry_number if r.journal_entry else None,
            status=r.status,
            asset_count=len(r.details) if r.details else 0,
            details=r.details or [],
            created_at=r.created_at
        ))
    return output
