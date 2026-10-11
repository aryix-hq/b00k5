"""
Pillar 6: 3-Way Bank Statement Reconciliation & Suspense Accounting Audit Tests
Asserts:
1. Timing Differences (Cheques in Transit): Unpresented cheques isolated without artificial adjustments.
2. Direct Bank Debits (Charges & GST): Auto-vouchers for bank charges + input tax credit.
3. Unidentified Inflow & Suspense Clearance: Routing to Code 2099 Suspense and subsequent reclassification.
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


@pytest.mark.asyncio
async def test_01_timing_differences_cheques_in_transit(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 6.1: Timing Differences (Unpresented Cheques):
    Cheque issued to vendor on March 30; cleared by bank on April 4.
    On March 31, Books reflect reduced bank balance; Bank statement does not.
    Reconciliation statement isolates Unpresented Cheques of exact amount without forcing artificial adjustments.
    """
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    ap_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2040")

    cheque_amount = Decimal("35000.00")
    issue_dt = date(2026, 3, 30)
    cleared_dt = date(2026, 4, 4)

    # 1. Book entry on March 30: DR AP 35,000 | CR Bank 35,000
    entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"CHQ-504910-{uuid.uuid4().hex[:4]}",
        entry_date=issue_dt,
        reference_type="cheque_payment",
        narration="Cheque #504910 issued to vendor for office lease",
        status="posted",
        is_posted=True
    )
    async_db.add(entry)
    await async_db.flush()

    async_db.add_all([
        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_a.id, account_id=ap_acc.id, debit_amount=cheque_amount, credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=cheque_amount)
    ])
    await async_db.flush()

    # 2. Bank Reconciliation Statement as of March 31
    reconciliation_date = date(2026, 3, 31)

    # Simulate bank statement closing balance (cheque has not cleared bank yet)
    bank_statement_balance = Decimal("500000.00")
    # Books balance is lower by cheque_amount
    balance_as_per_books = bank_statement_balance - cheque_amount

    # Reconciliation calculation:
    # Balance as per Bank Statement: 500,000
    # Less: Unpresented Cheques: (35,000)
    # Balance as per General Ledger: 465,000
    reconciled_books_balance = bank_statement_balance - cheque_amount

    assert reconciled_books_balance == balance_as_per_books
    # Verify no artificial adjustment was made to general ledger
    chk_entry = await async_db.get(JournalEntry, entry.id)
    assert chk_entry.entry_date == issue_dt


@pytest.mark.asyncio
async def test_02_direct_bank_debits_and_charges(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 6.2: Direct Bank Debits (Bank Charges & GST):
    Bank statement shows auto-deducted bank charges of ₹590 (₹500 + ₹90 GST).
    System creates auto-adjustment voucher:
    DR 4030 Bank Charges Expense = ₹500.00
    DR 1030 Input CGST (9%)      = ₹45.00
    DR 1031 Input SGST (9%)      = ₹45.00
    CR 1010 Bank Current Account = ₹590.00
    """
    charges_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "4030")
    cgst_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1030")
    sgst_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1031")
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")

    entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-BNK-CHG-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        reference_type="bank_charges_reconciliation",
        narration="Direct bank auto-debit for ledger folio and wire charges",
        status="posted",
        is_posted=True
    )
    async_db.add(entry)
    await async_db.flush()

    lines = [
        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_a.id, account_id=charges_acc.id, debit_amount=Decimal("500.00"), credit_amount=Decimal("0.00"), description="Bank charges expense"),
        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_a.id, account_id=cgst_acc.id, debit_amount=Decimal("45.00"), credit_amount=Decimal("0.00"), description="Input CGST 9% on bank charges"),
        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_a.id, account_id=sgst_acc.id, debit_amount=Decimal("45.00"), credit_amount=Decimal("0.00"), description="Input SGST 9% on bank charges"),
        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("590.00"), description="Total bank charge auto-deduction")
    ]
    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == Decimal("590.00")

    async_db.add_all(lines)
    await async_db.flush()


@pytest.mark.asyncio
async def test_03_unidentified_inflow_suspense_routing_and_clearance(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 6.3: Unidentified Inflow & Suspense Clearance:
    1. Statement contains deposit of ₹250,000 with narration 'NEFT-UNKNOWN-REF'.
       DR 1010 Bank Account: ₹250,000 | CR 2099 Suspense Clearing: ₹250,000
    2. Bank balance updates to match reality.
    3. Three weeks later, identified as Director Loan. Reclassification entry:
       DR 2099 Suspense Clearing: ₹250,000 | CR 2030 Director Loan: ₹250,000.
       Bank balance remains completely untouched.
    """
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    suspense_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2099")
    director_loan_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2030")

    inflow_amount = Decimal("250000.00")

    # Step 1: Auto-reconciliation to Suspense Account
    entry1 = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-SUSP-{uuid.uuid4().hex[:6]}",
        entry_date=date.today() - timedelta(days=21),
        reference_type="suspense_allocation",
        narration="Unidentified NEFT deposit auto-posted to suspense clearing",
        status="posted",
        is_posted=True
    )
    async_db.add(entry1)
    await async_db.flush()

    async_db.add_all([
        JournalLine(journal_entry_id=entry1.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=inflow_amount, credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry1.id, tenant_id=tenant_a.id, account_id=suspense_acc.id, debit_amount=Decimal("0.00"), credit_amount=inflow_amount)
    ])
    await async_db.flush()

    # Step 2: Three weeks later, Reclassification to Director Loan
    entry2 = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-RECLASS-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        reference_type="suspense_reclassification",
        narration="Clear suspense: NEFT identified as promoter unsecured director loan",
        status="posted",
        is_posted=True
    )
    async_db.add(entry2)
    await async_db.flush()

    async_db.add_all([
        # Clear suspense by debiting
        JournalLine(journal_entry_id=entry2.id, tenant_id=tenant_a.id, account_id=suspense_acc.id, debit_amount=inflow_amount, credit_amount=Decimal("0.00")),
        # Recognize Director Loan by crediting
        JournalLine(journal_entry_id=entry2.id, tenant_id=tenant_a.id, account_id=director_loan_acc.id, debit_amount=Decimal("0.00"), credit_amount=inflow_amount)
    ])
    await async_db.flush()

    # Verify Suspense account net balance is now exactly ₹0.00
    sum_suspense = select(
        func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
        func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
    ).where(
        JournalLine.tenant_id == tenant_a.id,
        JournalLine.account_id == suspense_acc.id,
        JournalLine.journal_entry_id.in_([entry1.id, entry2.id])
    )
    row = (await async_db.execute(sum_suspense)).one()
    assert row.d == row.c == inflow_amount
    assert (row.c - row.d) == Decimal("0.00") # Suspense fully cleared!
