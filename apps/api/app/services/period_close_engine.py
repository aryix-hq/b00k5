"""
b00k5 Financial Engine: Accruals, Period-End Close & Multi-Year Rollover Engine
Pillar 8:
- Prepaid Expenses & Monthly Amortization
- Expense Accruals & Matching Principle
- Year-End Closing Run (Nominal account clearing to zero, Retained earnings transfer, Period lock)
"""

from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date
from typing import Dict, Any, List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.tenant import Tenant
from app.services.ledger_service import LedgerService


class PeriodCloseEngine:
    @staticmethod
    def bankers_round(value: Decimal, places: int = 2) -> Decimal:
        quant = Decimal('10') ** -places
        return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_EVEN)

    @staticmethod
    async def book_prepaid_expense(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        vendor_name: str,
        total_amount: Decimal,
        prepaid_account_code: str = "1070", # Prepaid Expenses (Current Asset)
        bank_account_code: str = "1010",
        booking_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 8.1: Initial Prepaid Expense Booking:
        DR 1070 Prepaid Expenses (Asset) = ₹120,000
        CR 1010 Bank Current Account    = ₹120,000
        """
        b_dt = booking_date or date.today()
        amt = PeriodCloseEngine.bankers_round(total_amount)

        prepaid_acc = await LedgerService.get_account_by_code(session, tenant_id, prepaid_account_code)
        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, bank_account_code)

        if not (prepaid_acc and bank_acc):
            raise ValueError(f"Required accounts ({prepaid_account_code} or {bank_account_code}) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-PREPAID-{uuid.uuid4().hex[:6]}",
            entry_date=b_dt,
            reference_type="prepaid_expense",
            narration=f"Prepayment for {vendor_name} annual subscription",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=prepaid_acc.id,
                debit_amount=amt,
                credit_amount=Decimal("0.00"),
                description=f"Prepaid asset deferral: {vendor_name}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=bank_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=amt,
                description=f"Bank outflow for prepaid subscription: {vendor_name}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    async def amortize_prepaid_expense(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        monthly_expense_amount: Decimal,
        expense_account_code: str = "4010", # Cloud / Software Expense
        prepaid_account_code: str = "1070", # Prepaid Expenses
        period_label: str = "January 2026",
        amortization_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 8.1: Monthly Amortization of Prepaid Expense:
        DR 4010 Software Expense   = ₹10,000
        CR 1070 Prepaid Expenses   = ₹10,000
        Asset balance reduces to ₹110,000.
        """
        a_dt = amortization_date or date.today()
        amt = PeriodCloseEngine.bankers_round(monthly_expense_amount)

        exp_acc = await LedgerService.get_account_by_code(session, tenant_id, expense_account_code)
        prepaid_acc = await LedgerService.get_account_by_code(session, tenant_id, prepaid_account_code)

        if not (exp_acc and prepaid_acc):
            raise ValueError("Required accounts (Expense or Prepaid) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-AMORT-{uuid.uuid4().hex[:6]}",
            entry_date=a_dt,
            reference_type="prepaid_amortization",
            narration=f"Monthly amortization of prepaid software for {period_label}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=exp_acc.id,
                debit_amount=amt,
                credit_amount=Decimal("0.00"),
                description=f"Monthly software expense: {period_label}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=prepaid_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=amt,
                description=f"Prepaid software reduction: {period_label}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    async def book_expense_accrual(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        expense_description: str,
        accrual_amount: Decimal,
        expense_account_code: str = "4040", # or 5010
        accrued_liability_code: str = "2040", # Outstanding Expenses / Accrued Liabilities
        accrual_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 8.2: Expense Accrual under Matching Principle:
        Electricity/Utility bill for March received in April:
        DR 4040 Expense
        CR 2040 Outstanding Expenses / Accrued Liabilities
        """
        a_dt = accrual_date or date.today()
        amt = PeriodCloseEngine.bankers_round(accrual_amount)

        exp_acc = await LedgerService.get_account_by_code(session, tenant_id, expense_account_code)
        liab_acc = await LedgerService.get_account_by_code(session, tenant_id, accrued_liability_code)

        if not (exp_acc and liab_acc):
            raise ValueError("Required accounts (Expense or Accrued Liability) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-ACCRUAL-{uuid.uuid4().hex[:6]}",
            entry_date=a_dt,
            reference_type="expense_accrual",
            narration=f"Expense accrual: {expense_description} for period ending {a_dt}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=exp_acc.id,
                debit_amount=amt,
                credit_amount=Decimal("0.00"),
                description=f"Accrued expense recognized: {expense_description}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=liab_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=amt,
                description=f"Outstanding liability for: {expense_description}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    async def close_financial_year(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year_label: str = "FY 2025-26",
        retained_earnings_code: str = "2020", # Reserves & Surplus / Retained Earnings
        closing_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Pillar 8.3: Year-End Closing Sequence:
        1. Nominal Accounts (Revenue & Expenses): Cleared to exactly ₹0.00.
        2. Retained Earnings Transfer: Net Profit = Sum(Revenue) - Sum(Expense)
           credited to Reserves & Surplus / Retained Earnings (Code 2020/3010).
        3. Real & Personal Accounts (Assets, Liabilities, Equity): Rolled forward.
        4. Audit Lock: Period is marked is_closed = True. System rejects backdated postings.
        """
        c_dt = closing_date or date(2026, 3, 31)

        # 1. Fetch all nominal accounts (Revenue & Expense)
        nominal_stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.tenant_id == tenant_id,
            ChartOfAccounts.type.in_(["revenue", "expense"]),
            ChartOfAccounts.is_active == True
        )
        nominal_accounts = (await session.execute(nominal_stmt)).scalars().all()

        retained_acc = await LedgerService.get_account_by_code(session, tenant_id, retained_earnings_code)
        if not retained_acc:
            raise ValueError(f"Retained earnings account ({retained_earnings_code}) not found.")

        # Calculate net balances for each nominal account
        lines = []
        total_revenue = Decimal("0.00")
        total_expense = Decimal("0.00")

        # Entry header
        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-CLOSE-{fiscal_year_label.replace(' ', '_')}",
            entry_date=c_dt,
            reference_type="year_end_close",
            narration=f"Annual year-end closing entry for {fiscal_year_label} - Nominal clearing to Retained Earnings",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        for acc in nominal_accounts:
            sum_stmt = select(
                func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
                func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
            ).join(
                JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
            ).where(
                JournalLine.tenant_id == tenant_id,
                JournalLine.account_id == acc.id,
                JournalEntry.status == "posted",
                JournalEntry.id != entry.id,
                JournalEntry.entry_date <= c_dt
            )
            row = (await session.execute(sum_stmt)).one()
            d_sum, c_sum = row.d, row.c

            if acc.type == "revenue":
                net_rev = c_sum - d_sum
                if net_rev != Decimal("0.00"):
                    total_revenue += net_rev
                    # Clear revenue credit balance by DEBITING revenue account
                    lines.append(JournalLine(
                        journal_entry_id=entry.id,
                        tenant_id=tenant_id,
                        account_id=acc.id,
                        debit_amount=net_rev,
                        credit_amount=Decimal("0.00"),
                        description=f"Year-end nominal closing of revenue account {acc.code}"
                    ))
            elif acc.type == "expense":
                net_exp = d_sum - c_sum
                if net_exp != Decimal("0.00"):
                    total_expense += net_exp
                    # Clear expense debit balance by CREDITING expense account
                    lines.append(JournalLine(
                        journal_entry_id=entry.id,
                        tenant_id=tenant_id,
                        account_id=acc.id,
                        debit_amount=Decimal("0.00"),
                        credit_amount=net_exp,
                        description=f"Year-end nominal closing of expense account {acc.code}"
                    ))

        net_profit = total_revenue - total_expense

        # Retained Earnings Leg:
        # If profit > 0, Credit Retained Earnings
        # If loss > 0, Debit Retained Earnings
        if net_profit > Decimal("0.00"):
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=retained_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=net_profit,
                description=f"Transfer of net surplus to Retained Earnings for {fiscal_year_label}"
            ))
        elif net_profit < Decimal("0.00"):
            loss_val = abs(net_profit)
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=retained_acc.id,
                debit_amount=loss_val,
                credit_amount=Decimal("0.00"),
                description=f"Transfer of net loss to Retained Earnings for {fiscal_year_label}"
            ))

        total_deb = sum(l.debit_amount for l in lines)
        total_crd = sum(l.credit_amount for l in lines)
        if total_deb != total_crd:
            raise ValueError(f"Imbalanced year-end closing entry: Debits ({total_deb}) != Credits ({total_crd})")

        session.add_all(lines)
        await session.flush()

        # 4. Audit Lock: Update tenant closed periods in statutory profile
        tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()
        if tenant:
            profile = dict(tenant.statutory_profile or {})
            closed_periods = profile.get("closed_periods", [])
            if fiscal_year_label not in closed_periods:
                closed_periods.append(fiscal_year_label)
            profile["closed_periods"] = closed_periods
            profile[f"closed_until_{fiscal_year_label}"] = c_dt.isoformat()
            tenant.statutory_profile = profile
            await session.flush()

        return {
            "journal_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "fiscal_year": fiscal_year_label,
            "total_revenue_cleared": total_revenue,
            "total_expense_cleared": total_expense,
            "net_profit_transferred": net_profit,
            "is_closed": True
        }

    @staticmethod
    def verify_period_is_open(tenant: Tenant, entry_date: date):
        """Rejects transaction posting if entry date falls within a closed fiscal period."""
        profile = tenant.statutory_profile or {}
        closed_periods = profile.get("closed_periods", [])
        for p in closed_periods:
            closed_until_str = profile.get(f"closed_until_{p}")
            if closed_until_str:
                closed_until = date.fromisoformat(closed_until_str)
                if entry_date <= closed_until:
                    raise PermissionError(
                        f"Period Lockout Error: Financial period '{p}' is closed. "
                        f"Backdated entries on or before {closed_until} are strictly prohibited by law."
                    )

    @staticmethod
    async def book_prior_period_adjustment(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        omitted_item_description: str,
        amount: Decimal,
        closed_fiscal_year_label: str,
        adjustment_date: Optional[date] = None,
        expense_or_loss_code: str = "4040",
        liability_or_bank_code: str = "2040",
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 10.2: Prior-Period Adjustment Tracking (AS 5 / Ind AS 8):
        Omitted transactions from closed financial years cannot mutate the closed period.
        The system requires an explicit Prior Period Adjustment Voucher dated in the
        current open period with distinct P&L disclosure.
        """
        tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()
        adj_dt = adjustment_date or date.today()

        if tenant:
            PeriodCloseEngine.verify_period_is_open(tenant, adj_dt)

        exp_acc = await LedgerService.get_account_by_code(session, tenant_id, expense_or_loss_code)
        cr_acc = await LedgerService.get_account_by_code(session, tenant_id, liability_or_bank_code)

        if not (exp_acc and cr_acc):
            raise ValueError("Required accounts for Prior Period Adjustment not found.")

        amt = PeriodCloseEngine.bankers_round(amount)

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-PPA-{uuid.uuid4().hex[:6]}",
            entry_date=adj_dt,
            reference_type="prior_period_adjustment",
            narration=f"Prior Period Adjustment for {closed_fiscal_year_label}: {omitted_item_description}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=exp_acc.id,
                debit_amount=amt,
                credit_amount=Decimal("0.00"),
                description=f"Prior period adjustment ({closed_fiscal_year_label}): {omitted_item_description}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=cr_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=amt,
                description=f"Liability recognized for prior period item ({closed_fiscal_year_label})"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry
