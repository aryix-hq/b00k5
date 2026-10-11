"""
b00k5 Financial Engine: Multi-Currency & Realized/Unrealized FX Gain/Loss Engine
Pillar 9 (IAS 21 / Ind AS 21 / AS 11):
- Realized FX Gain/Loss on Settlement of Foreign Currency Invoices
- Unrealized Balance Sheet Revaluation of Monetary Assets/Liabilities at Period-End Spot Rates
"""

from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date
from typing import Dict, Any, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService


class MultiCurrencyEngine:
    @staticmethod
    def bankers_round(value: Decimal, places: int = 2) -> Decimal:
        quant = Decimal('10') ** -places
        return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_EVEN)

    @staticmethod
    async def settle_foreign_invoice(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        invoice_number: str,
        foreign_amount: Decimal,
        booking_exchange_rate: Decimal,
        settlement_exchange_rate: Decimal,
        bank_account_code: str = "1010",
        ar_account_code: str = "1020",
        fx_gain_account_code: str = "3030", # Realized FX Gain (Other Operating Income / Revenue)
        fx_loss_account_code: str = "4040", # Realized FX Loss (Expense)
        settlement_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Pillar 9.1: Realized Foreign Exchange Gain/Loss on Settlement:
        Example:
        $1,000 USD booked @ 83.00 = Booked AR ₹83,000
        $1,000 USD settled @ 84.50 = Received ₹84,500
        Realized Gain = ₹1,500
        DR 1010 Bank (INR)              = ₹84,500
        CR 1020 Accounts Receivable     = ₹83,000
        CR 3030 Realized FX Gain (P&L)  = ₹1,500
        Total Debits (₹84,500) == Total Credits (₹84,500)
        """
        s_dt = settlement_date or date.today()
        f_amt = Decimal(str(foreign_amount))
        book_rate = Decimal(str(booking_exchange_rate))
        settle_rate = Decimal(str(settlement_exchange_rate))

        booked_inr = MultiCurrencyEngine.bankers_round(f_amt * book_rate)
        settled_inr = MultiCurrencyEngine.bankers_round(f_amt * settle_rate)
        fx_difference = settled_inr - booked_inr # positive = gain, negative = loss

        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, bank_account_code)
        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, ar_account_code)
        gain_acc = await LedgerService.get_account_by_code(session, tenant_id, fx_gain_account_code)
        loss_acc = await LedgerService.get_account_by_code(session, tenant_id, fx_loss_account_code)

        if not (bank_acc and ar_acc):
            raise ValueError("Required accounts (Bank or AR) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-FX-SETTLE-{invoice_number}-{uuid.uuid4().hex[:6]}",
            entry_date=s_dt,
            reference_type="fx_settlement",
            narration=f"Settlement of Inv #{invoice_number} ({f_amt} USD @ {settle_rate} vs Booked @ {book_rate})",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            # 1. DR Bank (Actual INR received)
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=bank_acc.id,
                debit_amount=settled_inr,
                credit_amount=Decimal("0.00"),
                description=f"Inflow for foreign settlement of Inv #{invoice_number}"
            ),
            # 2. CR AR (Clear originally booked AR balance)
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=ar_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=booked_inr,
                description=f"AR derecognition for Inv #{invoice_number}"
            )
        ]

        # 3. FX Gain or Loss
        if fx_difference > Decimal("0.00"):
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=gain_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=fx_difference,
                description=f"Realized foreign exchange gain on Inv #{invoice_number}"
            ))
        elif fx_difference < Decimal("0.00"):
            loss_val = abs(fx_difference)
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=loss_acc.id,
                debit_amount=loss_val,
                credit_amount=Decimal("0.00"),
                description=f"Realized foreign exchange loss on Inv #{invoice_number}"
            ))

        total_deb = sum(l.debit_amount for l in lines)
        total_crd = sum(l.credit_amount for l in lines)
        if total_deb != total_crd:
            raise ValueError(f"Imbalanced FX settlement entry: {total_deb} vs {total_crd}")

        session.add_all(lines)
        await session.flush()

        return {
            "journal_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "booked_inr": booked_inr,
            "settled_inr": settled_inr,
            "fx_difference": fx_difference,
            "is_gain": fx_difference > Decimal("0.00"),
            "total_debits": total_deb,
            "total_credits": total_crd
        }

    @staticmethod
    async def revalue_foreign_monetary_asset(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        account_name: str,
        foreign_currency_units: Decimal,
        current_book_value_inr: Decimal,
        closing_spot_exchange_rate: Decimal,
        monetary_account_code: str = "1010",
        unrealized_gain_account_code: str = "3030",
        unrealized_loss_account_code: str = "4040",
        revaluation_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Pillar 9.2: Period-End Unrealized Balance Sheet Revaluation:
        Example:
        Hold $5,000 USD in foreign account. Current Book Value = ₹415,000 ($1 = ₹83.00).
        Year-end closing spot rate is $1 = ₹82.00 (Fair Value = ₹410,000).
        Unrealized FX Loss = ₹5,000.
        DR 4040 Unrealized FX Loss (P&L)          = ₹5,000
        CR 1010 Bank Account (Foreign Currency)   = ₹5,000
        """
        r_dt = revaluation_date or date.today()
        f_units = Decimal(str(foreign_currency_units))
        book_val = MultiCurrencyEngine.bankers_round(current_book_value_inr)
        spot_rate = Decimal(str(closing_spot_exchange_rate))
        fair_val = MultiCurrencyEngine.bankers_round(f_units * spot_rate)
        diff = fair_val - book_val # positive = gain, negative = loss

        monetary_acc = await LedgerService.get_account_by_code(session, tenant_id, monetary_account_code)
        gain_acc = await LedgerService.get_account_by_code(session, tenant_id, unrealized_gain_account_code)
        loss_acc = await LedgerService.get_account_by_code(session, tenant_id, unrealized_loss_account_code)

        if not monetary_acc:
            raise ValueError(f"Monetary account ({monetary_account_code}) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-FX-REVAL-{uuid.uuid4().hex[:6]}",
            entry_date=r_dt,
            reference_type="unrealized_fx_revaluation",
            narration=f"Period-end FX revaluation of {account_name} ({f_units} units @ {spot_rate} vs Book {book_val})",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = []
        if diff > Decimal("0.00"):
            # Asset value appreciated: DR Asset, CR Unrealized Gain
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=monetary_acc.id,
                debit_amount=diff,
                credit_amount=Decimal("0.00"),
                description=f"Mark-to-market upward revaluation: {account_name}"
            ))
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=gain_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=diff,
                description=f"Unrealized FX Gain recognized in P&L: {account_name}"
            ))
        elif diff < Decimal("0.00"):
            # Asset value depreciated: DR Unrealized Loss, CR Asset
            loss_val = abs(diff)
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=loss_acc.id,
                debit_amount=loss_val,
                credit_amount=Decimal("0.00"),
                description=f"Unrealized FX Loss recognized in P&L: {account_name}"
            ))
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=monetary_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=loss_val,
                description=f"Mark-to-market downward revaluation: {account_name}"
            ))

        total_deb = sum(l.debit_amount for l in lines)
        total_crd = sum(l.credit_amount for l in lines)
        if total_deb != total_crd:
            raise ValueError(f"Imbalanced FX revaluation entry: {total_deb} vs {total_crd}")

        session.add_all(lines)
        await session.flush()

        return {
            "journal_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "foreign_units": f_units,
            "book_value": book_val,
            "fair_value": fair_val,
            "unrealized_difference": diff,
            "is_gain": diff > Decimal("0.00"),
            "total_debits": total_deb,
            "total_credits": total_crd
        }
