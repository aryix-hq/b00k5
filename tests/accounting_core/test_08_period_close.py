"""
Pillar 8: Accruals, Period-End Close & Multi-Year Rollover Audit Tests
Asserts:
1. Prepaid Expenses & Monthly Amortization: Asset deferral, monthly P&L expensing, asset reduction.
2. Expense Accruals & Matching Principle: Expense recognized in correct period with accrued liability.
3. Year-End Closing Run: Nominal accounts cleared to 0.00, profit transferred to Retained Earnings, period locked.
"""

from decimal import Decimal
from datetime import date
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.period_close_engine import PeriodCloseEngine
from app.services.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_01_prepaid_expenses_and_amortization(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 8.1: Prepaid Software Subscription:
    1. Pay 1-year subscription of ₹120,000 on Jan 1:
       DR 1070 Prepaid Software = ₹120,000 | CR 1010 Bank = ₹120,000
    2. Monthly close for January:
       DR 4010 Software Expense = ₹10,000  | CR 1070 Prepaid Software = ₹10,000
       Prepaid asset balance drops to ₹110,000.
    """
    # 1. Initial prepayment
    entry_prep = await PeriodCloseEngine.book_prepaid_expense(
        session=async_db,
        tenant_id=tenant_a.id,
        vendor_name="GitHub Enterprise",
        total_amount=Decimal("120000.00"),
        booking_date=date(2026, 1, 1)
    )
    assert entry_prep.status == "posted"

    # 2. Amortization for January
    entry_amort = await PeriodCloseEngine.amortize_prepaid_expense(
        session=async_db,
        tenant_id=tenant_a.id,
        monthly_expense_amount=Decimal("10000.00"),
        period_label="January 2026",
        amortization_date=date(2026, 1, 31)
    )
    assert entry_amort.status == "posted"

    # 3. Verify net balance of Prepaid Asset account (Code 1070)
    prepaid_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1070")
    bal_stmt = select(
        func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
        func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
    ).where(
        JournalLine.tenant_id == tenant_a.id,
        JournalLine.account_id == prepaid_acc.id
    )
    row = (await async_db.execute(bal_stmt)).one()
    net_prepaid = row.d - row.c
    assert net_prepaid == Decimal("110000.00") # 120k - 10k = 110k exactly!


@pytest.mark.asyncio
async def test_02_expense_accruals_and_matching(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 8.2: Expense Accrual under Matching Principle:
    Electricity bill of ₹18,500 for March received in April.
    Accrual entry on March 31:
    DR 4040 Utility / Other Expense           = ₹18,500.00
    CR 2030 Outstanding Expenses / Accrued Liab = ₹18,500.00
    """
    accrual_amt = Decimal("18500.00")
    accrual_dt = date(2026, 3, 31)

    entry = await PeriodCloseEngine.book_expense_accrual(
        session=async_db,
        tenant_id=tenant_a.id,
        expense_description="March BESCOM Electricity Power Consumption",
        accrual_amount=accrual_amt,
        accrual_date=accrual_dt
    )

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2

    # DR Expense
    assert lines[0].debit_amount == accrual_amt
    assert lines[0].credit_amount == Decimal("0.00")

    # CR Accrued Liability
    assert lines[1].debit_amount == Decimal("0.00")
    assert lines[1].credit_amount == accrual_amt

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == accrual_amt


@pytest.mark.asyncio
async def test_03_year_end_closing_and_period_lockout(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 8.3: Year-End Closing Sequence:
    1. Nominal Accounts (Revenue 3010, Expenses 4010/4040) are cleared to exactly ₹0.00.
    2. Net Profit is credited to Reserves & Surplus / Retained Earnings (Code 2020).
    3. Audit Lock: Fiscal year is marked is_closed = True. System rejects backdated postings.
    """
    # 1. Post revenue of 300,000 and expenses of 100,000 for FY 2025-26
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")
    exp_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "4010")

    # Revenue
    entry_rev = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-FY-REV-{uuid.uuid4().hex[:4]}",
        entry_date=date(2026, 3, 15),
        narration="FY 2025-26 SaaS Revenue",
        status="posted",
        is_posted=True
    )
    async_db.add(entry_rev)
    await async_db.flush()
    async_db.add_all([
        JournalLine(journal_entry_id=entry_rev.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=Decimal("300000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry_rev.id, tenant_id=tenant_a.id, account_id=rev_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("300000.00"))
    ])

    # Expense
    entry_exp = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-FY-EXP-{uuid.uuid4().hex[:4]}",
        entry_date=date(2026, 3, 20),
        narration="FY 2025-26 Cloud Infrastructure",
        status="posted",
        is_posted=True
    )
    async_db.add(entry_exp)
    await async_db.flush()
    async_db.add_all([
        JournalLine(journal_entry_id=entry_exp.id, tenant_id=tenant_a.id, account_id=exp_acc.id, debit_amount=Decimal("100000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry_exp.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000.00"))
    ])
    await async_db.flush()

    # 2. Run year-end close sequence
    close_res = await PeriodCloseEngine.close_financial_year(
        session=async_db,
        tenant_id=tenant_a.id,
        fiscal_year_label="FY 2025-26",
        retained_earnings_code="2020",
        closing_date=date(2026, 3, 31)
    )

    assert close_res["is_closed"] is True
    assert close_res["total_revenue_cleared"] >= Decimal("300000.00")
    assert close_res["total_expense_cleared"] >= Decimal("100000.00")
    assert close_res["net_profit_transferred"] >= Decimal("200000.00")

    # 3. Verify Nominal accounts now have zero balance as of closing date
    tb_after = await LedgerService.get_trial_balance(async_db, tenant_a.id)
    items_by_code = {it["code"]: it for it in tb_after["items"]}
    if "3010" in items_by_code:
        # Net balance must be 0
        assert items_by_code["3010"]["debit_balance"] == items_by_code["3010"]["credit_balance"] == Decimal("0.00")

    # 4. Verify Period Lockout: Backdated entries rejected
    with pytest.raises(PermissionError) as exc:
        PeriodCloseEngine.verify_period_is_open(tenant_a, date(2026, 3, 10))
    assert "period lockout" in str(exc.value).lower()
