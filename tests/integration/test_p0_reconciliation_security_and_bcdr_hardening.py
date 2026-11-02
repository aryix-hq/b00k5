"""
Integration and Regression Test Suite:
P0/P1/P2 Defect Hardening: Reconciliation Locks, Security Boundaries, BCDR Integrity, and Ind AS 8 Compliance.
Governed by DEF-AUDIT-ALL.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.tenant import Tenant, User
from app.models.invoice import Invoice
from app.models.expense import Expense
from app.models.payroll import ContractorPayment, Contractor
from app.models.bank import BankStatementLine
from app.models.ledger import JournalEntry, JournalLine
from app.services.payroll_service import PayrollService
from app.services.db_backup import DatabaseBackupManager
from app.api.v1.invoices import strike_off_invoice
from app.api.v1.expenses import strike_off_expense
from app.api.v1.storage import get_presigned_url_endpoint, get_sync_status
from app.core.iam import IAMContext


@pytest.mark.asyncio
async def test_reconciled_contractor_payment_strike_off_blocked():
    """DEF-01: Prohibit strike-off of contractor payments when reconciled with bank statement."""
    tenant_id = uuid.uuid4()
    payment_id = uuid.uuid4()
    disb_jv_id = uuid.uuid4()

    mock_payment = MagicMock(spec=ContractorPayment)
    mock_payment.id = payment_id
    mock_payment.tenant_id = tenant_id
    mock_payment.payment_number = "CPAY-2026-001"
    mock_payment.contractor_id = uuid.uuid4()
    mock_payment.status = "reconciled"
    mock_payment.disbursement_journal_id = disb_jv_id
    mock_payment.accrual_journal_id = uuid.uuid4()

    mock_session = AsyncMock()

    # Case 1: Payment status is directly 'reconciled'
    with patch.object(PayrollService, "get_contractor_payment", return_value=mock_payment):
        with pytest.raises(ValueError) as exc:
            await PayrollService.strike_off_contractor_payment(
                session=mock_session,
                tenant_id=tenant_id,
                payment_id=payment_id,
                reason="Void test"
            )
        assert "Cannot strike off a contractor payment that has been reconciled" in str(exc.value)

    # Case 2: Payment status is 'disbursed', but linked to a reconciled bank line
    mock_payment.status = "disbursed"
    mock_reconciled_line = MagicMock(spec=BankStatementLine)
    mock_reconciled_line.line_number = 42
    mock_reconciled_line.reference_number = "UTR99281726"

    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.first.return_value = mock_reconciled_line
    mock_session.execute.return_value = mock_exec_res

    with patch.object(PayrollService, "get_contractor_payment", return_value=mock_payment):
        with pytest.raises(ValueError) as exc2:
            await PayrollService.strike_off_contractor_payment(
                session=mock_session,
                tenant_id=tenant_id,
                payment_id=payment_id,
                reason="Void test"
            )
        assert "The associated disbursement journal is matched and reconciled against bank statement line #42" in str(exc2.value)


@pytest.mark.asyncio
async def test_reconciled_expense_strike_off_blocked():
    """DEF-02: Prohibit strike-off of expenses when settled/reconciled with bank feed."""
    tenant_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_expense = MagicMock(spec=Expense)
    mock_expense.id = expense_id
    mock_expense.tenant_id = tenant_id
    mock_expense.employee_id = user_id
    mock_expense.status = "approved"
    mock_expense.settlement_status = "reconciled"
    mock_expense.merchant_name = "AWS Cloud Hosting"
    mock_expense.journal_entry_number = "JV-EXP-001"

    mock_session = AsyncMock()
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.first.return_value = mock_expense
    mock_session.execute.return_value = mock_exec_res

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.id = tenant_id

    mock_ctx = MagicMock(spec=IAMContext)
    mock_ctx.user = mock_user
    mock_ctx.tenant = mock_tenant
    mock_ctx.role = "owner"

    with pytest.raises(HTTPException) as exc:
        await strike_off_expense(
            expense_id=expense_id,
            reason="Test",
            ctx=mock_ctx,
            db=mock_session
        )
    assert exc.value.status_code == 400
    assert "Cannot strike off an expense that has been reconciled" in exc.value.detail


@pytest.mark.asyncio
async def test_paid_invoice_strike_off_blocked():
    """DEF-03: Prohibit strike-off of paid invoices; enforce CGST Section 34 Credit Notes."""
    tenant_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    mock_inv = MagicMock(spec=Invoice)
    mock_inv.id = inv_id
    mock_inv.tenant_id = tenant_id
    mock_inv.invoice_number = "INV-2026-0099"
    mock_inv.status = "paid"

    mock_session = AsyncMock()
    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = mock_inv
    mock_session.execute.return_value = mock_exec_res

    mock_ctx = MagicMock(spec=IAMContext)
    mock_ctx.user = MagicMock(id=uuid.uuid4())
    mock_ctx.tenant = MagicMock(id=tenant_id)

    with pytest.raises(HTTPException) as exc:
        await strike_off_invoice(
            invoice_id=inv_id,
            reason="Void paid invoice",
            ctx=mock_ctx,
            db=mock_session
        )
    assert exc.value.status_code == 400
    assert "paid invoices cannot be struck off" in exc.value.detail


@pytest.mark.asyncio
async def test_prior_period_invoice_reversal_dates_today():
    """DEF-09 / Ind AS 8: Prior period invoice strike-offs must be recognized in current active period."""
    tenant_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    mock_inv = MagicMock(spec=Invoice)
    mock_inv.id = inv_id
    mock_inv.tenant_id = tenant_id
    mock_inv.invoice_number = "INV-2024-001"
    mock_inv.status = "sent"
    mock_inv.issue_date = date(2024, 5, 10)  # Prior year
    mock_inv.subtotal = Decimal("10000.00")
    mock_inv.cgst_total = Decimal("900.00")
    mock_inv.sgst_total = Decimal("900.00")
    mock_inv.igst_total = Decimal("0.00")
    mock_inv.grand_total = Decimal("11800.00")

    mock_session = AsyncMock()
    mock_exec_inv = MagicMock()
    mock_exec_inv.scalar_one_or_none.return_value = mock_inv

    mock_exec_recon = MagicMock()
    mock_exec_recon.scalars.return_value.first.return_value = None

    mock_session.execute.side_effect = [mock_exec_inv, mock_exec_recon]

    mock_ctx = MagicMock(spec=IAMContext)
    mock_ctx.user = MagicMock(id=uuid.uuid4())
    mock_ctx.tenant = MagicMock(id=tenant_id)

    with patch("app.services.ledger_service.LedgerService.get_account_by_code", return_value=MagicMock(id=uuid.uuid4())):
        res = await strike_off_invoice(
            invoice_id=inv_id,
            reason="Void old sent invoice",
            ctx=mock_ctx,
            db=mock_session
        )

    assert res["success"] is True
    assert mock_inv.status == "cancelled"

    # Verify JournalEntry entry_date is today's date (current fiscal period), not backdated to 2024
    added_objects = [call[0][0] for call in mock_session.add.call_args_list]
    je_entries = [obj for obj in added_objects if isinstance(obj, JournalEntry)]
    assert len(je_entries) == 1
    assert je_entries[0].entry_date == date.today()


def test_db_restore_pg_restore_failure_returns_false():
    """DEF-05: Ensure pg_restore exit code > 1 returns False, preventing silent disaster recovery false-success."""
    mock_res = MagicMock()
    mock_res.returncode = 2  # Fatal pg_restore error
    mock_res.stderr = b"pg_restore: error: ARCHIVE IS CORRUPT"

    with patch("subprocess.run", return_value=mock_res):
        success = DatabaseBackupManager.execute_pg_restore(b"corrupt-bytes")
        assert success is False, "DatabaseBackupManager.execute_pg_restore must return False on non-zero/non-one returncode"


@pytest.mark.asyncio
async def test_presigned_url_tenant_scoping():
    """DEF-06: Presigned URL endpoint must enforce tenant scoping and block cross-tenant object access."""
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    mock_tenant_a = MagicMock(spec=Tenant)
    mock_tenant_a.id = tenant_a_id

    mock_user = MagicMock(spec=User)
    mock_user.role = "employee"
    mock_user.is_super_admin = False

    # Case 1: Employee of Tenant A requests object belonging to Tenant B -> HTTP 403
    foreign_object = f"{tenant_b_id}/vault/coi_secret.pdf"
    with pytest.raises(HTTPException) as exc:
        await get_presigned_url_endpoint(
            bucket="b00k5-vault",
            object_name=foreign_object,
            tenant=mock_tenant_a,
            current_user=mock_user
        )
    assert exc.value.status_code == 403
    assert "Access denied" in exc.value.detail

    # Case 2: Employee of Tenant A requests object belonging to Tenant A -> Success
    valid_object = f"{tenant_a_id}/vault/invoices/INV_001.pdf"
    with patch("app.core.s3.storage_manager.generate_presigned_url", return_value="https://minio.local/signed/url"):
        resp = await get_presigned_url_endpoint(
            bucket="b00k5-vault",
            object_name=valid_object,
            tenant=mock_tenant_a,
            current_user=mock_user
        )
        assert resp.presigned_url == "https://minio.local/signed/url"
