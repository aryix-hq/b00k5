"""
Pillar 12: Financial Statements Mathematical Integrity Audit Tests
Asserts:
1. Trial Balance Zero-Check:
   Sum(All Account Debit Balances) - Sum(All Account Credit Balances) == 0.00 across all accounts.
2. The Fundamental Accounting Equation:
   Assets == Liabilities + Equity + (Current Period Revenue - Current Period Expenses) with zero paise deviation.
3. Cash Flow Statement Direct & Indirect Reconciliation:
   Operating Activities + Investing Activities + Financing Activities == Net Change in Cash (Ending Cash - Beginning Cash).
"""

from decimal import Decimal
from datetime import date, timedelta
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService
from app.services.financial_reporting_service import FinancialReportingService


async def _seed_comprehensive_ledger_activity(session: AsyncSession, tenant_id: uuid.UUID):
    """Seed realistic full-cycle ledger activity for financial statements."""
    bank_acc = await LedgerService.get_account_by_code(session, tenant_id, "1010") # Asset
    ar_acc = await LedgerService.get_account_by_code(session, tenant_id, "1020") # Asset
    asset_acc = await LedgerService.get_account_by_code(session, tenant_id, "1050") # Asset (Hardware)
    dep_acc = await LedgerService.get_account_by_code(session, tenant_id, "1029") # Contra-Asset (Accum Dep)
    prepaid_acc = await LedgerService.get_account_by_code(session, tenant_id, "1070") # Asset (Prepaid)

    equity_acc = await LedgerService.get_account_by_code(session, tenant_id, "2010") # Equity
    loan_acc = await LedgerService.get_account_by_code(session, tenant_id, "2030") # Liability
    ap_acc = await LedgerService.get_account_by_code(session, tenant_id, "2040") # Liability
    cgst_out = await LedgerService.get_account_by_code(session, tenant_id, "2050") # Liability
    sgst_out = await LedgerService.get_account_by_code(session, tenant_id, "2051") # Liability

    rev_acc = await LedgerService.get_account_by_code(session, tenant_id, "3010") # Revenue
    exp_acc = await LedgerService.get_account_by_code(session, tenant_id, "4010") # Expense
    dep_exp_acc = await LedgerService.get_account_by_code(session, tenant_id, "4020") # Expense (Depreciation)

    today = date.today()

    # 1. Equity Infusion: ₹1,000,000.00
    e1 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-01-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=90), reference_type="equity_infusion", narration="Equity Infusion", status="posted", is_posted=True)
    session.add(e1)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e1.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("1000000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e1.id, tenant_id=tenant_id, account_id=equity_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("1000000.00"))
    ])

    # 2. Promoter Unsecured Loan: ₹200,000.00
    e2 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-02-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=80), reference_type="director_loan", narration="Director Loan", status="posted", is_posted=True)
    session.add(e2)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e2.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("200000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e2.id, tenant_id=tenant_id, account_id=loan_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("200000.00"))
    ])

    # 3. Capital Asset Acquisition (Servers & IT Hardware): ₹300,000.00
    e3 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-03-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=70), reference_type="asset_capitalization", narration="Server Capitalization", status="posted", is_posted=True)
    session.add(e3)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e3.id, tenant_id=tenant_id, account_id=asset_acc.id, debit_amount=Decimal("300000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e3.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("300000.00"))
    ])

    # 4. Annual Software Subscription (Prepaid Asset): ₹120,000.00
    e4 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-04-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=60), reference_type="prepaid_license", narration="Prepaid License", status="posted", is_posted=True)
    session.add(e4)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e4.id, tenant_id=tenant_id, account_id=prepaid_acc.id, debit_amount=Decimal("120000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e4.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("120000.00"))
    ])

    # 5. Customer Revenue Invoicing: Base ₹500,000 + CGST ₹45,000 + SGST ₹45,000 = ₹590,000.00
    e5 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-05-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=50), reference_type="tax_invoice", narration="Subscription Billing", status="posted", is_posted=True)
    session.add(e5)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e5.id, tenant_id=tenant_id, account_id=ar_acc.id, debit_amount=Decimal("590000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e5.id, tenant_id=tenant_id, account_id=rev_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("500000.00")),
        JournalLine(journal_entry_id=e5.id, tenant_id=tenant_id, account_id=cgst_out.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("45000.00")),
        JournalLine(journal_entry_id=e5.id, tenant_id=tenant_id, account_id=sgst_out.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("45000.00"))
    ])

    # 6. Customer Cash Receipt: ₹400,000.00
    e6 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-06-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=30), reference_type="customer_payment", narration="AR Collection", status="posted", is_posted=True)
    session.add(e6)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e6.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("400000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e6.id, tenant_id=tenant_id, account_id=ar_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("400000.00"))
    ])

    # 7. Cloud Hosting Expense on Credit: ₹80,000.00
    e7 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-07-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=20), reference_type="vendor_bill", narration="Cloud Server Invoice", status="posted", is_posted=True)
    session.add(e7)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e7.id, tenant_id=tenant_id, account_id=exp_acc.id, debit_amount=Decimal("80000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e7.id, tenant_id=tenant_id, account_id=ap_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("80000.00"))
    ])

    # 8. Vendor Payment from Bank: ₹50,000.00
    e8 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-08-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=10), reference_type="vendor_payment", narration="Vendor Payment", status="posted", is_posted=True)
    session.add(e8)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e8.id, tenant_id=tenant_id, account_id=ap_acc.id, debit_amount=Decimal("50000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e8.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000.00"))
    ])

    # 9. Non-cash Depreciation Run: ₹15,000.00
    e9 = JournalEntry(tenant_id=tenant_id, entry_number=f"JV-FIN-09-{uuid.uuid4().hex[:4]}", entry_date=today - timedelta(days=5), reference_type="depreciation_run", narration="Monthly Depreciation", status="posted", is_posted=True)
    session.add(e9)
    await session.flush()
    session.add_all([
        JournalLine(journal_entry_id=e9.id, tenant_id=tenant_id, account_id=dep_exp_acc.id, debit_amount=Decimal("15000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=e9.id, tenant_id=tenant_id, account_id=dep_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("15000.00"))
    ])

    await session.flush()


@pytest.mark.asyncio
async def test_01_trial_balance_zero_check(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 12.1: Trial Balance Zero-Check:
    Sum(Debit Balances) - Sum(Credit Balances) == 0.00
    Strict invariant: Discrepancy must equal ₹0.00.
    """
    await _seed_comprehensive_ledger_activity(async_db, tenant_a.id)

    tb = await FinancialReportingService.generate_trial_balance(async_db, tenant_a.id)

    assert tb["is_balanced"] is True
    assert tb["drift"] == Decimal("0.00")
    assert tb["total_debits"] > Decimal("0.00")
    assert tb["total_debits"] == tb["total_credits"]


@pytest.mark.asyncio
async def test_02_fundamental_accounting_equation(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 12.2: The Fundamental Accounting Equation:
    Assets == Liabilities + Equity + (Revenue - Expenses)
    Discrepancy must strictly equal ₹0.00 to exact paise.
    """
    await _seed_comprehensive_ledger_activity(async_db, tenant_a.id)

    # 1. Generate P&L
    pnl = await FinancialReportingService.generate_profit_and_loss(async_db, tenant_a.id)
    assert pnl["total_revenue"] == Decimal("500000.00")
    assert pnl["total_expenses"] == Decimal("95000.00") # 80,000 hosting + 15,000 depreciation
    assert pnl["net_profit"] == Decimal("405000.00")

    # 2. Generate Balance Sheet
    bs = await FinancialReportingService.generate_balance_sheet(async_db, tenant_a.id)

    assert bs["is_equation_satisfied"] is True
    assert bs["drift"] == Decimal("0.00")
    assert bs["current_period_net_profit"] == Decimal("405000.00")

    # Mathematical identity verification:
    # Assets == Liabilities + Equity + Net Profit
    assert bs["total_assets"] == bs["total_equity_and_liabilities"]


@pytest.mark.asyncio
async def test_03_cash_flow_statement_reconciliation(async_db: AsyncSession, tenant_a: Tenant):
    """
    Pillar 12.3: Cash Flow Statement Direct & Indirect Reconciliation:
    Operating + Investing + Financing == Ending Cash - Beginning Cash
    Matches Bank account net change with zero discrepancy.
    """
    await _seed_comprehensive_ledger_activity(async_db, tenant_a.id)

    cf = await FinancialReportingService.generate_cash_flow_statement(async_db, tenant_a.id)

    assert cf["is_reconciled"] is True
    assert cf["drift"] == Decimal("0.00")
    assert cf["net_cash_change_computed"] == cf["net_cash_change_actual"]

    # Verify breakdown:
    # Financing Inflow: ₹1,000,000 (Equity) + ₹200,000 (Director Loan) = ₹1,200,000.00
    assert cf["financing_cash_flow"] == Decimal("1200000.00")

    # Investing Outflow: ₹300,000 (Hardware Capitalization) = -₹300,000.00
    assert cf["investing_cash_flow"] == Decimal("-300000.00")

    # Operating Cash Flow: ₹400,000 (Customer collection) - ₹120,000 (Prepaid) - ₹50,000 (Vendor) = ₹230,000.00
    assert cf["operating_cash_flow"] == Decimal("230000.00")

    # Net change = 1,200,000 - 300,000 + 230,000 = ₹1,130,000.00
    assert cf["ending_cash"] == Decimal("1130000.00")
    assert cf["net_cash_change_actual"] == Decimal("1130000.00")
