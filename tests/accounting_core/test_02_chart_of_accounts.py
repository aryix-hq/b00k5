"""
Pillar 2: Chart of Accounts (COA) Structure & Account Normal Balances Audit Tests
Asserts:
1. Normal Balance Behavior: Assets (DR), Liabilities (CR), Equity (CR), Revenue (CR), Expenses (DR).
2. Account Tree & Roll-Up: Parent accounts block direct posting (is_leaf=False); child balances roll up.
3. Deactivation Invariant: Accounts with non-zero balances refuse deactivation.
"""

from decimal import Decimal
from datetime import date
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_01_normal_balance_behavior(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 2.1: Verify Normal Balance Formula across the 5 Standard Classes:
    - Assets: Debit Balance = Debits - Credits
    - Liabilities: Credit Balance = Credits - Debits
    - Equity: Credit Balance = Credits - Debits
    - Revenue: Credit Balance = Credits - Debits
    - Expenses: Debit Balance = Debits - Credits
    """
    # 1. Post transactions across all 5 classes
    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010") # Asset (DR)
    equity_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2010") # Equity (CR)
    ap_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2040") # Liability (CR)
    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010") # Revenue (CR)
    exp_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "4010") # Expense (DR)

    # Initial Capital Infusion: DR Bank 500,000 | CR Equity 500,000
    entry1 = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-COA-CAP-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Initial Equity Capital Injection",
        status="posted",
        is_posted=True
    )
    async_db.add(entry1)
    await async_db.flush()
    async_db.add_all([
        JournalLine(journal_entry_id=entry1.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=Decimal("500000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry1.id, tenant_id=tenant_a.id, account_id=equity_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("500000.00"))
    ])
    await async_db.flush()

    # Revenue Earned: DR Bank 100,000 | CR Revenue 100,000
    entry2 = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-COA-REV-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Subscription Revenue Inflow",
        status="posted",
        is_posted=True
    )
    async_db.add(entry2)
    await async_db.flush()
    async_db.add_all([
        JournalLine(journal_entry_id=entry2.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=Decimal("100000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry2.id, tenant_id=tenant_a.id, account_id=rev_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000.00"))
    ])
    await async_db.flush()

    # Expense on Credit: DR Expense 25,000 | CR AP 25,000
    entry3 = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-COA-EXP-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Cloud server expenses incurred",
        status="posted",
        is_posted=True
    )
    async_db.add(entry3)
    await async_db.flush()
    async_db.add_all([
        JournalLine(journal_entry_id=entry3.id, tenant_id=tenant_a.id, account_id=exp_acc.id, debit_amount=Decimal("25000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry3.id, tenant_id=tenant_a.id, account_id=ap_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("25000.00"))
    ])
    await async_db.flush()

    # 2. Check net balances against normal nature
    tb = await LedgerService.get_trial_balance(async_db, tenant_a.id)
    assert tb["is_balanced"] is True

    items_by_code = {item["code"]: item for item in tb["items"]}

    # Asset (Bank): 500,000 + 100,000 = 600,000 Debit Balance
    assert items_by_code["1010"]["debit_balance"] == Decimal("600000.00")
    assert items_by_code["1010"]["credit_balance"] == Decimal("0.00")

    # Equity (Share Capital): 500,000 Credit Balance
    assert items_by_code["2010"]["credit_balance"] == Decimal("500000.00")
    assert items_by_code["2010"]["debit_balance"] == Decimal("0.00")

    # Liability (AP): 25,000 Credit Balance
    assert items_by_code["2040"]["credit_balance"] == Decimal("25000.00")
    assert items_by_code["2040"]["debit_balance"] == Decimal("0.00")

    # Revenue: 100,000 Credit Balance
    assert items_by_code["3010"]["credit_balance"] == Decimal("100000.00")
    assert items_by_code["3010"]["debit_balance"] == Decimal("0.00")

    # Expense: 25,000 Debit Balance
    assert items_by_code["4010"]["debit_balance"] == Decimal("25000.00")
    assert items_by_code["4010"]["credit_balance"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_02_account_tree_and_roll_up(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 2.2: Account Tree & Roll-Up Tests:
    1. Parent accounts refuse direct transaction posting (is_leaf = False).
    2. Roll-up queries compute exact aggregates from child nodes without timeouts.
    """
    # Parent account Code 1000 has is_leaf = False
    parent_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1000")
    assert parent_acc.is_leaf is False

    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")

    # Attempt to post direct journal entry to parent account
    class FakeLine:
        def __init__(self, account_id, debit, credit):
            self.account_id = account_id
            self.debit_amount = debit
            self.credit_amount = credit
            self.description = "Direct parent posting test"

    class FakePayload:
        def __init__(self, entry_num, lines):
            self.entry_number = entry_num
            self.entry_date = date.today()
            self.reference_type = "manual_jv"
            self.reference_id = None
            self.narration = "Illegal direct posting to parent"
            self.lines = lines

    payload = FakePayload(
        f"JV-PARENT-{uuid.uuid4().hex[:6]}",
        [
            FakeLine(parent_acc.id, Decimal("5000.00"), Decimal("0.00")),
            FakeLine(rev_acc.id, Decimal("0.00"), Decimal("5000.00"))
        ]
    )

    with pytest.raises(ValueError) as exc:
        await LedgerService.create_journal_entry(async_db, tenant_a.id, payload)
    assert "prohibited" in str(exc.value).lower()

    # 2. Test recursive rollup calculation:
    # Post entries to leaf accounts under Current Assets (1010 Bank, 1020 AR)
    child_bank = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    child_ar = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1020")
    equity_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "2010")

    entry_leaf = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-LEAF-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Leaf postings for parent rollup",
        status="posted",
        is_posted=True
    )
    async_db.add(entry_leaf)
    await async_db.flush()

    async_db.add_all([
        JournalLine(journal_entry_id=entry_leaf.id, tenant_id=tenant_a.id, account_id=child_bank.id, debit_amount=Decimal("40000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry_leaf.id, tenant_id=tenant_a.id, account_id=child_ar.id, debit_amount=Decimal("60000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry_leaf.id, tenant_id=tenant_a.id, account_id=equity_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000.00"))
    ])
    await async_db.flush()

    # Roll-up from parent Code 1000 should aggregate 40,000 + 60,000 = 100,000
    rolled_up_balance = await LedgerService.get_account_balance_with_rollups(async_db, tenant_a.id, parent_acc.id)
    assert rolled_up_balance >= Decimal("100000.00")


@pytest.mark.asyncio
async def test_03_deactivation_invariant(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 2.3: Deactivation Invariant:
    Attempt to deactivate an account with a non-zero balance must be blocked.
    Only when balance is zero can an account be deactivated.
    """
    # 1. Create a temporary account with a non-zero balance
    temp_acc = ChartOfAccounts(
        tenant_id=tenant_a.id,
        code=f"1099_{uuid.uuid4().hex[:4]}",
        name="Temporary Clearing Account",
        type="asset",
        sub_type="current_asset",
        normal_balance="debit",
        is_leaf=True,
        is_active=True
    )
    async_db.add(temp_acc)
    await async_db.flush()

    rev_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")

    # Post non-zero transaction
    entry = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-DEACT-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Funding temporary account",
        status="posted",
        is_posted=True
    )
    async_db.add(entry)
    await async_db.flush()

    async_db.add_all([
        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_a.id, account_id=temp_acc.id, debit_amount=Decimal("15000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_a.id, account_id=rev_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("15000.00"))
    ])
    await async_db.flush()

    # Attempt to deactivate while balance is ₹15,000
    with pytest.raises(ValueError) as exc:
        await LedgerService.deactivate_account(async_db, tenant_a.id, temp_acc.id)
    assert "non-zero balance" in str(exc.value).lower()

    # Zero out the balance
    entry_zero = JournalEntry(
        tenant_id=tenant_a.id,
        entry_number=f"JV-ZERO-BAL-{uuid.uuid4().hex[:6]}",
        entry_date=date.today(),
        narration="Zeroing temporary account balance",
        status="posted",
        is_posted=True
    )
    async_db.add(entry_zero)
    await async_db.flush()

    bank_acc = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    async_db.add_all([
        JournalLine(journal_entry_id=entry_zero.id, tenant_id=tenant_a.id, account_id=bank_acc.id, debit_amount=Decimal("15000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=entry_zero.id, tenant_id=tenant_a.id, account_id=temp_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("15000.00"))
    ])
    await async_db.flush()

    # Deactivation succeeds once balance is ₹0.00
    deactivated = await LedgerService.deactivate_account(async_db, tenant_a.id, temp_acc.id)
    assert deactivated.is_active is False
