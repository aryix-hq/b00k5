"""
Pillar 9: Multi-Currency & Realized/Unrealized FX Gain/Loss Audit Tests
Asserts (IAS 21 / Ind AS 21 / AS 11):
1. Realized FX Gain on Settlement: $1,000 USD booked @ 83.00, settled @ 84.50.
   DR Bank 84,500 | CR AR 83,000 | CR Realized FX Gain 1,500. Zero AR residue.
2. Realized FX Loss on Settlement: $2,000 USD booked @ 84.00, settled @ 82.50.
   DR Bank 165,000 | DR Realized FX Loss 3,000 | CR AR 168,000.
3. Period-End Unrealized Mark-to-Market Revaluation:
   $5,000 USD book value ₹4,15,000 revalued at spot 82.00 (-₹5,000 loss) and 86.00 (+₹20,000 gain).
"""

from decimal import Decimal
from datetime import date, timedelta
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService
from app.services.multi_currency_engine import MultiCurrencyEngine


@pytest.mark.asyncio
async def test_01_realized_fx_gain_on_settlement(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 9.1: Realized Foreign Exchange Gain on Settlement:
    - Issue export invoice for $1,000 USD @ 83.00 = Booked AR: ₹83,000.
    - Receive wire payment 30 days later @ 84.50 = Received: ₹84,500.
    - Assertion:
      DR 1010 Bank (INR): ₹84,500
      CR 1020 Accounts Receivable: ₹83,000
      CR 3030 Realized FX Gain (P&L): ₹1,500
      AR balance is cleared to ₹0.00.
    """
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    ar_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1020")
    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")
    fx_gain_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3030")

    inv_num = f"EXP-INV-{uuid.uuid4().hex[:6]}"
    booking_rate = Decimal("83.00")
    usd_amount = Decimal("1000.00")
    booked_inr = usd_amount * booking_rate # 83,000.00

    # 1. Book export invoice in General Ledger
    inv_entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-INV-{inv_num}",
        entry_date=date.today() - timedelta(days=30),
        reference_type="export_invoice",
        narration=f"Export SaaS billing: {usd_amount} USD @ {booking_rate} INR/USD",
        status="posted",
        is_posted=True
    )
    async_db.add(inv_entry)
    await async_db.flush()

    async_db.add_all([
        JournalLine(
            journal_entry_id=inv_entry.id,
            tenant_id=tenant_a.id,
            account_id=ar_acc.id,
            debit_amount=booked_inr,
            credit_amount=Decimal("0.00"),
            description=f"Export AR booked: {inv_num}"
        ),
        JournalLine(
            journal_entry_id=inv_entry.id,
            tenant_id=tenant_a.id,
            account_id=rev_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=booked_inr,
            description=f"Export SaaS Revenue: {inv_num}"
        )
    ])
    await async_db.flush()

    # 2. Settle payment when exchange rate has strengthened to 84.50
    settlement_rate = Decimal("84.50")
    settle_res = await MultiCurrencyEngine.settle_foreign_invoice(
        session=async_db,
        tenant_id=tenant_a.id,
        invoice_number=inv_num,
        foreign_amount=usd_amount,
        booking_exchange_rate=booking_rate,
        settlement_exchange_rate=settlement_rate,
        bank_account_code="1010",
        ar_account_code="1020",
        fx_gain_account_code="3030",
        fx_loss_account_code="4040",
        settlement_date=date.today()
    )

    assert settle_res["is_gain"] is True
    assert settle_res["booked_inr"] == Decimal("83000.00")
    assert settle_res["settled_inr"] == Decimal("84500.00")
    assert settle_res["fx_difference"] == Decimal("1500.00")
    assert settle_res["total_debits"] == Decimal("84500.00")
    assert settle_res["total_credits"] == Decimal("84500.00")

    # 3. Assert Sub-ledger & GL balances: AR balance MUST be exactly ₹0.00
    sum_ar = select(
        func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
        func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
    ).where(
        JournalLine.tenant_id == tenant_a.id,
        JournalLine.account_id == ar_acc.id
    )
    ar_row = (await async_db.execute(sum_ar)).one()
    assert ar_row.d == Decimal("83000.00")
    assert ar_row.c == Decimal("83000.00")
    assert (ar_row.d - ar_row.c) == Decimal("0.00")

    # Realized FX Gain has credit balance of ₹1,500.00
    sum_gain = select(
        func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
    ).where(
        JournalLine.tenant_id == tenant_a.id,
        JournalLine.account_id == fx_gain_acc.id
    )
    total_gain = (await async_db.execute(sum_gain)).scalar_one()
    assert total_gain == Decimal("1500.00")


@pytest.mark.asyncio
async def test_02_realized_fx_loss_on_settlement(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 9.1 (Loss scenario):
    - Export invoice $2,000 USD booked @ 84.00 = Booked AR: ₹168,000.
    - Wire payment received @ 82.50 = Received: ₹165,000.
    - Realized FX Loss = ₹3,000.
    - Assertion:
      DR 1010 Bank: ₹165,000
      DR 4040 Realized FX Loss: ₹3,000
      CR 1020 AR: ₹168,000
      AR balance is cleared to ₹0.00.
    """
    ar_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1020")
    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")
    fx_loss_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "4040")

    inv_num = f"EXP-LOSS-{uuid.uuid4().hex[:6]}"
    booking_rate = Decimal("84.00")
    usd_amount = Decimal("2000.00")
    booked_inr = usd_amount * booking_rate # 168,000.00

    # Book invoice
    inv_entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-INV-{inv_num}",
        entry_date=date.today() - timedelta(days=20),
        reference_type="export_invoice",
        narration=f"Export consulting: {usd_amount} USD @ {booking_rate}",
        status="posted",
        is_posted=True
    )
    async_db.add(inv_entry)
    await async_db.flush()

    async_db.add_all([
        JournalLine(journal_entry_id=inv_entry.id, tenant_id=tenant_a.id, account_id=ar_acc.id, debit_amount=booked_inr, credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=inv_entry.id, tenant_id=tenant_a.id, account_id=rev_acc.id, debit_amount=Decimal("0.00"), credit_amount=booked_inr)
    ])
    await async_db.flush()

    # Settle at 82.50
    settle_res = await MultiCurrencyEngine.settle_foreign_invoice(
        session=async_db,
        tenant_id=tenant_a.id,
        invoice_number=inv_num,
        foreign_amount=usd_amount,
        booking_exchange_rate=booking_rate,
        settlement_exchange_rate=Decimal("82.50"),
        bank_account_code="1010",
        ar_account_code="1020",
        fx_gain_account_code="3030",
        fx_loss_account_code="4040",
        settlement_date=date.today()
    )

    assert settle_res["is_gain"] is False
    assert settle_res["booked_inr"] == Decimal("168000.00")
    assert settle_res["settled_inr"] == Decimal("165000.00")
    assert settle_res["fx_difference"] == Decimal("-3000.00")
    assert settle_res["total_debits"] == Decimal("168000.00")
    assert settle_res["total_credits"] == Decimal("168000.00")

    # Assert FX Loss account debited by ₹3,000.00
    sum_loss = select(
        func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00"))
    ).where(
        JournalLine.tenant_id == tenant_a.id,
        JournalLine.account_id == fx_loss_acc.id
    )
    total_loss = (await async_db.execute(sum_loss)).scalar_one()
    assert total_loss == Decimal("3000.00")


@pytest.mark.asyncio
async def test_03_period_end_unrealized_fx_revaluation(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 9.2: Period-End Unrealized Balance Sheet Mark-to-Market Revaluation:
    - Hold $5,000 USD in foreign currency account. Book value: ₹4,15,000 ($1 = ₹83.00).
    - Year-end closing spot rate is $1 = ₹82.00 (Fair Value: ₹4,10,000).
    - Assertion: System generates unrealized revaluation entry:
      DR 4040 Unrealized FX Loss: ₹5,000
      CR 1010 Bank Account (Foreign Currency): ₹5,000
    - Next period spot rate rises to $1 = ₹86.00 (Fair Value: ₹4,30,000):
      DR 1010 Bank Account: ₹20,000
      CR 3030 Unrealized FX Gain: ₹20,000
    """
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")

    # 1. Initial booking of $5,000 USD @ 83.00 = ₹4,15,000
    init_entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-USD-DEPOSIT-{uuid.uuid4().hex[:6]}",
        entry_date=date(2026, 3, 1),
        narration="Foreign currency escrow deposit: 5,000 USD @ 83.00",
        status="posted",
        is_posted=True
    )
    async_db.add(init_entry)
    await async_db.flush()

    equity_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2010")
    async_db.add_all([
        JournalLine(journal_entry_id=init_entry.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=Decimal("415000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=init_entry.id, tenant_id=tenant_a.id, account_id=equity_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("415000.00"))
    ])
    await async_db.flush()

    # 2. Year-End Revaluation at Spot 82.00 (Loss of ₹5,000)
    reval_loss = await MultiCurrencyEngine.revalue_foreign_monetary_asset(
        session=async_db,
        tenant_id=tenant_a.id,
        account_name="USD Escrow Bank Account",
        foreign_currency_units=Decimal("5000.00"),
        current_book_value_inr=Decimal("415000.00"),
        closing_spot_exchange_rate=Decimal("82.00"),
        monetary_account_code="1010",
        unrealized_gain_account_code="3030",
        unrealized_loss_account_code="4040",
        revaluation_date=date(2026, 3, 31)
    )

    assert reval_loss["is_gain"] is False
    assert reval_loss["fair_value"] == Decimal("410000.00")
    assert reval_loss["unrealized_difference"] == Decimal("-5000.00")

    # Verify Bank net debit balance is now exactly ₹410,000.00
    sum_bank1 = select(
        func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
    ).where(
        JournalLine.tenant_id == tenant_a.id,
        JournalLine.account_id == bank_acc.id
    )
    bank_bal1 = (await async_db.execute(sum_bank1)).scalar_one()
    assert bank_bal1 == Decimal("410000.00")

    # 3. Next Period Revaluation at Spot 86.00 (Gain of ₹20,000 from current 410,000 to 430,000)
    reval_gain = await MultiCurrencyEngine.revalue_foreign_monetary_asset(
        session=async_db,
        tenant_id=tenant_a.id,
        account_name="USD Escrow Bank Account",
        foreign_currency_units=Decimal("5000.00"),
        current_book_value_inr=Decimal("410000.00"),
        closing_spot_exchange_rate=Decimal("86.00"),
        monetary_account_code="1010",
        unrealized_gain_account_code="3030",
        unrealized_loss_account_code="4040",
        revaluation_date=date(2026, 6, 30)
    )

    assert reval_gain["is_gain"] is True
    assert reval_gain["fair_value"] == Decimal("430000.00")
    assert reval_gain["unrealized_difference"] == Decimal("20000.00")

    # Verify Bank net debit balance is now exactly ₹430,000.00
    bank_bal2 = (await async_db.execute(sum_bank1)).scalar_one()
    assert bank_bal2 == Decimal("430000.00")
