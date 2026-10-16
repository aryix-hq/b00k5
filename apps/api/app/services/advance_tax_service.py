import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.invoice import Invoice
from app.models.compliance import AdvanceTaxForecast, AdvanceTaxChallan


class AdvanceTaxService:
    """
    Direct Tax Advance Tax Forecasting & Penal Interest Watchdog Engine.
    Implements Sections 208, 211, 234B, and 234C of the Income-tax Act, 1961.
    """

    @staticmethod
    def parse_fy_dates(fy: str) -> tuple[date, date, str]:
        """Parses standard Indian FY notation (e.g. '2026-27') into start, end dates and AY."""
        parts = fy.split('-')
        start_yr = int(parts[0])
        end_yr = start_yr + 1 if len(parts[1]) == 2 else int(parts[1])
        start_date = date(start_yr, 4, 1)
        end_date = date(end_yr, 3, 31)
        ay = f"{end_yr}-{str(end_yr+1)[-2:]}"
        return start_date, end_date, ay

    @staticmethod
    def calculate_corporate_tax_breakdown(
        entity_type: str,
        projected_profit: Decimal,
        annualized_turnover: Decimal,
        selected_regime: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dynamically calculates corporate or LLP income tax liability under the Income-tax Act, 1961.
        Evaluates turnover threshold (<= 400 Cr vs > 400 Cr), profit slab surcharges (7%/12%), and Section 115BAA.
        """
        clean_entity = entity_type.upper()
        is_llp = "LLP" in clean_entity or "LIMITED LIABILITY PARTNERSHIP" in clean_entity

        cess_pct = Decimal("4.00") # Health and Education Cess under Finance Act

        if is_llp:
            regime_code = "llp_30"
            regime_name = "LLP / Partnership Firm (Flat 30% + Surcharge)"
            base_rate = Decimal("30.00")
            turnover_slab = "Turnover Threshold N/A (Flat Partnership Rate)"
            
            # Surcharge: 12% if total income > ₹1 Crore
            one_crore = Decimal("10000000.00")
            if projected_profit > one_crore:
                surcharge_pct = Decimal("12.00")
                statutory_notes = "Flat 30% base rate + 12% surcharge on income exceeding ₹1 Crore + 4% HEC = 34.944% effective."
            else:
                surcharge_pct = Decimal("0.00")
                statutory_notes = "Flat 30% base rate + 0% surcharge (income <= ₹1 Crore) + 4% HEC = 31.20% effective."

            base_tax = (projected_profit * (base_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            surcharge_amt = (base_tax * (surcharge_pct / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            tax_plus_surcharge = base_tax + surcharge_amt
            cess_amt = (tax_plus_surcharge * (cess_pct / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            total_tax = tax_plus_surcharge + cess_amt
            effective_rate = (Decimal("30.00") * (Decimal("1.00") + (surcharge_pct / Decimal("100.00"))) * Decimal("1.04")).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)

            return {
                "entity_category": "LLP",
                "regime_code": regime_code,
                "regime_name": regime_name,
                "base_rate_pct": float(base_rate),
                "turnover_slab": turnover_slab,
                "surcharge_pct": float(surcharge_pct),
                "cess_pct": float(cess_pct),
                "effective_rate_pct": float(effective_rate),
                "base_tax_amount": float(base_tax),
                "surcharge_amount": float(surcharge_amt),
                "cess_amount": float(cess_amt),
                "gross_tax_amount": float(total_tax),
                "statutory_reference": "Finance Act / Income-tax Act, 1961 - Partnership Firm Rate",
                "notes": statutory_notes
            }

        # Domestic Company (Private Limited / OPC / Public Limited)
        regime = (selected_regime or "sec_115baa").lower().strip()
        if regime in ["old_regime", "normal", "old", "sec_115ba"]:
            regime_code = "old_regime"
            regime_name = "Old Regime / Normal Corporate Provisions (Sec 115BA / Finance Act)"

            # Turnover Threshold: <= 400 Cr -> 25%, > 400 Cr -> 30%
            four_hundred_cr = Decimal("4000000000.00")
            if annualized_turnover > four_hundred_cr:
                base_rate = Decimal("30.00")
                turnover_slab = "Turnover > ₹400 Crores (Base Rate 30%)"
            else:
                base_rate = Decimal("25.00")
                turnover_slab = "Turnover <= ₹400 Crores (Base Rate 25%)"

            # Surcharge slabs for Domestic Company:
            # Income <= 1 Cr: 0%
            # 1 Cr < Income <= 10 Cr: 7%
            # Income > 10 Cr: 12%
            one_cr = Decimal("10000000.00")
            ten_cr = Decimal("100000000.00")
            if projected_profit > ten_cr:
                surcharge_pct = Decimal("12.00")
                profit_bracket = "Total Income > ₹10 Crores (12% surcharge)"
            elif projected_profit > one_cr:
                surcharge_pct = Decimal("7.00")
                profit_bracket = "Total Income ₹1 Cr - ₹10 Cr (7% surcharge)"
            else:
                surcharge_pct = Decimal("0.00")
                profit_bracket = "Total Income <= ₹1 Crore (0% surcharge)"

            base_tax = (projected_profit * (base_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            surcharge_amt = (base_tax * (surcharge_pct / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            tax_plus_surcharge = base_tax + surcharge_amt
            cess_amt = (tax_plus_surcharge * (cess_pct / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            total_tax = tax_plus_surcharge + cess_amt
            effective_rate = (base_rate * (Decimal("1.00") + (surcharge_pct / Decimal("100.00"))) * Decimal("1.04")).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)

            statutory_notes = (
                f"Normal Provisions: Base Rate {base_rate}% ({turnover_slab}) + {surcharge_pct}% surcharge ({profit_bracket}) + 4% HEC."
            )

            return {
                "entity_category": "Company",
                "regime_code": regime_code,
                "regime_name": regime_name,
                "base_rate_pct": float(base_rate),
                "turnover_slab": turnover_slab,
                "surcharge_pct": float(surcharge_pct),
                "cess_pct": float(cess_pct),
                "effective_rate_pct": float(effective_rate),
                "base_tax_amount": float(base_tax),
                "surcharge_amount": float(surcharge_amt),
                "cess_amount": float(cess_amt),
                "gross_tax_amount": float(total_tax),
                "statutory_reference": "Section 115BA & Finance Act (Normal Corporate Tax)",
                "notes": statutory_notes
            }
        else:
            # Default / Selected: Section 115BAA New Concessional Regime
            regime_code = "sec_115baa_22"
            regime_name = "Section 115BAA Concessional Corporate Regime"
            base_rate = Decimal("22.00")
            turnover_slab = "Turnover Threshold N/A (Eligible for all domestic companies)"
            surcharge_pct = Decimal("10.00") # Flat 10% under Section 115BAA
            
            base_tax = (projected_profit * (base_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            surcharge_amt = (base_tax * (surcharge_pct / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            tax_plus_surcharge = base_tax + surcharge_amt
            cess_amt = (tax_plus_surcharge * (cess_pct / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            total_tax = tax_plus_surcharge + cess_amt
            effective_rate = Decimal("25.168")

            statutory_notes = (
                "Section 115BAA: Base rate 22% + mandatory 10% surcharge + 4% HEC = 25.168% effective. "
                "Exempt from Section 115JB Minimum Alternate Tax (MAT)."
            )

            return {
                "entity_category": "Company",
                "regime_code": regime_code,
                "regime_name": regime_name,
                "base_rate_pct": float(base_rate),
                "turnover_slab": turnover_slab,
                "surcharge_pct": float(surcharge_pct),
                "cess_pct": float(cess_pct),
                "effective_rate_pct": float(effective_rate),
                "base_tax_amount": float(base_tax),
                "surcharge_amount": float(surcharge_amt),
                "cess_amount": float(cess_amt),
                "gross_tax_amount": float(total_tax),
                "statutory_reference": "Section 115BAA Income-tax Act, 1961",
                "notes": statutory_notes
            }

    @staticmethod
    async def compute_advance_tax_forecast(
        db: AsyncSession,
        tenant: Tenant,
        fiscal_year: str,
        custom_projected_profit: Optional[Decimal] = None,
        selected_regime: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates real-time YTD performance, projects annual tax liability,
        evaluates quarterly Section 211 thresholds, and simulates Section 234C/234B interest.
        """
        start_date, end_date, ay = AdvanceTaxService.parse_fy_dates(fiscal_year)
        today = date.today()
        calc_date = today if start_date <= today <= end_date else end_date

        # 1. Compute Live YTD Operating Revenue (Class 3000-3999)
        stmt_rev = (
            select(func.coalesce(func.sum(JournalLine.credit_amount - JournalLine.debit_amount), Decimal("0.00")))
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(ChartOfAccounts, JournalLine.account_id == ChartOfAccounts.id)
            .where(
                JournalLine.tenant_id == tenant.id,
                JournalEntry.entry_date.between(start_date, calc_date),
                JournalEntry.status == "posted",
                ChartOfAccounts.type == "revenue"
            )
        )
        res_rev = await db.execute(stmt_rev)
        ytd_revenue = res_rev.scalar_one()

        # 2. Compute Live YTD Deductible Operating Expenses (Class 4000-4999)
        stmt_exp = (
            select(func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00")))
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(ChartOfAccounts, JournalLine.account_id == ChartOfAccounts.id)
            .where(
                JournalLine.tenant_id == tenant.id,
                JournalEntry.entry_date.between(start_date, calc_date),
                JournalEntry.status == "posted",
                ChartOfAccounts.type == "expense"
            )
        )
        res_exp = await db.execute(stmt_exp)
        ytd_expenses = res_exp.scalar_one()

        ytd_net_profit = ytd_revenue - ytd_expenses

        # 3. Project Annual Profit
        elapsed_days = max(1, (calc_date - start_date).days)
        if custom_projected_profit is not None:
            projected_profit = custom_projected_profit
        elif elapsed_days >= 30 and ytd_net_profit > 0:
            # Annualized run-rate
            projected_profit = (ytd_net_profit * Decimal(365) / Decimal(elapsed_days)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        else:
            projected_profit = max(Decimal("0.00"), ytd_net_profit)

        # 4. Determine Corporate / LLP Tax Regime & Effective Rate dynamically
        legal_name = (tenant.legal_name or "").upper()
        prof = tenant.statutory_profile or {}
        raw_entity = (prof.get("entity_type") or "").upper()
        if not raw_entity:
            raw_entity = "LLP" if ("LLP" in legal_name or "LIMITED LIABILITY PARTNERSHIP" in legal_name) else "PVT_LTD"

        regime_pref = selected_regime or prof.get("tax_regime")
        tax_calc = AdvanceTaxService.calculate_corporate_tax_breakdown(
            entity_type=raw_entity,
            projected_profit=projected_profit,
            annualized_turnover=ytd_revenue,
            selected_regime=regime_pref
        )

        tax_regime = tax_calc["regime_code"]
        effective_rate = Decimal(str(tax_calc["effective_rate_pct"]))
        gross_tax = Decimal(str(tax_calc["gross_tax_amount"])) if projected_profit > 0 else Decimal("0.00")

        # 5. Extract Client TDS Credits Claimed (Form 26AS Parity)
        stmt_tds = (
            select(func.coalesce(func.sum(Invoice.tds_amount), Decimal("0.00")))
            .where(
                Invoice.tenant_id == tenant.id,
                Invoice.issue_date.between(start_date, end_date),
                Invoice.status.notin_(["draft", "cancelled"])
            )
        )
        res_tds = await db.execute(stmt_tds)
        total_tds_credits = res_tds.scalar_one()

        net_advance_tax = max(Decimal("0.00"), (gross_tax - total_tds_credits).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
        is_sec208_mandatory = net_advance_tax >= Decimal("10000.00")

        # 6. Compute Section 211 Statutory Installments
        q1_target = (net_advance_tax * Decimal("0.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        q2_target = (net_advance_tax * Decimal("0.45")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        q3_target = (net_advance_tax * Decimal("0.75")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        q4_target = net_advance_tax

        # 7. Query Actual Paid Challans from advance_tax_challans
        stmt_challans = (
            select(AdvanceTaxChallan)
            .where(
                AdvanceTaxChallan.tenant_id == tenant.id,
                AdvanceTaxChallan.fiscal_year == fiscal_year
            )
        )
        res_challans = await db.execute(stmt_challans)
        challans = list(res_challans.scalars().all())

        q1_paid = sum((c.amount_paid for c in challans if c.quarter == "Q1"), Decimal("0.00"))
        q2_paid = sum((c.amount_paid for c in challans if c.quarter == "Q2"), Decimal("0.00"))
        q3_paid = sum((c.amount_paid for c in challans if c.quarter == "Q3"), Decimal("0.00"))
        q4_paid = sum((c.amount_paid for c in challans if c.quarter == "Q4"), Decimal("0.00"))

        cum_paid_q1 = q1_paid
        cum_paid_q2 = q1_paid + q2_paid
        cum_paid_q3 = q1_paid + q2_paid + q3_paid
        cum_paid_q4 = q1_paid + q2_paid + q3_paid + q4_paid

        # 8. Section 234C Deferral Interest Simulation
        # Due dates
        q1_due_date = date(start_date.year, 6, 15)
        q2_due_date = date(start_date.year, 9, 15)
        q3_due_date = date(start_date.year, 12, 15)
        q4_due_date = date(end_date.year, 3, 15)

        penal_interest_234c = Decimal("0.00")
        shortfalls = {}

        if is_sec208_mandatory:
            # Q1 check (Safe harbor: >= 12% incurs zero interest)
            q1_safe_harbor = (net_advance_tax * Decimal("0.12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            if calc_date > q1_due_date and cum_paid_q1 < q1_safe_harbor:
                sf_q1 = q1_target - cum_paid_q1
                shortfalls["Q1"] = sf_q1
                penal_interest_234c += (sf_q1 * Decimal("0.01") * Decimal(3)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

            # Q2 check (Safe harbor: >= 36% incurs zero interest)
            q2_safe_harbor = (net_advance_tax * Decimal("0.36")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            if calc_date > q2_due_date and cum_paid_q2 < q2_safe_harbor:
                sf_q2 = q2_target - cum_paid_q2
                shortfalls["Q2"] = sf_q2
                penal_interest_234c += (sf_q2 * Decimal("0.01") * Decimal(3)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

            # Q3 check (Strict 75%)
            if calc_date > q3_due_date and cum_paid_q3 < q3_target:
                sf_q3 = q3_target - cum_paid_q3
                shortfalls["Q3"] = sf_q3
                penal_interest_234c += (sf_q3 * Decimal("0.01") * Decimal(3)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

            # Q4 check (Strict 100%)
            if calc_date > q4_due_date and cum_paid_q4 < q4_target:
                sf_q4 = q4_target - cum_paid_q4
                shortfalls["Q4"] = sf_q4
                penal_interest_234c += (sf_q4 * Decimal("0.01") * Decimal(1)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

        # 9. Section 234B Default Interest Simulation (If after March 31 paid < 90%)
        penal_interest_234b = Decimal("0.00")
        if is_sec208_mandatory and calc_date >= end_date:
            ninety_percent_target = (net_advance_tax * Decimal("0.90")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            if cum_paid_q4 < ninety_percent_target:
                b_shortfall = net_advance_tax - cum_paid_q4
                # Simulating 1 month interest from April 1
                penal_interest_234b = (b_shortfall * Decimal("0.01")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

        # Next upcoming installment determination
        if calc_date <= q1_due_date:
            next_inst = {"quarter": "Q1", "due_date": q1_due_date.isoformat(), "target_amount": float(q1_target), "payable_now": float(max(Decimal("0.00"), q1_target - cum_paid_q1))}
        elif calc_date <= q2_due_date:
            next_inst = {"quarter": "Q2", "due_date": q2_due_date.isoformat(), "target_amount": float(q2_target), "payable_now": float(max(Decimal("0.00"), q2_target - cum_paid_q2))}
        elif calc_date <= q3_due_date:
            next_inst = {"quarter": "Q3", "due_date": q3_due_date.isoformat(), "target_amount": float(q3_target), "payable_now": float(max(Decimal("0.00"), q3_target - cum_paid_q3))}
        else:
            next_inst = {"quarter": "Q4", "due_date": q4_due_date.isoformat(), "target_amount": float(q4_target), "payable_now": float(max(Decimal("0.00"), q4_target - cum_paid_q4))}

        # 10. Persist Snapshot into advance_tax_forecasts
        forecast_rec = AdvanceTaxForecast(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            fiscal_year=fiscal_year,
            assessment_year=ay,
            calculation_date=calc_date,
            tax_regime=tax_regime,
            ytd_revenue=ytd_revenue,
            ytd_expenses=ytd_expenses,
            ytd_net_profit=ytd_net_profit,
            projected_annual_profit=projected_profit,
            effective_tax_rate=effective_rate,
            gross_projected_tax=gross_tax,
            tds_tcs_credits_claimed=total_tds_credits,
            net_advance_tax_payable=net_advance_tax,
            q1_due=q1_target,
            q2_due=q2_target,
            q3_due=q3_target,
            q4_due=q4_target,
            q1_paid=q1_paid,
            q2_paid=q2_paid,
            q3_paid=q3_paid,
            q4_paid=q4_paid,
            interest_234c_projected=penal_interest_234c,
            interest_234b_projected=penal_interest_234b
        )
        db.add(forecast_rec)
        await db.commit()

        # Monthly recommended reserve to make upcoming installment painless
        rem_payable = next_inst["payable_now"]
        monthly_reserve = (Decimal(str(rem_payable)) / Decimal(3)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) if rem_payable > 0 else Decimal("0.00")

        return {
            "tenant_id": str(tenant.id),
            "fiscal_year": fiscal_year,
            "assessment_year": ay,
            "calculation_date": calc_date.isoformat(),
            "tax_regime": tax_regime,
            "effective_tax_rate_percent": float(effective_rate),
            "tax_breakdown": tax_calc,
            "ytd_metrics": {
                "operating_revenue": float(ytd_revenue),
                "operating_expenses": float(ytd_expenses),
                "net_profit": float(ytd_net_profit),
                "elapsed_calendar_days": elapsed_days
            },
            "annual_projection": {
                "projected_net_taxable_income": float(projected_profit),
                "gross_tax_liability": float(gross_tax),
                "tds_credits_claimed": float(total_tds_credits),
                "net_advance_tax_payable": float(net_advance_tax),
                "is_sec208_mandatory": is_sec208_mandatory,
                "statutory_threshold_rule": "Section 208 mandates Advance Tax when net liability exceeds ₹10,000."
            },
            "installments": [
                {
                    "quarter": "Q1",
                    "due_date": q1_due_date.isoformat(),
                    "cumulative_percent": 15,
                    "target_amount": float(q1_target),
                    "safe_harbor_amount": float((net_advance_tax * Decimal("0.12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)),
                    "paid_in_quarter": float(q1_paid),
                    "cumulative_paid": float(cum_paid_q1),
                    "is_compliant": cum_paid_q1 >= (net_advance_tax * Decimal("0.12")) or calc_date <= q1_due_date,
                    "shortfall": float(shortfalls.get("Q1", Decimal("0.00")))
                },
                {
                    "quarter": "Q2",
                    "due_date": q2_due_date.isoformat(),
                    "cumulative_percent": 45,
                    "target_amount": float(q2_target),
                    "safe_harbor_amount": float((net_advance_tax * Decimal("0.36")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)),
                    "paid_in_quarter": float(q2_paid),
                    "cumulative_paid": float(cum_paid_q2),
                    "is_compliant": cum_paid_q2 >= (net_advance_tax * Decimal("0.36")) or calc_date <= q2_due_date,
                    "shortfall": float(shortfalls.get("Q2", Decimal("0.00")))
                },
                {
                    "quarter": "Q3",
                    "due_date": q3_due_date.isoformat(),
                    "cumulative_percent": 75,
                    "target_amount": float(q3_target),
                    "safe_harbor_amount": float(q3_target),
                    "paid_in_quarter": float(q3_paid),
                    "cumulative_paid": float(cum_paid_q3),
                    "is_compliant": cum_paid_q3 >= q3_target or calc_date <= q3_due_date,
                    "shortfall": float(shortfalls.get("Q3", Decimal("0.00")))
                },
                {
                    "quarter": "Q4",
                    "due_date": q4_due_date.isoformat(),
                    "cumulative_percent": 100,
                    "target_amount": float(q4_target),
                    "safe_harbor_amount": float(q4_target),
                    "paid_in_quarter": float(q4_paid),
                    "cumulative_paid": float(cum_paid_q4),
                    "is_compliant": cum_paid_q4 >= q4_target or calc_date <= q4_due_date,
                    "shortfall": float(shortfalls.get("Q4", Decimal("0.00")))
                }
            ],
            "next_action": {
                **next_inst,
                "recommended_monthly_savings_reserve": float(monthly_reserve)
            },
            "penal_interest_simulation": {
                "section_234c_deferral_interest": float(penal_interest_234c),
                "section_234b_default_interest": float(penal_interest_234b),
                "total_statutory_penalty_risk": float(penal_interest_234c + penal_interest_234b)
            },
            "challans_recorded": [
                {
                    "id": str(c.id),
                    "quarter": c.quarter,
                    "payment_date": c.payment_date.isoformat(),
                    "bsr_code": c.bsr_code,
                    "challan_serial_no": c.challan_serial_no,
                    "amount_paid": float(c.amount_paid)
                } for c in challans
            ]
        }

    @staticmethod
    async def record_advance_tax_challan(
        db: AsyncSession,
        tenant: Tenant,
        fiscal_year: str,
        quarter: str,
        payment_date: date,
        bsr_code: str,
        challan_serial_no: str,
        amount_paid: Decimal,
        cin_number: Optional[str] = None,
        s3_challan_receipt_key: Optional[str] = None
    ) -> AdvanceTaxChallan:
        """
        Records an advance tax payment (Challan ITNS 280 / e-Pay Tax).
        """
        norm_q = quarter.upper().strip()
        if norm_q not in ("Q1", "Q2", "Q3", "Q4"):
            raise ValueError(f"Invalid quarter '{quarter}'. Must be Q1, Q2, Q3, or Q4.")

        stmt = (
            select(AdvanceTaxChallan)
            .where(
                AdvanceTaxChallan.tenant_id == tenant.id,
                AdvanceTaxChallan.bsr_code == bsr_code,
                AdvanceTaxChallan.challan_serial_no == challan_serial_no
            )
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            raise ValueError(f"Challan with BSR {bsr_code} and Serial {challan_serial_no} is already registered.")

        challan = AdvanceTaxChallan(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            fiscal_year=fiscal_year,
            quarter=norm_q,
            payment_date=payment_date,
            bsr_code=bsr_code,
            challan_serial_no=challan_serial_no,
            cin_number=cin_number,
            amount_paid=amount_paid,
            s3_challan_receipt_key=s3_challan_receipt_key
        )
        db.add(challan)
        await db.commit()
        await db.refresh(challan)
        return challan

    @staticmethod
    def generate_epay_tax_packet(
        tenant: Tenant,
        fiscal_year: str,
        quarter: str,
        amount: Decimal
    ) -> Dict[str, Any]:
        """
        Formats pre-filled metadata for 1-click filing via CBDT e-Pay Tax / Challan 280.
        """
        _, _, ay = AdvanceTaxService.parse_fy_dates(fiscal_year)
        legal_name = (tenant.legal_name or "").upper()
        prof = tenant.statutory_profile or {}
        is_llp = "LLP" in legal_name or "LLP" in (prof.get("entity_type") or "").upper()

        major_head = "0020 (Corporation Tax)" if not is_llp else "0021 (Other Than Companies)"
        major_head_code = "0020" if not is_llp else "0021"

        return {
            "entity_name": tenant.legal_name,
            "pan": tenant.pan,
            "financial_year": fiscal_year,
            "assessment_year": ay,
            "quarter": quarter.upper(),
            "major_head": major_head,
            "major_head_code": major_head_code,
            "minor_head": "100 (Advance Tax)",
            "minor_head_code": "100",
            "recommended_amount_inr": float(amount),
            "payment_portal_url": "https://eportal.incometax.gov.in/iec/foservices/#/login",
            "statutory_instructions": (
                f"Log into CBDT e-Filing portal, navigate to e-File -> e-Pay Tax -> New Payment. "
                f"Select Major Head {major_head_code} and Minor Head 100 (Advance Tax). "
                f"Enter Assessment Year {ay} and make payment via Netbanking/UPI."
            )
        }

