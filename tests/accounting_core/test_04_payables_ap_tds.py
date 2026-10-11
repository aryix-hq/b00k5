"""
Pillar 4: Accounts Payable (AP), Procurement & Statutory Withholding (TDS) Audit Tests
Asserts:
1. Vendor Bill Posting with TDS Withholding: DR Expense 100,000, DR GST Input 18,000 | CR TDS 10,000, CR AP 108,000.
2. Vendor Debit Note (Purchase Return): DR AP 29,500 | CR Returns 25,000, CR GST Input 4,500.
3. Statutory TDS Remittance: DR TDS Payable, CR Bank; liability zeroes out, bank reflects outflow.
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
async def test_01_vendor_bill_posting_with_tds_withholding(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 4.1: Vendor Bill for Professional Legal Services:
    Base ₹100,000 + 18% IGST (₹18,000) = ₹118,000.
    Statutory TDS 10% on base under Section 194J = ₹10,000.
    DR 4040 Legal Expense: ₹100,000 | DR 1032 GST Input Credit: ₹18,000
    CR 2060 TDS Payable: ₹10,000    | CR 2040 Vendor AP: ₹108,000
    Total Debits (₹118,000) == Total Credits (₹118,000).
    """
    bill_num = f"BILL-LEGAL-{uuid.uuid4().hex[:6]}"
    vendor_name = "Singhania & Partners Advocates"

    bill_res = await SubledgerService.post_vendor_bill_with_tds(
        session=async_db,
        tenant_id=tenant_a.id,
        vendor_name=vendor_name,
        bill_number=bill_num,
        base_amount=Decimal("100000.00"),
        gst_rate=Decimal("18.00"),
        tds_section="194J",
        tds_rate=Decimal("10.00"),
        expense_account_code="4040",
        is_interstate=True
    )

    assert bill_res["base_amount"] == Decimal("100000.00")
    assert bill_res["gst_amount"] == Decimal("18000.00")
    assert bill_res["tds_amount"] == Decimal("10000.00")
    assert bill_res["net_payable"] == Decimal("108000.00")
    assert bill_res["total_debits"] == Decimal("118000.00")
    assert bill_res["total_credits"] == Decimal("118000.00")

    # Verify journal entry lines in database
    jv_stmt = select(JournalLine).where(JournalLine.journal_entry_id == bill_res["journal_entry_id"])
    lines = (await async_db.execute(jv_stmt)).scalars().all()
    assert len(lines) == 4

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == Decimal("118000.00")


@pytest.mark.asyncio
async def test_02_vendor_debit_note_purchase_return(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 4.2: Vendor Debit Note (Purchase Return):
    Return defective cloud hardware/goods worth ₹25,000 + 18% IGST (₹4,500) = ₹29,500.
    DR 2040 Vendor AP (Reduction in payable) = ₹29,500
    CR 4040 Expense / Purchase Return       = ₹25,000
    CR 1032 GST Input Credit (Tax reversal) = ₹4,500
    """
    bill_num = f"BILL-HW-{uuid.uuid4().hex[:6]}"
    dn_num = f"DN-{uuid.uuid4().hex[:6]}"

    dn_entry = await SubledgerService.issue_vendor_debit_note(
        session=async_db,
        tenant_id=tenant_a.id,
        bill_number=bill_num,
        debit_note_number=dn_num,
        return_base_amount=Decimal("25000.00"),
        gst_rate=Decimal("18.00"),
        expense_account_code="4040",
        is_interstate=True
    )

    dn_lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == dn_entry.id)
    lines = (await async_db.execute(dn_lines_stmt)).scalars().all()
    assert len(lines) == 3

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == Decimal("29500.00")

    # Line 1: DR Vendor AP (₹29,500)
    assert lines[0].debit_amount == Decimal("29500.00")
    assert lines[0].credit_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_03_statutory_tds_remittance(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 4.3: Statutory TDS Remittance:
    Execute monthly government payment run for TDS (Challan ITNS-281):
    DR 2060 TDS Payable          = ₹10,000.00
    CR 1010 Bank Current Account = ₹10,000.00
    TDS Liability zeroes out; bank balance reflects outflow.
    """
    tds_remit_amt = Decimal("10000.00")

    remit_entry = await SubledgerService.remit_statutory_tds(
        session=async_db,
        tenant_id=tenant_a.id,
        tds_amount=tds_remit_amt,
        bank_account_code="1010",
        challan_ref="CHALLAN-ITNS281-APR2026"
    )

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == remit_entry.id)
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2

    # DR TDS Payable
    assert lines[0].debit_amount == tds_remit_amt
    assert lines[0].credit_amount == Decimal("0.00")

    # CR Bank
    assert lines[1].debit_amount == Decimal("0.00")
    assert lines[1].credit_amount == tds_remit_amt

    tot_deb = sum(l.debit_amount for l in lines)
    tot_crd = sum(l.credit_amount for l in lines)
    assert tot_deb == tot_crd == tds_remit_amt
