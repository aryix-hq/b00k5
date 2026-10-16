"""
b00k5 Financial Engine: Fixed Assets, Capitalization & Depreciation Engine
Pillar 7:
- Asset Capitalization (Direct purchase + Freight + Installation)
- Depreciation Run (Written Down Value - WDV and Straight Line Method - SLM)
- Asset Disposal, Gain/Loss on Sale, and Contra-Asset Derecognition
"""

from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date, datetime
from typing import Dict, Any, Optional, List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.asset import FixedAsset, FixedAssetDepreciationRun
from app.services.ledger_service import LedgerService
from app.schemas.asset import SCHEDULE_II_USEFUL_LIFE_MAP, SCHEDULE_II_CATEGORY_NAMES
from app.core.fiscal_year import calculate_indian_fy_ay


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

    @staticmethod
    async def register_asset(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_name: str,
        category: str,
        purchase_date: date,
        gross_block: Decimal,
        capitalization_date: Optional[date] = None,
        salvage_value: Optional[Decimal] = None,
        useful_life_years: Optional[Decimal] = None,
        depreciation_method: str = "SLM",
        location: Optional[str] = None,
        serial_number: Optional[str] = None,
        auto_post_purchase_jv: bool = False,
        payment_account_code: str = "1010",
        created_by: Optional[uuid.UUID] = None
    ) -> FixedAsset:
        """
        Registers an asset in the Schedule II Fixed Asset Registry.
        Computes 5% statutory salvage value if omitted.
        Assigns official useful life from Schedule II Part C if omitted.
        Optionally posts the initial purchase/capitalization Journal Entry.
        """
        cat = category.strip().upper()
        life = useful_life_years or SCHEDULE_II_USEFUL_LIFE_MAP.get(cat, Decimal("5.0"))
        cap_dt = capitalization_date or purchase_date
        gross = FixedAssetsEngine.bankers_round(gross_block)
        salvage = salvage_value if salvage_value is not None else FixedAssetsEngine.bankers_round(gross * Decimal("0.05"))

        # Generate unique asset code
        count_stmt = select(func.count(FixedAsset.id)).where(FixedAsset.tenant_id == tenant_id)
        current_count = (await session.execute(count_stmt)).scalar() or 0
        asset_code = f"FA-{purchase_date.year}-{current_count + 1:03d}"

        purchase_jv_id = None
        if auto_post_purchase_jv:
            cap_res = await FixedAssetsEngine.capitalize_asset(
                session=session,
                tenant_id=tenant_id,
                asset_name=f"{asset_name} ({asset_code})",
                base_cost=gross,
                asset_account_code="1050",
                payable_account_code="2040",
                bank_account_code=payment_account_code,
                pay_via_bank=(payment_account_code == "1010"),
                capitalization_date=cap_dt,
                created_by=created_by
            )
            purchase_jv_id = cap_res["journal_entry_id"]

        asset = FixedAsset(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            asset_code=asset_code,
            asset_name=asset_name,
            category=cat,
            purchase_date=purchase_date,
            capitalization_date=cap_dt,
            gross_block=gross,
            salvage_value=salvage,
            useful_life_years=life,
            depreciation_method=depreciation_method.upper(),
            accumulated_depreciation=Decimal("0.00"),
            net_block=gross,
            location=location,
            serial_number=serial_number,
            status="ACTIVE",
            purchase_journal_id=purchase_jv_id
        )
        session.add(asset)
        await session.flush()
        return asset

    @staticmethod
    async def list_assets(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: Optional[str] = "ACTIVE"
    ) -> List[FixedAsset]:
        query = select(FixedAsset).where(FixedAsset.tenant_id == tenant_id)
        if status:
            query = query.where(FixedAsset.status == status.upper())
        query = query.order_by(FixedAsset.purchase_date.desc(), FixedAsset.created_at.desc())
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def execute_period_depreciation_run(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: str,
        period_start: date,
        period_end: date,
        run_date: Optional[date] = None,
        auto_post_jv: bool = True,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Executes period-end Schedule II depreciation run across all active fixed assets.
        Calculates pro-rata daily depreciation for each asset in service during [period_start, period_end].
        Ensures net block never drops below 5% salvage value.
        Posts single balanced Journal Voucher to General Ledger:
        DR 4070 Depreciation & Amortization Expense (P&L)
        CR 1059 Accumulated Depreciation - Fixed Assets (Contra Asset)
        |Sum(Dr) - Sum(Cr)| == 0.00 guaranteed!
        """
        r_dt = run_date or period_end
        assets = await FixedAssetsEngine.list_assets(session, tenant_id, status="ACTIVE")

        total_run_depreciation = Decimal("0.00")
        asset_details = []

        for asset in assets:
            # Asset must have been capitalized on or before the period end
            if asset.capitalization_date > period_end:
                continue

            # Determine days in service during this period
            eff_start = max(asset.capitalization_date, period_start)
            days_in_service = (period_end - eff_start).days + 1
            if days_in_service <= 0:
                continue

            # Check remaining depreciable capacity
            max_depreciable = max(Decimal("0.00"), asset.net_block - asset.salvage_value)
            if max_depreciable <= Decimal("0.00"):
                continue

            # Calculate period depreciation
            if asset.depreciation_method == "SLM":
                depreciable_base = asset.gross_block - asset.salvage_value
                annual_depreciation = depreciable_base / asset.useful_life_years
                period_dep = FixedAssetsEngine.bankers_round(annual_depreciation * Decimal(str(days_in_service)) / Decimal("365.0"))
            else:
                # WDV Method
                # Rate R = 1 - (Salvage / Gross)^(1 / Life)
                gross_f = float(asset.gross_block)
                salvage_f = float(asset.salvage_value) if asset.salvage_value > Decimal("0.00") else gross_f * 0.05
                life_f = float(asset.useful_life_years)
                try:
                    wdv_rate = 1.0 - (salvage_f / gross_f) ** (1.0 / life_f)
                except Exception:
                    wdv_rate = 0.40  # fallback
                annual_depreciation = asset.net_block * Decimal(str(round(wdv_rate, 4)))
                period_dep = FixedAssetsEngine.bankers_round(annual_depreciation * Decimal(str(days_in_service)) / Decimal("365.0"))

            # Restrict by max depreciable
            actual_dep = min(period_dep, max_depreciable)
            if actual_dep > Decimal("0.00"):
                total_run_depreciation += actual_dep
                new_accum = asset.accumulated_depreciation + actual_dep
                new_net = asset.gross_block - new_accum

                # Update asset record
                asset.accumulated_depreciation = new_accum
                asset.net_block = new_net

                asset_details.append({
                    "asset_id": str(asset.id),
                    "asset_code": asset.asset_code,
                    "asset_name": asset.asset_name,
                    "category": asset.category,
                    "depreciation_method": asset.depreciation_method,
                    "days_in_service": days_in_service,
                    "period_depreciation": float(actual_dep),
                    "new_accumulated_depreciation": float(new_accum),
                    "new_net_block": float(new_net)
                })

        jv_id = None
        jv_number = None
        if auto_post_jv and total_run_depreciation > Decimal("0.00"):
            # Accounts: 4070 (Depreciation Expense), 1059 (Accumulated Depreciation - Fixed Assets)
            dep_exp_acc = await LedgerService.get_account_by_code(session, tenant_id, "4070")
            accum_dep_acc = await LedgerService.get_account_by_code(session, tenant_id, "1059")

            if not dep_exp_acc:
                dep_exp_acc = ChartOfAccounts(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    code="4070",
                    name="Depreciation & Amortization Expense",
                    type="expense",
                    sub_type="depreciation",
                    normal_balance="debit"
                )
                session.add(dep_exp_acc)
                await session.flush()

            if not accum_dep_acc:
                accum_dep_acc = ChartOfAccounts(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    code="1059",
                    name="Accumulated Depreciation - Fixed Assets",
                    type="asset",
                    sub_type="fixed_asset",
                    normal_balance="credit"
                )
                session.add(accum_dep_acc)
                await session.flush()

            jv_number = f"JV-DEP-{fiscal_year.replace(' ', '')}-{uuid.uuid4().hex[:6].upper()}"
            entry = JournalEntry(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                entry_number=jv_number,
                entry_date=r_dt,
                reference_type="depreciation_run",
                narration=f"Schedule II Depreciation Run for {fiscal_year} ({period_start} to {period_end}) across {len(asset_details)} assets",
                status="posted",
                is_posted=True,
                created_by=created_by
            )
            session.add(entry)
            await session.flush()

            lines = [
                JournalLine(
                    id=uuid.uuid4(),
                    journal_entry_id=entry.id,
                    tenant_id=tenant_id,
                    account_id=dep_exp_acc.id,
                    debit_amount=total_run_depreciation,
                    credit_amount=Decimal("0.00"),
                    description=f"Depreciation expense for {fiscal_year}"
                ),
                JournalLine(
                    id=uuid.uuid4(),
                    journal_entry_id=entry.id,
                    tenant_id=tenant_id,
                    account_id=accum_dep_acc.id,
                    debit_amount=Decimal("0.00"),
                    credit_amount=total_run_depreciation,
                    description=f"Accumulated depreciation on fixed assets ({len(asset_details)} items)"
                )
            ]
            session.add_all(lines)
            await session.flush()
            jv_id = entry.id

        dep_run = FixedAssetDepreciationRun(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            period_start=period_start,
            period_end=period_end,
            run_date=r_dt,
            total_depreciation_amount=total_run_depreciation,
            journal_entry_id=jv_id,
            status="POSTED" if jv_id else "CALCULATED",
            details=asset_details
        )
        session.add(dep_run)
        await session.flush()

        return {
            "depreciation_run_id": dep_run.id,
            "fiscal_year": fiscal_year,
            "period_start": period_start,
            "period_end": period_end,
            "run_date": r_dt,
            "total_depreciation_amount": total_run_depreciation,
            "journal_entry_id": jv_id,
            "journal_entry_number": jv_number,
            "status": dep_run.status,
            "asset_count": len(asset_details),
            "details": asset_details
        }

    @staticmethod
    async def get_schedule_ii_summary(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: Optional[str] = None,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Generates category-wise Schedule II PPE Summary for statutory reporting.
        """
        ref_dt = as_of_date or date.today()
        if fiscal_year:
            fy = fiscal_year
        else:
            fy_info = calculate_indian_fy_ay(ref_dt)
            fy = f"{fy_info['fy_start_year']}-{str(fy_info['fy_end_year'])[-2:]}"

        assets = await FixedAssetsEngine.list_assets(session, tenant_id, status=None)

        category_groups: Dict[str, Dict[str, Any]] = {}
        for cat_key, cat_name in SCHEDULE_II_CATEGORY_NAMES.items():
            category_groups[cat_key] = {
                "category": cat_key,
                "name": cat_name,
                "useful_life_years": float(SCHEDULE_II_USEFUL_LIFE_MAP.get(cat_key, Decimal("5.0"))),
                "asset_count": 0,
                "gross_block": Decimal("0.00"),
                "accumulated_depreciation": Decimal("0.00"),
                "net_block": Decimal("0.00"),
            }

        total_gross = Decimal("0.00")
        total_accum = Decimal("0.00")
        total_net = Decimal("0.00")

        for asset in assets:
            cat_key = asset.category if asset.category in category_groups else "OFFICE_EQUIPMENT"
            grp = category_groups[cat_key]
            grp["asset_count"] += 1
            grp["gross_block"] += asset.gross_block
            grp["accumulated_depreciation"] += asset.accumulated_depreciation
            grp["net_block"] += asset.net_block

            total_gross += asset.gross_block
            total_accum += asset.accumulated_depreciation
            total_net += asset.net_block

        categories_list = [
            {
                "category": v["category"],
                "name": v["name"],
                "useful_life_years": v["useful_life_years"],
                "asset_count": v["asset_count"],
                "gross_block": float(v["gross_block"]),
                "accumulated_depreciation": float(v["accumulated_depreciation"]),
                "net_block": float(v["net_block"])
            }
            for v in category_groups.values() if v["asset_count"] > 0 or v["category"] in ("COMPUTERS_END_USER", "OFFICE_EQUIPMENT", "FURNITURE")
        ]

        return {
            "fiscal_year": fy,
            "as_of_date": ref_dt,
            "total_gross_block": total_gross,
            "total_accumulated_depreciation": total_accum,
            "total_net_block": total_net,
            "categories": categories_list
        }

