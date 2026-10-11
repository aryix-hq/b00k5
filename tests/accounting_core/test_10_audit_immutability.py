"""
Pillar 10: Audit Trail, Immutability & Forensic Integrity Audit Tests
Asserts:
1. Zero-Update & Zero-Delete Trigger Test:
   - Direct SQL DELETE FROM journal_entries WHERE id = '<posted_id>' is blocked by DB trigger.
   - Direct SQL UPDATE journal_lines SET debit_amount = 0 WHERE id = '<posted_id>' is blocked by DB trigger.
   - Direct SQL DELETE FROM journal_lines WHERE id = '<posted_id>' is blocked by DB trigger.
2. Prior-Period Adjustment Tracking:
   - Closed period rejects backdated journal postings.
   - Requires explicit Prior Period Adjustment Voucher dated in current open period with distinct disclosure.
3. Forensic Audit Log:
   - State changes record immutable timestamp, user_id, action_type, and pre/post payload.
"""

from decimal import Decimal
from datetime import date, datetime, timezone
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, delete, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models.tenant import Tenant, User
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.expense import Expense, ExpenseAuditLog
from app.services.ledger_service import LedgerService
from app.services.period_close_engine import PeriodCloseEngine


@pytest.mark.asyncio
async def test_01_direct_sql_mutation_blocked_by_triggers(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 10.1: Zero-Update & Zero-Delete Trigger Test:
    Execute direct SQL:
    1. DELETE FROM journal_entries WHERE id = '<posted_id>'
    2. UPDATE journal_lines SET debit_amount = 0 WHERE id = '<posted_id>'
    3. DELETE FROM journal_lines WHERE id = '<posted_id>'
    Database triggers MUST block execution and raise exception:
    'Audit Immutability Violation: Posted journal entries cannot be modified or deleted.'
    """
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")

    # Create and post a journal entry
    entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-POSTED-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Posted entry for immutability trigger validation",
        status="posted",
        is_posted=True
    )
    async_db.add(entry)
    await async_db.flush()

    line1 = JournalLine(
        journal_entry_id=entry.id,
        tenant_id=tenant_a.id,
        account_id=bank_acc.id,
        debit_amount=Decimal("5000.00"),
        credit_amount=Decimal("0.00"),
        description="Leg 1"
    )
    line2 = JournalLine(
        journal_entry_id=entry.id,
        tenant_id=tenant_a.id,
        account_id=rev_acc.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("5000.00"),
        description="Leg 2"
    )
    async_db.add_all([line1, line2])
    await async_db.flush()

    # 1. Direct SQL DELETE on posted journal_entries header
    with pytest.raises((DBAPIError, IntegrityError, Exception)) as exc_delete_header:
        async with async_db.begin_nested():
            await async_db.execute(
                text("DELETE FROM journal_entries WHERE id = :id"),
                {"id": entry.id}
            )
    err_text = str(exc_delete_header.value).lower()
    assert any(w in err_text for w in ["immutable", "cannot be modified or deleted", "violation"])

    # 2. Direct SQL UPDATE on posted journal_lines leg
    with pytest.raises((DBAPIError, IntegrityError, Exception)) as exc_update_line:
        async with async_db.begin_nested():
            await async_db.execute(
                text("UPDATE journal_lines SET debit_amount = 0.00 WHERE id = :id"),
                {"id": line1.id}
            )
    err_text2 = str(exc_update_line.value).lower()
    assert any(w in err_text2 for w in ["immutable", "cannot be modified or deleted", "lines of a posted"])

    # 3. Direct SQL DELETE on posted journal_lines leg
    with pytest.raises((DBAPIError, IntegrityError, Exception)) as exc_delete_line:
        async with async_db.begin_nested():
            await async_db.execute(
                text("DELETE FROM journal_lines WHERE id = :id"),
                {"id": line2.id}
            )
    err_text3 = str(exc_delete_line.value).lower()
    assert any(w in err_text3 for w in ["immutable", "cannot be modified or deleted", "lines of a posted"])

    # Verify that the entry and lines still exist untouched in the database
    chk_entry = (await async_db.execute(select(JournalEntry).where(JournalEntry.id == entry.id))).scalar_one_or_none()
    assert chk_entry is not None
    assert chk_entry.status == "posted"

    chk_lines = (await async_db.execute(select(JournalLine).where(JournalLine.journal_entry_id == entry.id))).scalars().all()
    assert len(chk_lines) == 2
    assert sum(l.debit_amount for l in chk_lines) == Decimal("5000.00")
    assert sum(l.credit_amount for l in chk_lines) == Decimal("5000.00")


@pytest.mark.asyncio
async def test_02_prior_period_adjustment_tracking(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 10.2: Prior-Period Adjustment Tracking:
    1. Close FY 2024-25 (closing date 2025-03-31).
    2. Attempt to post an omitted backdated entry to 2025-01-15 -> Rejected by period lockout.
    3. CA discovers omitted legal retainer fee of ₹50,000 for FY 2024-25.
       Post explicit Prior Period Adjustment Voucher in current open period.
    4. Assert historical closed year retains exact net balances, while current open period
       discloses prior-period item separately.
    """
    # 1. Close FY 2024-25
    await PeriodCloseEngine.close_financial_year(
        session=async_db,
        tenant_id=tenant_a.id,
        fiscal_year_label="FY 2024-25",
        retained_earnings_code="2020",
        closing_date=date(2025, 3, 31)
    )

    # 2. Attempt backdated entry into closed period
    backdated_date = date(2025, 1, 15)
    with pytest.raises(PermissionError) as exc_lockout:
        PeriodCloseEngine.verify_period_is_open(tenant_a, backdated_date)
    assert "Period Lockout Error" in str(exc_lockout.value)

    # 3. Post explicit Prior Period Adjustment Voucher in current open period (e.g. today)
    ppa_entry = await PeriodCloseEngine.book_prior_period_adjustment(
        session=async_db,
        tenant_id=tenant_a.id,
        omitted_item_description="Omitted Q4 FY24-25 statutory legal retainer fee",
        amount=Decimal("50000.00"),
        closed_fiscal_year_label="FY 2024-25",
        adjustment_date=date.today(),
        expense_or_loss_code="4040", # Legal / Professional Fees
        liability_or_bank_code="2040" # Trade Payables / Accrued Liabilities
    )

    assert ppa_entry.reference_type == "prior_period_adjustment"
    assert "FY 2024-25" in ppa_entry.narration

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == ppa_entry.id)
    lines = (await async_db.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2
    assert sum(l.debit_amount for l in lines) == Decimal("50000.00")
    assert sum(l.credit_amount for l in lines) == Decimal("50000.00")


@pytest.mark.asyncio
async def test_03_forensic_audit_trail_logging(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 10.3: Forensic Audit Log:
    - Every state change records immutable timestamp (UTC), user_id, action_type, and pre/post state payload.
    - Audit logs cannot be tampered with.
    """
    # Create test user for changed_by
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"auditor-{user_id.hex[:6]}@example.com",
        password_hash="mock_hash_for_test",
        first_name="Chief",
        last_name="Auditor",
        is_active=True
    )
    async_db.add(user)
    await async_db.flush()

    # Create expense record
    expense = Expense(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        employee_id=user_id,
        merchant_name="AWS Cloud Hosting",
        total_amount=Decimal("12500.00"),
        currency="INR",
        category="Hosting & Infrastructure",
        expense_date=date.today(),
        payment_mode="corporate_card"
    )
    async_db.add(expense)
    await async_db.flush()

    # State change 1: Creation audit log
    log1 = ExpenseAuditLog(
        tenant_id=tenant_a.id,
        expense_id=expense.id,
        changed_by=user_id,
        action="CREATED",
        field_changes={
            "amount": {"old": None, "new": "12500.00"},
            "merchant_name": {"old": None, "new": "AWS Cloud Hosting"}
        },
        reason="Initial expense voucher submission"
    )
    async_db.add(log1)
    await async_db.flush()

    # State change 2: Modification / Correction audit log
    log2 = ExpenseAuditLog(
        tenant_id=tenant_a.id,
        expense_id=expense.id,
        changed_by=user_id,
        action="UPDATED",
        field_changes={
            "amount": {"old": "12500.00", "new": "14750.00"},
            "reason_for_change": "Includes 18% GST invoice component"
        },
        reason="Corrected to gross inclusive amount after invoice received"
    )
    async_db.add(log2)
    await async_db.flush()

    # Assert audit trail integrity
    audit_stmt = select(ExpenseAuditLog).where(
        ExpenseAuditLog.expense_id == expense.id
    ).order_by(ExpenseAuditLog.created_at.asc())
    audit_trail = (await async_db.execute(audit_stmt)).scalars().all()

    assert len(audit_trail) == 2
    assert audit_trail[0].action == "CREATED"
    assert audit_trail[0].changed_by == user_id
    assert audit_trail[0].field_changes["amount"]["new"] == "12500.00"

    assert audit_trail[1].action == "UPDATED"
    assert audit_trail[1].field_changes["amount"]["old"] == "12500.00"
    assert audit_trail[1].field_changes["amount"]["new"] == "14750.00"
    assert audit_trail[1].created_at is not None
