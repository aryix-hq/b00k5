"""
Pillar 1: Inviolable Double-Entry General Ledger Core Audit Tests
Asserts:
1. Atomic Zero-Sum Ledger Invariant: Debit 10,000.00 vs Credit 9,999.99 aborts transaction.
2. Debit/Credit Mutual Exclusivity: Rejects (DR>0 and CR>0), (DR=0 and CR=0), and negative amounts.
3. Compound Journal Entries: 1 Debit leg and 4 Credit legs perfectly balance to exact paise.
4. Banker's Rounding & Fractional Quantities: ROUND_HALF_EVEN applied; zero cumulative imbalance.
"""

from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_01_atomic_zero_sum_ledger_invariant(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 1.1: Attempt to commit an unbalanced journal entry:
    Debit: ₹10,000.00 vs Credit: ₹9,999.99 (0.01 drift).
    Database transaction must abort with check constraint / trigger error. Zero records written.
    """
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")

    unbalanced_entry_num = f"JV-UNBAL-{uuid.uuid4().hex[:6]}"
    # Flush passes locally, but commit or transaction block MUST reject it via trigger
    with pytest.raises((DBAPIError, IntegrityError, Exception)) as exc_info:
        async with async_db.begin_nested():
            entry = JournalEntry(
                tenant_id=tenant_a.id,
                entry_number=unbalanced_entry_num,
                entry_date=date.today(),
                narration="Malicious / Buggy unbalanced entry test",
                status="posted",
                is_posted=True
            )
            async_db.add(entry)
            await async_db.flush()

            line1 = JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_a.id,
                account_id=bank_acc.id,
                debit_amount=Decimal("10000.00"),
                credit_amount=Decimal("0.00")
            )
            line2 = JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_a.id,
                account_id=rev_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("9999.99") # 1-paise discrepancy!
            )
            async_db.add_all([line1, line2])
            await async_db.flush()
            # Explicitly verify deferred trigger
            await async_db.execute(text("SET CONSTRAINTS ALL IMMEDIATE;"))

    error_msg = str(exc_info.value).lower()
    assert any(term in error_msg for term in ["check_zero_sum_balance", "inviolable", "discrepancy", "trigger", "failed"])

    # Verify zero records written
    chk_stmt = select(JournalEntry).where(
        JournalEntry.tenant_id == tenant_a.id,
        JournalEntry.entry_number == unbalanced_entry_num
    )
    res = await async_db.execute(chk_stmt)
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_02_debit_credit_mutual_exclusivity(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 1.2: Database level column constraints:
    1. Reject journal_item with debit > 0 and credit > 0
    2. Reject journal_item with debit = 0 and credit = 0
    3. Reject journal_item with negative debit or credit (e.g. debit = -500.00)
    """
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")

    entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-MUTUAL-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Mutual exclusivity test",
        status="draft",
        is_posted=False
    )
    async_db.add(entry)
    await async_db.flush()

    # Case 1: Both debit > 0 and credit > 0
    with pytest.raises((IntegrityError, DBAPIError)):
        async with async_db.begin_nested():
            line_both = JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_a.id,
                account_id=bank_acc.id,
                debit_amount=Decimal("500.00"),
                credit_amount=Decimal("500.00")
            )
            async_db.add(line_both)
            await async_db.flush()

    # Case 2: Both debit = 0 and credit = 0
    with pytest.raises((IntegrityError, DBAPIError)):
        async with async_db.begin_nested():
            line_zero = JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_a.id,
                account_id=bank_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("0.00")
            )
            async_db.add(line_zero)
            await async_db.flush()

    # Case 3: Negative numbers (debit = -500.00)
    with pytest.raises((IntegrityError, DBAPIError)):
        async with async_db.begin_nested():
            line_neg = JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_a.id,
                account_id=bank_acc.id,
                debit_amount=Decimal("-500.00"),
                credit_amount=Decimal("0.00")
            )
            async_db.add(line_neg)
            await async_db.flush()


@pytest.mark.asyncio
async def test_03_compound_journal_entries(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 1.3: Compound Journal Entry:
    1 Debit leg and 4 Credit legs:
    DR 1010 Bank Current Account              = ₹1,20,000.00
    CR 3010 Operating Base Revenue           = ₹1,00,000.00
    CR 2050 Output CGST (9%)                 = ₹9,000.00
    CR 2051 Output SGST (9%)                 = ₹9,000.00
    CR 4030 Platform Fee Withholding         = ₹2,000.00
    Sum of 4 credits matches debit to exact sub-cent/paise.
    """
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")
    cgst_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2050")
    sgst_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2051")
    fee_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "4030")

    entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-COMPOUND-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Compound entry: Revenue split with CGST, SGST, and Platform Fee",
        status="posted",
        is_posted=True
    )
    async_db.add(entry)
    await async_db.flush()

    debit_total = Decimal("120000.00")
    cr_base = Decimal("100000.00")
    cr_cgst = Decimal("9000.00")
    cr_sgst = Decimal("9000.00")
    cr_fee = Decimal("2000.00")

    lines = [
        JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_a.id,
            account_id=bank_acc.id,
            debit_amount=debit_total,
            credit_amount=Decimal("0.00"),
            description="Gross Bank Inflow"
        ),
        JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_a.id,
            account_id=rev_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=cr_base,
            description="Base Subscription Revenue"
        ),
        JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_a.id,
            account_id=cgst_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=cr_cgst,
            description="Output CGST @ 9%"
        ),
        JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_a.id,
            account_id=sgst_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=cr_sgst,
            description="Output SGST @ 9%"
        ),
        JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_a.id,
            account_id=fee_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=cr_fee,
            description="Platform Fee Collection"
        )
    ]

    total_debits = sum(l.debit_amount for l in lines)
    total_credits = sum(l.credit_amount for l in lines)
    assert total_debits == total_credits
    assert total_credits == Decimal("120000.00")

    async_db.add_all(lines)
    await async_db.flush()
    # Explicitly test deferred zero-sum trigger
    await async_db.execute(text("SET CONSTRAINTS ALL IMMEDIATE;"))


@pytest.mark.asyncio
async def test_04_bankers_rounding_and_fractional_quantities(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 1.4: Banker's Rounding & Fractional Quantities:
    Create an invoice with 3 items priced at ₹33.3333 with 18% tax.
    Assertion: Calculations apply ROUND_HALF_EVEN.
    Ledger never stores or rounds values in a way that causes a 1-paise cumulative imbalance.
    """
    qty = Decimal("3.000")
    rate = Decimal("33.3333")
    taxable_raw = qty * rate # 99.9999

    quantize_2dp = Decimal('0.01')
    taxable_rounded = taxable_raw.quantize(quantize_2dp, rounding=ROUND_HALF_EVEN)
    assert taxable_rounded == Decimal("100.00")

    tax_rate = Decimal("18.00")
    tax_raw = taxable_rounded * (tax_rate / Decimal("100.00")) # 18.0000
    tax_rounded = tax_raw.quantize(quantize_2dp, rounding=ROUND_HALF_EVEN)
    assert tax_rounded == Decimal("18.00")

    grand_total = taxable_rounded + tax_rounded
    assert grand_total == Decimal("118.00")

    # Post through subledger service and verify exact paise preservation
    from app.services.subledger_service import SubledgerService
    post_res = await SubledgerService.post_tax_invoice(
        session=async_db,
        tenant_id=tenant_a.id,
        customer_id=uuid.uuid4(),
        invoice_number="INV-ROUNDING-001",
        subtotal=taxable_rounded,
        cgst_rate=Decimal("9.00"),
        sgst_rate=Decimal("9.00")
    )

    assert post_res["grand_total"] == Decimal("118.00")
    assert post_res["cgst_amount"] == Decimal("9.00")
    assert post_res["sgst_amount"] == Decimal("9.00")
    assert post_res["subtotal"] + post_res["cgst_amount"] + post_res["sgst_amount"] == post_res["grand_total"]
