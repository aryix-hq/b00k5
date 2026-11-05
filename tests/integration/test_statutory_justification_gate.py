"""
Integration Test Suite: Statutory Reconciliation Justification & Classification Review Gate
Governed by FEAT-OPS-07 / PLAN-007.

Verifies:
1. Classification heuristic engine (`suggest_statutory_justification`):
   - Debit card fees -> Code 4030 Finance Costs & Bank Charges
   - Self-vouched operational expenses -> Code 4090 Miscellaneous Business Expenses
   - Vendor advances without bill -> Code 1030 Prepaid Expenses & Vendor Advances
   - Director personal swipes -> Code 1040 Loans & Advances to Directors / Director Current Account
2. Batch allocation engine (`batch_allocate_lines`):
   - Generates balanced double-entry Journal Entries (Debit == Credit)
   - Accurately posts contra accounts (clearing Suspense 2099 or direct Bank 1010)
   - Updates statement lines to 'reconciled' with statutory narrations in notes
3. Global sweep gate intercept:
   - Identifies remaining unbilled/unmatched withdrawals
   - Triggers `requires_statutory_justification: True` and returns `suspense_lines`
"""

import uuid
from decimal import Decimal
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.tenant import Tenant, User
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.bank import BankStatement, BankStatementLine
from app.schemas.bank import BatchAllocateRequest, BatchAllocateItem
from app.api.v1.reconciliation import (
    suggest_statutory_justification,
    batch_allocate_lines,
    reconcile_all_statements,
    get_pending_justifications
)
from app.core.iam import IAMContext


def test_suggest_statutory_justification_rules():
    """Validates statutory classification rules under Companies Act Sec 128 & IT Act Sec 37."""
    # 1. Debit card maintenance fee
    l_card = BankStatementLine(
        description="ANNUAL DEBIT CARD MAINTENANCE CHG",
        counterparty_name=None,
        reference_number="CHG99283"
    )
    res_card = suggest_statutory_justification(l_card)
    assert res_card["suggested_category"] == "bank_fee"
    assert res_card["suggested_account_code"] == "4030"
    assert "Statutory Finance Cost" in res_card["suggested_narration"]

    # 2. Advance to vendor
    l_adv = BankStatementLine(
        description="IMPS/ADVANCE TO HARDWARE SUPPLIER/CHQ",
        counterparty_name="TECH HARDWARE LTD",
        reference_number="992837162"
    )
    res_adv = suggest_statutory_justification(l_adv)
    assert res_adv["suggested_category"] == "vendor_advance"
    assert res_adv["suggested_account_code"] == "1030"
    assert "Advance disbursement" in res_adv["suggested_narration"]

    # 3. Director personal swipe / ATM cash withdrawal
    l_dir = BankStatementLine(
        description="ATM WDL PERSONAL CASH FOR DIRECTOR",
        counterparty_name=None,
        reference_number="ATM882299"
    )
    res_dir = suggest_statutory_justification(l_dir)
    assert res_dir["suggested_category"] == "director_due"
    assert res_dir["suggested_account_code"] == "1040"
    assert "CA2013 Sec 185" in res_dir["suggested_narration"]

    # 4. Self-vouched operational expense (unbilled debit)
    l_swiggy = BankStatementLine(
        description="UPI/409823124567/SWIGGY INSTAMART/OFFICE SNACKS",
        counterparty_name="SWIGGY INSTAMART",
        reference_number="409823124567"
    )
    res_swiggy = suggest_statutory_justification(l_swiggy)
    assert res_swiggy["suggested_category"] == "self_vouched"
    assert res_swiggy["suggested_account_code"] == "4090"
    assert "IT Act Sec 37" in res_swiggy["suggested_narration"]


@pytest.mark.asyncio
async def test_batch_allocate_lines_double_entry_balance():
    """
    Verifies batch_allocate_lines posts balanced double-entry vouchers:
    - sum(Debit) == sum(Credit)
    - Correct target accounts (4030, 4090, 1030, 1040)
    - Updates statement line status to 'reconciled'
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_tenant = MagicMock(spec=Tenant, id=tenant_id)
    mock_user = MagicMock(spec=User, id=user_id)
    ctx = IAMContext(user=mock_user, tenant=mock_tenant, role="owner")

    # Mock accounts
    bank_acc = MagicMock(spec=ChartOfAccounts, id=uuid.uuid4(), tenant_id=tenant_id, code="1010", name="Bank Current Account")
    suspense_acc = MagicMock(spec=ChartOfAccounts, id=uuid.uuid4(), tenant_id=tenant_id, code="2099", name="Schedule III Suspense Account")
    fee_acc = MagicMock(spec=ChartOfAccounts, id=uuid.uuid4(), tenant_id=tenant_id, code="4030", name="Finance Costs & Bank Charges")
    exp_acc = MagicMock(spec=ChartOfAccounts, id=uuid.uuid4(), tenant_id=tenant_id, code="4090", name="Miscellaneous Business Expenses")

    # Mock statement lines
    line1 = BankStatementLine(
        id=uuid.uuid4(),
        statement_id=uuid.uuid4(),
        tenant_id=tenant_id,
        line_number=1,
        transaction_date=date(2025, 4, 10),
        description="ANNUAL DEBIT CARD FEE",
        withdrawal_amount=Decimal("590.00"),
        deposit_amount=Decimal("0.00"),
        reconciliation_status="suspense_posted",
        reconciliation_tier="tier3_suspense"
    )
    line2 = BankStatementLine(
        id=uuid.uuid4(),
        statement_id=uuid.uuid4(),
        tenant_id=tenant_id,
        line_number=2,
        transaction_date=date(2025, 4, 15),
        description="UPI/LOCAL HARDWARE/CABLES",
        withdrawal_amount=Decimal("1200.00"),
        deposit_amount=Decimal("0.00"),
        reconciliation_status="suspense_posted",
        reconciliation_tier="tier3_suspense"
    )

    mock_db = AsyncMock()

    # Configure mock_db.get returns
    async def mock_get(model, pk):
        if pk == line1.id:
            return line1
        elif pk == line2.id:
            return line2
        elif pk == fee_acc.id:
            return fee_acc
        elif pk == exp_acc.id:
            return exp_acc
        elif pk == suspense_acc.id:
            return suspense_acc
        elif pk == bank_acc.id:
            return bank_acc
        return None
    mock_db.get = mock_get

    # Configure execute results for queries
    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_exec_res

    added_objects = []
    def mock_add(obj):
        added_objects.append(obj)
    def mock_add_all(objs):
        added_objects.extend(objs)
    mock_db.add = mock_add
    mock_db.add_all = mock_add_all

    with patch("app.services.ledger_service.LedgerService.get_account_by_code") as mock_get_code:
        async def mock_lookup(session, t_id, code):
            if code == "1010":
                return bank_acc
            elif code == "2099":
                return suspense_acc
            elif code == "4030":
                return fee_acc
            elif code == "4090":
                return exp_acc
            return None
        mock_get_code.side_effect = mock_lookup

        payload = BatchAllocateRequest(
            allocations=[
                BatchAllocateItem(
                    line_id=line1.id,
                    target_account_code="4030",
                    category_tag="bank_fee",
                    narration="Debit card maintenance fee debited per statement"
                ),
                BatchAllocateItem(
                    line_id=line2.id,
                    target_account_code="4090",
                    category_tag="self_vouched",
                    narration="Self-vouched office cables purchase. IT Act Sec 37."
                )
            ]
        )

        resp = await batch_allocate_lines(payload=payload, ctx=ctx, db=mock_db)
        assert resp["success"] is True
        assert resp["allocated_count"] == 2

        # Check line statuses
        assert line1.reconciliation_status == "reconciled"
        assert line2.reconciliation_status == "reconciled"
        assert "Statutory Allocation" in line1.notes
        assert "Statutory Allocation" in line2.notes

        # Verify posted JournalEntries and JournalLines
        entries = [o for o in added_objects if isinstance(o, JournalEntry)]
        j_lines = [o for o in added_objects if isinstance(o, JournalLine)]
        assert len(entries) == 2
        assert len(j_lines) == 4

        # For line 1 (590.00): Dr 4030 (590), Cr 1010/2099 (590)
        l1_lines = [jl for jl in j_lines if jl.journal_entry_id == entries[0].id]
        dr_l1 = sum(jl.debit_amount for jl in l1_lines)
        cr_l1 = sum(jl.credit_amount for jl in l1_lines)
        assert dr_l1 == cr_l1 == Decimal("590.00")

        # For line 2 (1200.00): Dr 4090 (1200), Cr 1010/2099 (1200)
        l2_lines = [jl for jl in j_lines if jl.journal_entry_id == entries[1].id]
        dr_l2 = sum(jl.debit_amount for jl in l2_lines)
        cr_l2 = sum(jl.credit_amount for jl in l2_lines)
        assert dr_l2 == cr_l2 == Decimal("1200.00")


@pytest.mark.asyncio
async def test_reconcile_all_triggers_statutory_gate():
    """
    Verifies that reconcile_all_statements intercepts remaining unbilled debits
    and returns requires_statutory_justification=True and formatted suspense_lines.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_tenant = MagicMock(spec=Tenant, id=tenant_id)
    mock_user = MagicMock(spec=User, id=user_id)
    ctx = IAMContext(user=mock_user, tenant=mock_tenant, role="owner")

    stmt = MagicMock(spec=BankStatement, id=uuid.uuid4(), tenant_id=tenant_id)
    unmatched_line = BankStatementLine(
        id=uuid.uuid4(),
        statement_id=stmt.id,
        tenant_id=tenant_id,
        line_number=5,
        transaction_date=date(2025, 4, 18),
        description="POS CHG ANNUAL CARD SERVICE",
        withdrawal_amount=Decimal("350.00"),
        deposit_amount=Decimal("0.00"),
        reconciliation_status="suspense_posted",
        reconciliation_tier="tier3_suspense",
        notes="Unmatched bank transaction auto-routed to Schedule III Suspense Account"
    )

    mock_db = AsyncMock()

    # Return statement and unmatched line
    mock_stmts_res = MagicMock()
    mock_stmts_res.scalars.return_value.all.return_value = [stmt]

    mock_lines_res = MagicMock()
    mock_lines_res.scalars.return_value.all.return_value = [unmatched_line]

    mock_db.execute.side_effect = [mock_stmts_res, mock_lines_res]

    with patch("app.services.reconciliation_engine.ReconciliationEngine.reconcile_statement") as mock_engine:
        mock_engine.return_value = {
            "total_lines": 5,
            "tier1_reconciled": 4,
            "tier2_probable": 0,
            "tier3_suspense": 1
        }

        resp = await reconcile_all_statements(ctx=ctx, db=mock_db)
        assert resp["success"] is True
        assert resp["requires_statutory_justification"] is True
        assert resp["pending_justifications_count"] == 1
        assert len(resp["suspense_lines"]) == 1

        first_line = resp["suspense_lines"][0]
        assert first_line["id"] == str(unmatched_line.id)
        assert first_line["withdrawal_amount"] == 350.0
        assert first_line["suggested_account_code"] == "4030"
        assert first_line["suggested_category"] == "bank_fee"
        assert "Statutory Finance Cost" in first_line["suggested_narration"]

