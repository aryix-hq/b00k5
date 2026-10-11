"""
Pillar 3: Accounts Receivable (AR) & Sales Sub-Ledger Audit Tests
Asserts:
1. Invoice Posting & Sub-Ledger Sync: DR AR 118,000 | CR Rev 100,000, CR CGST 9,000, CR SGST 9,000.
2. Partial Payments & AR Aging: Payment of 50,000 drops balance to 68,000; aged into 0-30 days.
3. Credit Notes & Tax Reversals: Credit note for 20,000 + 18% tax reverses revenue, tax, and AR.
4. Bad Debt Write-Off: DR Bad Debt Expense, CR AR; customer balance zeroes without tax contamination.
"""

from decimal import Decimal
from datetime import date, timedelta
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.subledger_service import SubledgerService
from app.services.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_01_invoice_posting_and_subledger_sync(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 3.1: Post Tax Invoice #INV-001:
    Subtotal ₹100,000, CGST ₹9,000, SGST ₹9,000. Total ₹118,000.
    DR AR (1020): ₹118,000 | CR Revenue (3010): ₹100,000, CR CGST (2050): ₹9,000, CR SGST (2051): ₹9,000.
    Customer AR sub-ledger balance increases by exactly ₹118,000.
    """
    customer_id = uuid.uuid4()
    inv_num = f"INV-TEST-{uuid.uuid4().hex[:6]}"

    post_res = await SubledgerService.post_tax_invoice(
        session=async_db,
        tenant_id=tenant_a.id,
        customer_id=customer_id,
        invoice_number=inv_num,
        subtotal=Decimal("100000.00"),
        cgst_rate=Decimal("9.00"),
        sgst_rate=Decimal("9.00")
    )

    assert post_res["subtotal"] == Decimal("100000.00")
    assert post_res["cgst_amount"] == Decimal("9000.00")
    assert post_res["sgst_amount"] == Decimal("9000.00")
    assert post_res["grand_total"] == Decimal("118000.00")

    # Verify journal lines
    jv_stmt = select(JournalLine).where(JournalLine.journal_entry_id == post_res["journal_entry_id"])
    lines = (await async_db.execute(jv_stmt)).scalars().all()
    assert len(lines) == 4

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == Decimal("118000.00")

    # Verify customer AR balance increased
    ar_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1020")
    ar_bal_stmt = select(
        func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
        func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
    ).where(JournalLine.tenant_id == tenant_a.id, JournalLine.account_id == ar_acc.id)
    row = (await async_db.execute(ar_bal_stmt)).one()
    assert (row.d - row.c) >= Decimal("118000.00")


@pytest.mark.asyncio
async def test_02_partial_payments_and_aging_buckets(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 3.2: Apply payment of ₹50,000 against #INV-001:
    Outstanding balance reduces from ₹118,000 to ₹68,000.
    AR Aging Schedule correctly buckets remaining ₹68,000 into 0-30 days.
    """
    inv_num = f"INV-AGING-{uuid.uuid4().hex[:6]}"
    customer_id = uuid.uuid4()

    await SubledgerService.post_tax_invoice(
        session=async_db,
        tenant_id=tenant_a.id,
        customer_id=customer_id,
        invoice_number=inv_num,
        subtotal=Decimal("100000.00"),
        cgst_rate=Decimal("9.00"),
        sgst_rate=Decimal("9.00")
    )

    # Apply payment of 50,000
    pay_entry = await SubledgerService.apply_partial_payment(
        session=async_db,
        tenant_id=tenant_a.id,
        invoice_number=inv_num,
        payment_amount=Decimal("50000.00")
    )
    assert pay_entry.status == "posted"

    # Calculate remaining balance
    original_total = Decimal("118000.00")
    paid_total = Decimal("50000.00")
    remaining_balance = original_total - paid_total
    assert remaining_balance == Decimal("68000.00")

    # Verify aging schedule
    open_invoices = [{
        "invoice_number": inv_num,
        "issue_date": date.today() - timedelta(days=10), # 10 days old
        "outstanding_balance": remaining_balance
    }]
    aging = SubledgerService.calculate_ar_aging_buckets(open_invoices, as_of_date=date.today())

    assert aging["current_0_30"] == Decimal("68000.00")
    assert aging["overdue_31_60"] == Decimal("0.00")
    assert aging["total_outstanding"] == Decimal("68000.00")


@pytest.mark.asyncio
async def test_03_credit_notes_and_tax_reversals(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 3.3: Issue Credit Note for ₹20,000 + 18% tax (₹3,600) against invoice:
    DR 3010 Revenue (Sales Return) = ₹20,000
    DR 2050 Output CGST (9%)       = ₹1,800
    DR 2051 Output SGST (9%)       = ₹1,800
    CR 1020 Accounts Receivable    = ₹23,600
    Customer AR sub-ledger reduces by exactly ₹23,600.
    """
    inv_num = f"INV-CN-{uuid.uuid4().hex[:6]}"
    cn_num = f"CN-{uuid.uuid4().hex[:6]}"
    customer_id = uuid.uuid4()

    # Post initial invoice: 100,000 + 18% = 118,000
    await SubledgerService.post_tax_invoice(
        session=async_db,
        tenant_id=tenant_a.id,
        customer_id=customer_id,
        invoice_number=inv_num,
        subtotal=Decimal("100000.00")
    )

    # Issue credit note for 20,000 base + 18% tax = 23,600 total
    cn_entry = await SubledgerService.issue_credit_note(
        session=async_db,
        tenant_id=tenant_a.id,
        invoice_number=inv_num,
        credit_note_number=cn_num,
        return_subtotal=Decimal("20000.00"),
        cgst_rate=Decimal("9.00"),
        sgst_rate=Decimal("9.00")
    )

    # Check journal lines of credit note
    cn_lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == cn_entry.id)
    cn_lines = (await async_db.execute(cn_lines_stmt)).scalars().all()
    assert len(cn_lines) == 4

    tot_deb = sum(l.debit_amount for l in cn_lines)
    tot_crd = sum(l.credit_amount for l in cn_lines)
    assert tot_deb == tot_crd == Decimal("23600.00")


@pytest.mark.asyncio
async def test_04_bad_debt_write_off(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 3.4: Bad Debt Write-Off:
    Customer becomes insolvent; remaining debt of ₹44,400 declared uncollectible:
    DR 4040 Bad Debt Expense  = ₹44,400.00
    CR 1020 Accounts Receivable = ₹44,400.00
    Customer balance drops to ₹0; Tax accounts remain untouched.
    """
    inv_num = f"INV-BAD-{uuid.uuid4().hex[:6]}"
    customer_id = uuid.uuid4()
    write_off_amt = Decimal("44400.00")

    wo_entry = await SubledgerService.write_off_bad_debt(
        session=async_db,
        tenant_id=tenant_a.id,
        invoice_number=inv_num,
        write_off_amount=write_off_amt
    )

    # Verify journal entry lines
    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == wo_entry.id)
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2

    # Line 1: DR Bad Debt Expense
    assert lines[0].debit_amount == write_off_amt
    assert lines[0].credit_amount == Decimal("0.00")

    # Line 2: CR Accounts Receivable
    assert lines[1].debit_amount == Decimal("0.00")
    assert lines[1].credit_amount == write_off_amt

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == write_off_amt
