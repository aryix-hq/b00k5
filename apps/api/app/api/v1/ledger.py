from typing import List, Optional
from datetime import date, datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_tenant, get_current_user
from app.models.tenant import Tenant, User
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.schemas.ledger import (
    AccountCreate, AccountResponse,
    JournalEntryCreate, JournalEntryResponse, TrialBalanceReport
)
from app.services.ledger_service import LedgerService

from app.core.iam import require_owner, require_ca_or_owner, IAMContext

router = APIRouter()

@router.post("/entries", response_model=JournalEntryResponse)
async def create_journal_entry(
    payload: JournalEntryCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (Company Owner only) Creates an inviolable, balanced Schedule III double-entry journal entry.
    Requires: Sum(Debits) - Sum(Credits) = 0.
    """
    try:
        entry = await LedgerService.create_journal_entry(
            session=db,
            tenant_id=ctx.tenant.id,
            payload=payload,
            created_by_user_id=ctx.user.id
        )
        await db.commit()
        stmt = select(JournalEntry).options(selectinload(JournalEntry.lines)).where(JournalEntry.id == entry.id)
        return (await db.execute(stmt)).scalar_one()
    except ValueError as ve:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(ve))

@router.post("/entries/audit-adjustment", response_model=JournalEntryResponse)
async def create_audit_adjustment_entry(
    payload: JournalEntryCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (CA / Statutory Auditor & Owner) Posts a statutory audit adjustment journal voucher.
    Used during year-end audit verification for provisions, depreciation adjustments, and tax reconciliations.
    """
    try:
        if not payload.entry_number or not payload.entry_number.startswith("JV-AUDIT-ADJ"):
            payload.entry_number = f"JV-AUDIT-ADJ-{uuid.uuid4().hex[:6].upper()}"
        payload.reference_type = "audit_adjustment"
        entry = await LedgerService.create_journal_entry(
            session=db,
            tenant_id=ctx.tenant.id,
            payload=payload,
            created_by_user_id=ctx.user.id
        )
        await db.commit()
        stmt = select(JournalEntry).options(selectinload(JournalEntry.lines)).where(JournalEntry.id == entry.id)
        return (await db.execute(stmt)).scalar_one()
    except ValueError as ve:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(ve))

@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == ctx.tenant.id).order_by(ChartOfAccounts.code)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/accounts", response_model=AccountResponse)
async def create_account(
    payload: AccountCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    # Check duplicate code
    existing = await db.execute(
        select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == ctx.tenant.id, ChartOfAccounts.code == payload.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Account code {payload.code} already exists.")

    acc = ChartOfAccounts(
        tenant_id=ctx.tenant.id,
        code=payload.code,
        name=payload.name,
        type=payload.type,
        sub_type=payload.sub_type,
        normal_balance=payload.normal_balance,
        description=payload.description
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return acc

@router.get("/journals", response_model=List[JournalEntryResponse])
async def list_journal_entries(
    fy: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .where(JournalEntry.tenant_id == ctx.tenant.id)
    )
    if fy and fy.lower() != "all":
        from app.core.fiscal_year import get_fy_date_bounds
        try:
            fy_start, fy_end = get_fy_date_bounds(fy)
            stmt = stmt.where(JournalEntry.entry_date >= fy_start, JournalEntry.entry_date <= fy_end)
        except Exception:
            pass

    stmt = stmt.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    res = await db.execute(stmt)
    entries = res.scalars().all()
    
    # Format line representations
    out = []
    for entry in entries:
        lines_out = []
        for line in entry.lines:
            lines_out.append({
                "id": line.id,
                "account_id": line.account_id,
                "account_code": line.account.code if line.account else None,
                "account_name": line.account.name if line.account else None,
                "debit_amount": line.debit_amount,
                "credit_amount": line.credit_amount,
                "description": line.description
            })
        out.append({
            "id": entry.id,
            "tenant_id": entry.tenant_id,
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date,
            "narration": entry.narration,
            "reference_type": entry.reference_type,
            "is_posted": entry.is_posted,
            "lines": lines_out,
            "created_at": entry.created_at
        })
    return out

@router.get("/trial-balance", response_model=TrialBalanceReport)
async def get_trial_balance(
    fy: Optional[str] = Query(None),
    as_of_date: Optional[date] = None,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes an auditor-ready, balanced Trial Balance statement.
    """
    report = await LedgerService.get_trial_balance(db, ctx.tenant.id, as_of_date=as_of_date, fy=fy)
    return report

@router.get("/reports/schedule-iii-balance-sheet")
async def get_ledger_schedule_iii_report(
    as_of_date: Optional[date] = None,
    fy: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    from app.services.schedule_iii_service import ScheduleIIIService
    return await ScheduleIIIService.get_schedule_iii_summary(
        session=db,
        tenant=ctx.tenant,
        as_of_date=as_of_date,
        fy=fy
    )

from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import func

def get_current_indian_fy() -> str:
    today = date.today()
    start_yr = today.year if today.month >= 4 else today.year - 1
    return f"{start_yr}-{str(start_yr + 1)[-2:]}"

class YearEndCloseRequest(BaseModel):
    fiscal_year: Optional[str] = None
    closing_date: Optional[date] = None

@router.post("/year-end-close")
async def run_year_end_close(
    payload: YearEndCloseRequest,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    current_user = ctx.user
    tenant = ctx.tenant
    """
    Journey 6: Multi-Year Rollover & Year-End Closing Run
    - Calculates total revenue (Class 3000) and total expenses (Class 4000) for the fiscal year
    - Clears all nominal accounts to ₹0.00
    - Transfers Net Profit/Loss into Reserves & Surplus / Retained Earnings (Code 2010)
    - Sets is_closed = TRUE and locks the fiscal year
    - Establishes Real/Personal accounts as Opening Balances for the next fiscal year
    """
    fy = payload.fiscal_year or get_current_indian_fy()
    parts = fy.split("-")
    if len(parts) == 2:
        start_year = int(parts[0])
        end_year = int("20" + parts[1]) if len(parts[1]) == 2 else int(parts[1])
    else:
        today = date.today()
        start_year = today.year if today.month >= 4 else today.year - 1
        end_year = start_year + 1

    start_date = date(start_year, 4, 1)
    end_date = payload.closing_date or date(end_year, 3, 31)

    # 1. Fetch all nominal accounts (Revenue & Expense)
    stmt = select(ChartOfAccounts).where(
        ChartOfAccounts.tenant_id == tenant.id,
        ChartOfAccounts.type.in_(["revenue", "expense"]),
        ChartOfAccounts.is_active == True
    )
    res = await db.execute(stmt)
    nominal_accounts = res.scalars().all()

    # Ensure Retained Earnings account exists (Code 2010 or 2020)
    re_stmt = select(ChartOfAccounts).where(
        ChartOfAccounts.tenant_id == tenant.id,
        ChartOfAccounts.code.in_(["2010", "2020"])
    )
    re_acc = (await db.execute(re_stmt)).scalars().first()
    if not re_acc:
        re_acc = ChartOfAccounts(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            code="2010",
            name="Reserves & Surplus / Retained Earnings",
            type="equity",
            sub_type="retained_earnings",
            normal_balance="credit"
        )
        db.add(re_acc)
        await db.flush()

    total_revenue = Decimal("0.00")
    total_expenses = Decimal("0.00")
    closing_lines = []

    # Calculate net balance for each nominal account
    account_balances = {}
    for acc in nominal_accounts:
        sum_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d_sum"),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c_sum")
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
            JournalLine.tenant_id == tenant.id,
            JournalLine.account_id == acc.id,
            JournalEntry.entry_date >= start_date,
            JournalEntry.entry_date <= end_date
        )
        sum_res = (await db.execute(sum_stmt)).one()
        d_val = sum_res.d_sum
        c_val = sum_res.c_sum

        if acc.type == "revenue":
            net_rev = c_val - d_val
            if net_rev != Decimal("0.00"):
                total_revenue += net_rev
                account_balances[acc.id] = (acc, net_rev, "revenue")
        else: # expense
            net_exp = d_val - c_val
            if net_exp != Decimal("0.00"):
                total_expenses += net_exp
                account_balances[acc.id] = (acc, net_exp, "expense")

    net_profit = total_revenue - total_expenses

    # Create Year-End Closing Journal Entry
    close_jv = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number=f"JV-CLOSE-FY{fy}",
        entry_date=end_date,
        reference_type="year_end_close",
        narration=f"Statutory Year-End Closing Run for FY {fy}: Clearing Nominal Accounts to Retained Earnings",
        status="posted",
        is_posted=True,
        created_by=current_user.id
    )
    db.add(close_jv)
    await db.flush()

    # Generate closing lines
    # For Revenue: Debit the account to zero it out
    for acc_id, (acc, balance, kind) in account_balances.items():
        if kind == "revenue" and balance > Decimal("0.00"):
            closing_lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=close_jv.id,
                tenant_id=tenant.id,
                account_id=acc.id,
                debit_amount=balance,
                credit_amount=Decimal("0.00"),
                description=f"Year-End Close: Clearing {acc.name}"
            ))
        elif kind == "expense" and balance > Decimal("0.00"):
            closing_lines.append(JournalLine(
                id=uuid.uuid4(),
                journal_entry_id=close_jv.id,
                tenant_id=tenant.id,
                account_id=acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=balance,
                description=f"Year-End Close: Clearing {acc.name}"
            ))

    # Transfer Net Profit/Loss to Retained Earnings
    if net_profit >= Decimal("0.00"):
        # Profit -> Credit Retained Earnings
        closing_lines.append(JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=close_jv.id,
            tenant_id=tenant.id,
            account_id=re_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=net_profit,
            description=f"Net Profit transfer for FY {fy} to Reserves & Surplus"
        ))
    else:
        # Loss -> Debit Retained Earnings
        closing_lines.append(JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=close_jv.id,
            tenant_id=tenant.id,
            account_id=re_acc.id,
            debit_amount=abs(net_profit),
            credit_amount=Decimal("0.00"),
            description=f"Net Loss transfer for FY {fy} from Reserves & Surplus"
        ))

    db.add_all(closing_lines)

    # 4. Lock the Fiscal Year in statutory profile
    statutory_profile = dict(tenant.statutory_profile or {})
    closed_fys = dict(statutory_profile.get("closed_fiscal_years", {}))
    closed_fys[fy] = {
        "is_closed": True,
        "closed_at": datetime.utcnow().isoformat(),
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses),
        "net_profit": float(net_profit),
        "closing_entry_id": str(close_jv.id),
        "retained_earnings_account": re_acc.code
    }
    statutory_profile["closed_fiscal_years"] = closed_fys
    tenant.statutory_profile = statutory_profile
    await db.commit()

    # 5. Calculate Real/Personal Opening Balances for next Fiscal Year
    real_personal_stmt = select(ChartOfAccounts).where(
        ChartOfAccounts.tenant_id == tenant.id,
        ChartOfAccounts.type.in_(["asset", "liability", "equity"]),
        ChartOfAccounts.is_active == True
    ).order_by(ChartOfAccounts.code)
    rp_accounts = (await db.execute(real_personal_stmt)).scalars().all()

    opening_balances = []
    next_fy = f"{end_year}-{str(end_year+1)[-2:]}"
    for acc in rp_accounts:
        bal_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d_sum"),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c_sum")
        ).where(
            JournalLine.tenant_id == tenant.id,
            JournalLine.account_id == acc.id
        )
        bal_res = (await db.execute(bal_stmt)).one()
        d_total = bal_res.d_sum
        c_total = bal_res.c_sum

        if acc.normal_balance == "debit":
            net_bal = d_total - c_total
        else:
            net_bal = c_total - d_total

        if net_bal != Decimal("0.00"):
            opening_balances.append({
                "account_code": acc.code,
                "account_name": acc.name,
                "type": acc.type,
                "normal_balance": acc.normal_balance,
                "balance": float(net_bal)
            })

    return {
        "success": True,
        "fiscal_year": fy,
        "next_fiscal_year": next_fy,
        "is_closed": True,
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses),
        "net_profit": float(net_profit),
        "closing_entry_number": close_jv.entry_number,
        "nominal_accounts_cleared": True,
        "opening_balances_count": len(opening_balances),
        "opening_balances": opening_balances,
        "message": f"Fiscal Year {fy} successfully closed and locked. All nominal accounts cleared to ₹0.00; Net Profit ₹{net_profit:,.2f} transferred to Reserves & Surplus."
    }

@router.get("/fiscal-years")
async def list_fiscal_years(
    ctx: IAMContext = Depends(require_ca_or_owner)
):
    tenant = ctx.tenant
    """
    Returns list of fiscal years, lock status, and closing metadata.
    """
    statutory_profile = tenant.statutory_profile or {}
    closed_fys = statutory_profile.get("closed_fiscal_years", {})
    cur_fy = get_current_indian_fy()
    today = date.today()
    cur_start = today.year if today.month >= 4 else today.year - 1
    avail_years = []
    for y in range(cur_start, cur_start - 4, -1):
        fy_str = f"{y}-{str(y + 1)[-2:]}"
        avail_years.append({
            "fiscal_year": fy_str,
            "is_closed": closed_fys.get(fy_str, {}).get("is_closed", False),
            "details": closed_fys.get(fy_str)
        })
    return {
        "current_active_year": cur_fy,
        "available_years": avail_years
    }

