"""
Pillar 7: Fixed Assets, Capitalization & Depreciation Engine Audit Tests
Asserts:
1. Asset Capitalization: Base 200,000 + Inst 15,000 + Freight 5,000 = Capitalize 220,000 to Code 1050.
2. Depreciation Run (WDV): DR Depreciation Expense, CR Accumulated Depreciation; NBV verified.
3. Asset Disposal & Gain/Loss: Sale of asset with Cost 100,000, AccDep 60,000 for 48,000 -> Profit 8,000.
"""

from decimal import Decimal
from datetime import date
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.fixed_assets_engine import FixedAssetsEngine
from app.services.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_01_asset_capitalization(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 7.1: Purchase server for ₹200,000 + installation charges ₹15,000 + freight ₹5,000.
    System capitalizes total acquisition cost (₹220,000) to Computer Hardware (Code 1050).
    Freight and installation are NOT expensed to P&L.
    """
    cap_res = await FixedAssetsEngine.capitalize_asset(
        session=async_db,
        tenant_id=tenant_a.id,
        asset_name="Dell PowerEdge R750 Rack Server",
        base_cost=Decimal("200000.00"),
        installation_charges=Decimal("15000.00"),
        freight_charges=Decimal("5000.00"),
        asset_account_code="1050",
        payable_account_code="2040"
    )

    assert cap_res["total_capitalized"] == Decimal("220000.00")
    assert cap_res["base_cost"] == Decimal("200000.00")
    assert cap_res["installation"] == Decimal("15000.00")
    assert cap_res["freight"] == Decimal("5000.00")

    # Check journal lines
    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == cap_res["journal_entry_id"])
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2

    # DR 1050 Fixed Asset (₹220,000)
    assert lines[0].debit_amount == Decimal("220000.00")
    assert lines[0].credit_amount == Decimal("0.00")

    # CR 2040 Trade Payables (₹220,000)
    assert lines[1].debit_amount == Decimal("0.00")
    assert lines[1].credit_amount == Decimal("220000.00")


@pytest.mark.asyncio
async def test_02_depreciation_run_wdv(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 7.2: Written Down Value (WDV) Depreciation Run:
    Gross Cost: ₹2,20,000. Prior Accumulated Depreciation: ₹0.
    Annual WDV Rate: 40% (as per Schedule II for servers/computers).
    Period: 1 month.
    Monthly Depreciation = 220,000 * 0.40 * (1/12) = ₹7,333.33.
    DR 4020 Depreciation Expense          = ₹7,333.33
    CR 1029 Accumulated Depreciation (CA) = ₹7,333.33
    Net Book Value = ₹2,12,666.67.
    """
    dep_res = await FixedAssetsEngine.run_depreciation_wdv(
        session=async_db,
        tenant_id=tenant_a.id,
        asset_name="Dell PowerEdge Server",
        gross_cost=Decimal("220000.00"),
        prior_accumulated_dep=Decimal("0.00"),
        annual_wdv_rate_percent=Decimal("40.00"),
        period_months=1,
        expense_account_code="4020",
        accumulated_dep_code="1029"
    )

    assert dep_res["opening_wdv"] == Decimal("220000.00")
    assert dep_res["depreciation_amount"] == Decimal("7333.33")
    assert dep_res["new_accumulated_depreciation"] == Decimal("7333.33")
    assert dep_res["net_book_value"] == Decimal("212666.67")

    # Verify journal entry lines
    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == dep_res["journal_entry_id"])
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2

    # DR Depreciation Expense
    assert lines[0].debit_amount == Decimal("7333.33")
    # CR Accumulated Depreciation
    assert lines[1].credit_amount == Decimal("7333.33")


@pytest.mark.asyncio
async def test_03_asset_disposal_and_gain_loss(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 7.3: Asset Disposal & Gain/Loss Calculation:
    Cost: ₹100,000, Accumulated Depreciation: ₹60,000 (NBV = ₹40,000).
    Sold for ₹48,000 (Profit on sale = ₹8,000).
    DR 1010 Bank                     = ₹48,000
    DR 1029 Accumulated Depreciation = ₹60,000
    CR 1050 Fixed Asset Cost         = ₹100,000
    CR 3030 Profit on Sale of Asset  = ₹8,000
    Total Debits (₹108,000) == Total Credits (₹108,000).
    """
    disp_res = await FixedAssetsEngine.dispose_fixed_asset(
        session=async_db,
        tenant_id=tenant_a.id,
        asset_name="Development Workstation #04",
        gross_cost=Decimal("100000.00"),
        accumulated_dep=Decimal("60000.00"),
        sale_proceeds=Decimal("48000.00"),
        asset_account_code="1050",
        accumulated_dep_code="1029",
        bank_account_code="1010",
        profit_account_code="3030"
    )

    assert disp_res["net_book_value"] == Decimal("40000.00")
    assert disp_res["gain_or_loss"] == Decimal("8000.00")
    assert disp_res["total_debits"] == Decimal("108000.00")
    assert disp_res["total_credits"] == Decimal("108000.00")

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == disp_res["journal_entry_id"])
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 4

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == Decimal("108000.00")
