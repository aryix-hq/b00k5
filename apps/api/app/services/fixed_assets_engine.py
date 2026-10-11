"""
b00k5 Financial Engine: Fixed Assets, Capitalization & Depreciation Engine
Pillar 7:
- Asset Capitalization (Direct purchase + Freight + Installation)
- Depreciation Run (Written Down Value - WDV and Straight Line Method - SLM)
- Asset Disposal, Gain/Loss on Sale, and Contra-Asset Derecognition
"""

from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date
from typing import Dict, Any, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.ledger_service import LedgerService


class FixedAssetsEngine:
    @staticmethod
    def bankers_round(value: Decimal, places: int = 2) -> Decimal:
        quant = Decimal('10') ** -places
        return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_EVEN)

    @staticmethod
    async def capitalize_asset(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_name: str,
        base_cost: Decimal,
        installation_charges: Decimal = Decimal("0.00"),
        freight_charges: Decimal = Decimal("0.00"),
        asset_account_code: str = "1050", # Computer & IT Hardware (Fixed Asset)
        payable_account_code: str = "2040", # Trade Payables / Vendor AP
        bank_account_code: str = "1010",
        pay_via_bank: bool = False,
        capitalization_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Pillar 7.1: Capitalization of Acquisition Cost:
        Base cost + installation + freight are all capitalized into Gross Asset Block.
        None are expensed to P&L.
        DR 1050 Fixed Asset (Gross Block) = Base + Installation + Freight
        CR 2040 Trade Payables / 1010 Bank = Total Amount
        """
        cap_dt = capitalization_date or date.today()
        base = FixedAssetsEngine.bankers_round(base_cost)
        inst = FixedAssetsEngine.bankers_round(installation_charges)
        frt = FixedAssetsEngine.bankers_round(freight_charges)
        total_capitalized = base + inst + frt

        asset_acc = await LedgerService.get_account_by_code(session, tenant_id, asset_account_code)
        credit_acc_code = bank_account_code if pay_via_bank else payable_account_code
        credit_acc = await LedgerService.get_account_by_code(session, tenant_id, credit_acc_code)

        if not (asset_acc and credit_acc):
            raise ValueError(f"Required accounts ({asset_account_code} or {credit_acc_code}) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-CAP-{uuid.uuid4().hex[:6]}",
            entry_date=cap_dt,
            reference_type="asset_capitalization",
            narration=f"Capitalization of {asset_name} (Cost: {base}, Inst: {inst}, Freight: {frt})",
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
                account_id=asset_acc.id,
                debit_amount=total_capitalized,
                credit_amount=Decimal("0.00"),
                description=f"Gross block acquisition: {asset_name}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=credit_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=total_capitalized,
                description=f"Liability/Payment for acquisition of {asset_name}"
            )
        ]
        session.add_all(lines)
        await session.flush()

        return {
            "journal_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "total_capitalized": total_capitalized,
            "base_cost": base,
            "installation": inst,
            "freight": frt
        }

    @staticmethod
    async def run_depreciation_wdv(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_name: str,
        gross_cost: Decimal,
        prior_accumulated_dep: Decimal,
        annual_wdv_rate_percent: Decimal,
        period_months: int = 1,
        expense_account_code: str = "4040", # or 5020 Depreciation Expense
        accumulated_dep_code: str = "1029", # Contra-Asset
        run_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Pillar 7.2: Written Down Value (WDV) Depreciation Run:
        Current WDV = Gross Cost - Prior Accumulated Depreciation
        Depreciation = Current WDV * (Annual Rate / 100) * (Period Months / 12)
        DR Depreciation Expense (P&L)
        CR Accumulated Depreciation (Contra-Asset)
        NBV = Gross Cost - (Prior Accumulated + Current Depreciation)
        """
        r_dt = run_date or date.today()
        gross = FixedAssetsEngine.bankers_round(gross_cost)
        prior_dep = FixedAssetsEngine.bankers_round(prior_accumulated_dep)
        opening_wdv = gross - prior_dep

        if opening_wdv < Decimal("0.00"):
            opening_wdv = Decimal("0.00")

        annual_rate = annual_wdv_rate_percent / Decimal("100.00")
        period_fraction = Decimal(str(period_months)) / Decimal("12.00")
        dep_amount = FixedAssetsEngine.bankers_round(opening_wdv * annual_rate * period_fraction)

        # Do not depreciate below salvage value of 5%
        salvage_min = FixedAssetsEngine.bankers_round(gross * Decimal("0.05"))
        if (opening_wdv - dep_amount) < salvage_min:
            dep_amount = max(Decimal("0.00"), opening_wdv - salvage_min)

        new_accumulated = prior_dep + dep_amount
        net_book_value = gross - new_accumulated

        dep_acc = await LedgerService.get_account_by_code(session, tenant_id, expense_account_code)
        accum_acc = await LedgerService.get_account_by_code(session, tenant_id, accumulated_dep_code)

        if not (dep_acc and accum_acc):
            raise ValueError(f"Required accounts ({expense_account_code} or {accumulated_dep_code}) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-DEP-{uuid.uuid4().hex[:6]}",
            entry_date=r_dt,
            reference_type="depreciation_run",
            narration=f"WDV Depreciation for {asset_name} ({period_months} months @ {annual_wdv_rate_percent}%)",
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
                account_id=dep_acc.id,
                debit_amount=dep_amount,
                credit_amount=Decimal("0.00"),
                description=f"Depreciation expense: {asset_name}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=accum_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=dep_amount,
                description=f"Accumulated depreciation contra-asset: {asset_name}"
            )
        ]
        session.add_all(lines)
        await session.flush()

        return {
            "journal_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "opening_wdv": opening_wdv,
            "depreciation_amount": dep_amount,
            "new_accumulated_depreciation": new_accumulated,
            "net_book_value": net_book_value
        }

    @staticmethod
    async def dispose_fixed_asset(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_name: str,
        gross_cost: Decimal,
        accumulated_dep: Decimal,
        sale_proceeds: Decimal,
        asset_account_code: str = "1050",
        accumulated_dep_code: str = "1029",
        bank_account_code: str = "1010",
        profit_account_code: str = "3030", # Profit on Sale / Other Income
        loss_account_code: str = "4040",   # Loss on Sale of Asset / Expense
        disposal_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Pillar 7.3: Asset Disposal & Gain/Loss Calculation:
        Cost ₹100,000, Accumulated Depreciation ₹60,000 -> NBV = ₹40,000.
        Sold for ₹48,000 -> Profit = ₹8,000.
        DR 1010 Bank                      = ₹48,000 (Proceeds)
        DR 1029 Accumulated Depreciation  = ₹60,000 (Clear Contra-Asset)
        CR 1050 Fixed Asset Gross Cost    = ₹100,000 (Derecognize Gross Block)
        CR 3030 Profit on Sale of Asset   = ₹8,000 (Recognize P&L Gain)
        Total Debits (₹108,000) == Total Credits (₹108,000).
        """
        d_dt = disposal_date or date.today()
        cost = FixedAssetsEngine.bankers_round(gross_cost)
        acc_dep = FixedAssetsEngine.bankers_round(accumulated_dep)
        proceeds = FixedAssetsEngine.bankers_round(sale_proceeds)
        nbv = cost - acc_dep
        gain_or_loss = proceeds - nbv # positive = profit, negative = loss

        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, bank_account_code)
        accum_acc = await LedgerService.get_account_by_code(session, tenant_id, accumulated_dep_code)
        asset_acc = await LedgerService.get_account_by_code(session, tenant_id, asset_account_code)
        profit_acc = await LedgerService.get_account_by_code(session, tenant_id, profit_account_code)
        loss_acc = await LedgerService.get_account_by_code(session, tenant_id, loss_account_code)

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-DISP-{uuid.uuid4().hex[:6]}",
            entry_date=d_dt,
            reference_type="asset_disposal",
            narration=f"Disposal of {asset_name} for proceeds of {proceeds}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = []
        # 1. DR Bank (Proceeds received)
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=bank_acc.id,
            debit_amount=proceeds,
            credit_amount=Decimal("0.00"),
            description=f"Disposal proceeds from {asset_name}"
        ))

        # 2. DR Accumulated Depreciation (Derecognize contra-asset)
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=accum_acc.id,
            debit_amount=acc_dep,
            credit_amount=Decimal("0.00"),
            description=f"Accumulated depreciation derecognition for {asset_name}"
        ))

        # 3. CR Fixed Asset Cost (Derecognize gross asset cost)
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=asset_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=cost,
            description=f"Derecognition of gross block: {asset_name}"
        ))

        # 4. Gain or Loss
        if gain_or_loss > Decimal("0.00"):
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=profit_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=gain_or_loss,
                description=f"Net gain on sale of {asset_name}"
            ))
        elif gain_or_loss < Decimal("0.00"):
            loss_val = abs(gain_or_loss)
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=loss_acc.id,
                debit_amount=loss_val,
                credit_amount=Decimal("0.00"),
                description=f"Net loss on sale of {asset_name}"
            ))

        total_deb = sum(l.debit_amount for l in lines)
        total_crd = sum(l.credit_amount for l in lines)
        if total_deb != total_crd:
            raise ValueError(f"Imbalanced disposal entry: {total_deb} vs {total_crd}")

        session.add_all(lines)
        await session.flush()

        return {
            "journal_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "net_book_value": nbv,
            "gain_or_loss": gain_or_loss,
            "total_debits": total_deb,
            "total_credits": total_crd
        }
