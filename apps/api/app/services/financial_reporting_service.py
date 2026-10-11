"""
b00k5 Financial Engine: Financial Statements Mathematical Integrity Engine
Pillar 12:
- Trial Balance Zero-Sum Verification
- Profit & Loss Statement (Operating Revenue, Cost of Goods, Operating Expenses, Net Profit)
- Balance Sheet (Fundamental Accounting Equation: Assets = Liabilities + Equity + Net Profit)
- Cash Flow Statement (Direct & Indirect Reconciliation against Balance Sheet Cash)
"""

from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date
from typing import Dict, Any, List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService


class FinancialReportingService:
    @staticmethod
    def bankers_round(value: Decimal, places: int = 2) -> Decimal:
        quant = Decimal('10') ** -places
        return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_EVEN)

    @staticmethod
    async def generate_trial_balance(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Pillar 12.1: Trial Balance Zero-Check:
        Sum(All Debit Balances) - Sum(All Credit Balances) == 0.00
        """
        target_date = as_of_date or date.today()

        acc_stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.tenant_id == tenant_id,
            ChartOfAccounts.is_active == True
        ).order_by(ChartOfAccounts.code)
        accounts = (await session.execute(acc_stmt)).scalars().all()

        items = []
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")

        for acc in accounts:
            sum_stmt = select(
                func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
                func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
            ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
                JournalLine.tenant_id == tenant_id,
                JournalLine.account_id == acc.id,
                JournalEntry.entry_date <= target_date,
                JournalEntry.status == "posted"
            )
            row = (await session.execute(sum_stmt)).one()
            d_sum = FinancialReportingService.bankers_round(row.d)
            c_sum = FinancialReportingService.bankers_round(row.c)

            # Normal balance computation
            if acc.normal_balance == "debit":
                net = d_sum - c_sum
                debit_bal = net if net > 0 else Decimal("0.00")
                credit_bal = abs(net) if net < 0 else Decimal("0.00")
            else:
                net = c_sum - d_sum
                credit_bal = net if net > 0 else Decimal("0.00")
                debit_bal = abs(net) if net < 0 else Decimal("0.00")

            if debit_bal > 0 or credit_bal > 0:
                items.append({
                    "account_id": acc.id,
                    "code": acc.code,
                    "name": acc.name,
                    "type": acc.type,
                    "sub_type": acc.sub_type,
                    "debit_balance": debit_bal,
                    "credit_balance": credit_bal
                })
                total_debits += debit_bal
                total_credits += credit_bal

        total_debits = FinancialReportingService.bankers_round(total_debits)
        total_credits = FinancialReportingService.bankers_round(total_credits)
        drift = abs(total_debits - total_credits)

        return {
            "tenant_id": tenant_id,
            "as_of_date": target_date,
            "items": items,
            "total_debits": total_debits,
            "total_credits": total_credits,
            "drift": drift,
            "is_balanced": drift == Decimal("0.00")
        }

    @staticmethod
    async def generate_profit_and_loss(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Pillar 12.2: Profit & Loss Statement (Ind AS / Schedule III):
        Revenue from Operations + Other Income = Total Revenue
        Expenses (Materials, Employees, Depreciation, Other Expenses) = Total Expenses
        Net Profit / Loss = Total Revenue - Total Expenses
        """
        end_date = to_date or date.today()

        acc_stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.tenant_id == tenant_id,
            ChartOfAccounts.type.in_(["revenue", "expense"]),
            ChartOfAccounts.is_active == True
        ).order_by(ChartOfAccounts.code)
        accounts = (await session.execute(acc_stmt)).scalars().all()

        revenue_items = []
        expense_items = []
        total_revenue = Decimal("0.00")
        total_expense = Decimal("0.00")

        for acc in accounts:
            conds = [
                JournalLine.tenant_id == tenant_id,
                JournalLine.account_id == acc.id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date <= end_date
            ]
            if from_date:
                conds.append(JournalEntry.entry_date >= from_date)

            sum_stmt = select(
                func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
                func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
            ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(and_(*conds))

            row = (await session.execute(sum_stmt)).one()
            d_sum = FinancialReportingService.bankers_round(row.d)
            c_sum = FinancialReportingService.bankers_round(row.c)

            if acc.type == "revenue":
                net_rev = c_sum - d_sum
                if net_rev != Decimal("0.00"):
                    revenue_items.append({
                        "code": acc.code,
                        "name": acc.name,
                        "amount": net_rev
                    })
                    total_revenue += net_rev
            elif acc.type == "expense":
                net_exp = d_sum - c_sum
                if net_exp != Decimal("0.00"):
                    expense_items.append({
                        "code": acc.code,
                        "name": acc.name,
                        "amount": net_exp
                    })
                    total_expense += net_exp

        total_revenue = FinancialReportingService.bankers_round(total_revenue)
        total_expense = FinancialReportingService.bankers_round(total_expense)
        net_profit = total_revenue - total_expense

        return {
            "tenant_id": tenant_id,
            "from_date": from_date,
            "to_date": end_date,
            "revenue_items": revenue_items,
            "total_revenue": total_revenue,
            "expense_items": expense_items,
            "total_expenses": total_expense,
            "net_profit": net_profit
        }

    @staticmethod
    async def generate_balance_sheet(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Pillar 12.2: Fundamental Accounting Equation:
        Assets == Liabilities + Equity + Current Period Net Profit
        Discrepancy must strictly equal 0.00.
        """
        target_date = as_of_date or date.today()

        # 1. Compute P&L for current period up to as_of_date
        pnl = await FinancialReportingService.generate_profit_and_loss(session, tenant_id, to_date=target_date)
        current_net_profit = pnl["net_profit"]

        # 2. Compute Balance Sheet accounts (Asset, Liability, Equity)
        acc_stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.tenant_id == tenant_id,
            ChartOfAccounts.type.in_(["asset", "liability", "equity"]),
            ChartOfAccounts.is_active == True
        ).order_by(ChartOfAccounts.code)
        accounts = (await session.execute(acc_stmt)).scalars().all()

        asset_items = []
        liability_items = []
        equity_items = []

        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")

        for acc in accounts:
            sum_stmt = select(
                func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
                func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
            ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
                JournalLine.tenant_id == tenant_id,
                JournalLine.account_id == acc.id,
                JournalEntry.entry_date <= target_date,
                JournalEntry.status == "posted"
            )
            row = (await session.execute(sum_stmt)).one()
            d_sum = FinancialReportingService.bankers_round(row.d)
            c_sum = FinancialReportingService.bankers_round(row.c)

            if acc.type == "asset":
                # Normal balance debit; contra-assets (like Accumulated Dep) have normal balance credit
                if acc.normal_balance == "debit":
                    bal = d_sum - c_sum
                else:
                    bal = -(c_sum - d_sum) # Reduces gross assets
                if bal != Decimal("0.00"):
                    asset_items.append({"code": acc.code, "name": acc.name, "amount": bal})
                    total_assets += bal
            elif acc.type == "liability":
                bal = c_sum - d_sum
                if bal != Decimal("0.00"):
                    liability_items.append({"code": acc.code, "name": acc.name, "amount": bal})
                    total_liabilities += bal
            elif acc.type == "equity":
                bal = c_sum - d_sum
                if bal != Decimal("0.00"):
                    equity_items.append({"code": acc.code, "name": acc.name, "amount": bal})
                    total_equity += bal

        total_assets = FinancialReportingService.bankers_round(total_assets)
        total_liabilities = FinancialReportingService.bankers_round(total_liabilities)
        total_equity = FinancialReportingService.bankers_round(total_equity)

        total_equity_and_liabilities = total_liabilities + total_equity + current_net_profit
        drift = abs(total_assets - total_equity_and_liabilities)

        return {
            "tenant_id": tenant_id,
            "as_of_date": target_date,
            "asset_items": asset_items,
            "total_assets": total_assets,
            "liability_items": liability_items,
            "total_liabilities": total_liabilities,
            "equity_items": equity_items,
            "total_equity": total_equity,
            "current_period_net_profit": current_net_profit,
            "total_equity_and_liabilities": total_equity_and_liabilities,
            "drift": drift,
            "is_equation_satisfied": drift == Decimal("0.00")
        }

    @staticmethod
    async def generate_cash_flow_statement(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        cash_bank_account_code: str = "1010"
    ) -> Dict[str, Any]:
        """
        Pillar 12.3: Cash Flow Statement Direct & Indirect Reconciliation:
        Operating Activities + Investing Activities + Financing Activities = Net Change in Cash.
        Matches Ending Cash minus Beginning Cash on Balance Sheet.
        """
        target_end = to_date or date.today()

        # 1. Beginning and Ending Cash on Bank accounts
        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, cash_bank_account_code)
        if not bank_acc:
            raise ValueError(f"Cash/Bank account ({cash_bank_account_code}) not found.")

        # Beginning cash balance
        beg_conds = [
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == bank_acc.id,
            JournalEntry.status == "posted"
        ]
        if from_date:
            beg_conds.append(JournalEntry.entry_date < from_date)
        else:
            beg_conds.append(JournalEntry.entry_date < date(2000, 1, 1)) # 0 if no from_date

        beg_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(and_(*beg_conds))
        beg_row = (await session.execute(beg_stmt)).one()
        beginning_cash = FinancialReportingService.bankers_round(beg_row.d - beg_row.c)

        # Ending cash balance
        end_conds = [
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == bank_acc.id,
            JournalEntry.status == "posted",
            JournalEntry.entry_date <= target_end
        ]
        end_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(and_(*end_conds))
        end_row = (await session.execute(end_stmt)).one()
        ending_cash = FinancialReportingService.bankers_round(end_row.d - end_row.c)
        net_cash_change_actual = ending_cash - beginning_cash

        # 2. Classify cash flow legs from journal entries touching bank account
        cf_conds = [
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == bank_acc.id,
            JournalEntry.status == "posted",
            JournalEntry.entry_date <= target_end
        ]
        if from_date:
            cf_conds.append(JournalEntry.entry_date >= from_date)

        cf_lines_stmt = select(JournalLine, JournalEntry).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).where(and_(*cf_conds))
        cf_results = (await session.execute(cf_lines_stmt)).all()

        operating_cash_flow = Decimal("0.00")
        investing_cash_flow = Decimal("0.00")
        financing_cash_flow = Decimal("0.00")

        for line, entry in cf_results:
            net_movement = line.debit_amount - line.credit_amount
            ref_type = entry.reference_type or ""

            if ref_type in ["asset_capitalization", "asset_disposal"]:
                investing_cash_flow += net_movement
            elif ref_type in ["share_capital", "director_loan", "equity_infusion", "loan_borrowing"]:
                financing_cash_flow += net_movement
            else:
                # Default operating (customer payments, vendor bills, advances, tax, expenses)
                operating_cash_flow += net_movement

        computed_net_change = operating_cash_flow + investing_cash_flow + financing_cash_flow
        discrepancy = abs(computed_net_change - net_cash_change_actual)

        return {
            "tenant_id": tenant_id,
            "from_date": from_date,
            "to_date": target_end,
            "beginning_cash": beginning_cash,
            "operating_cash_flow": operating_cash_flow,
            "investing_cash_flow": investing_cash_flow,
            "financing_cash_flow": financing_cash_flow,
            "net_cash_change_computed": computed_net_change,
            "ending_cash": ending_cash,
            "net_cash_change_actual": net_cash_change_actual,
            "drift": discrepancy,
            "is_reconciled": discrepancy == Decimal("0.00")
        }
