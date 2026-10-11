"""
Pillar 5: Advance Payments, Unearned Revenue & Multi-Voucher Allocation Audit Tests
Asserts:
1. Customer Advance (Deferred Revenue): DR Bank, CR Customer Advances (Liability 2040); P&L revenue untouched.
2. Subsequent Invoice Offset: DR Advances 50,000, DR AR 30,000 | CR Revenue 80,000.
3. Cross-Voucher Many-to-Many Matching: Single payment 100,000 allocated across 3 invoices (30k, 45k, 25k).
"""

from decimal import Decimal
from datetime import date
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.subledger_service import SubledgerService
from app.services.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_01_customer_advance_unearned_revenue(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 5.1: Receive ₹50,000 advance before any goods are delivered or invoice generated.
    DR 1010 Bank Current Account                   = ₹50,000.00
    CR 2040 Customer Advances (Current Liability)   = ₹50,000.00
    P&L Revenue is strictly NOT impacted.
    """
    customer_name = "Zenith Labs Corp"
    adv_entry = await SubledgerService.receive_customer_advance(
        session=async_db,
        tenant_id=tenant_a.id,
        customer_name=customer_name,
        amount=Decimal("50000.00")
    )

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == adv_entry.id)
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2

    # DR Bank
    assert lines[0].debit_amount == Decimal("50000.00")
    assert lines[0].credit_amount == Decimal("0.00")

    # CR Customer Advances (Liability)
    assert lines[1].debit_amount == Decimal("0.00")
    assert lines[1].credit_amount == Decimal("50000.00")

    # Verify P&L accounts (Revenue 3010) are unaffected
    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")
    rev_bal_stmt = select(
        func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
    ).where(
        JournalLine.tenant_id == tenant_a.id,
        JournalLine.journal_entry_id == adv_entry.id,
        JournalLine.account_id == rev_acc.id
    )
    rev_bal = (await async_db.execute(rev_bal_stmt)).scalar()
    assert rev_bal == Decimal("0.00")


@pytest.mark.asyncio
async def test_02_subsequent_invoice_offset(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 5.2: Issue invoice for ₹80,000 to the same customer. Allocate ₹50,000 advance.
    DR 2040 Customer Advances (Offset)   = ₹50,000.00
    DR 1020 Accounts Receivable (Net due) = ₹30,000.00
    CR 3010 Operating Revenue            = ₹80,000.00
    Customer advance liability zeroes out; AR reflects net due of ₹30,000.
    """
    inv_num = f"INV-OFFSET-{uuid.uuid4().hex[:6]}"

    offset_entry = await SubledgerService.offset_advance_against_invoice(
        session=async_db,
        tenant_id=tenant_a.id,
        invoice_number=inv_num,
        advance_applied=Decimal("50000.00"),
        net_ar_remaining=Decimal("30000.00"),
        total_revenue_recognized=Decimal("80000.00")
    )

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == offset_entry.id)
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 3

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == Decimal("80000.00")

    # Line 1: DR Customer Advances (50,000)
    assert lines[0].debit_amount == Decimal("50000.00")
    # Line 2: DR AR Net Due (30,000)
    assert lines[1].debit_amount == Decimal("30000.00")
    # Line 3: CR Revenue (80,000)
    assert lines[2].credit_amount == Decimal("80000.00")


@pytest.mark.asyncio
async def test_03_cross_voucher_many_to_many_matching(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 5.3: Cross-Voucher Many-to-Many Matching:
    Single payment of ₹100,000 received covering 3 separate open invoices:
    - Inv 1: ₹30,000.00
    - Inv 2: ₹45,000.00
    - Inv 3: ₹25,000.00
    DR 1010 Bank Current Account = ₹100,000.00
    CR 1020 AR (Inv 1)          = ₹30,000.00
    CR 1020 AR (Inv 2)          = ₹45,000.00
    CR 1020 AR (Inv 3)          = ₹25,000.00
    Payment allocation links exact amounts without orphan residues.
    """
    allocations = [
        {"invoice_number": "INV-2026-001", "allocated_amount": Decimal("30000.00")},
        {"invoice_number": "INV-2026-002", "allocated_amount": Decimal("45000.00")},
        {"invoice_number": "INV-2026-003", "allocated_amount": Decimal("25000.00")}
    ]

    total_payment = Decimal("100000.00")

    match_entry = await SubledgerService.match_many_to_many_payments(
        session=async_db,
        tenant_id=tenant_a.id,
        total_payment=total_payment,
        allocations=allocations
    )

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == match_entry.id)
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 4

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == total_payment

    # Line 0: DR Bank (100,000)
    assert lines[0].debit_amount == Decimal("100000.00")
    # Lines 1-3: Credits matching each invoice exactly
    assert lines[1].credit_amount == Decimal("30000.00")
    assert lines[2].credit_amount == Decimal("45000.00")
    assert lines[3].credit_amount == Decimal("25000.00")
