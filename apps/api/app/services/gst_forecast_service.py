import uuid
import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.invoice import Invoice
from app.models.expense import Expense
from app.models.compliance import GSTChallan


class GSTForecastService:
    """
    Real-Time Multi-Frequency GST Forecasting Engine & Cash Watchdog.
    Supports:
    1. Monthly GSTR-3B (Due 20th of following month)
    2. Quarterly QRMP (PMT-06 35% safe harbor in M1/M2, GSTR-3B due 22nd/24th in M3)
    3. Quarterly Composition CMP-08 (Flat 1% or 6%, no ITC, due 18th)
    4. Annual GSTR-9 True-up & DRC-03 reconciliation (Due Dec 31)
    Enforces Rule 88A set-off hierarchy: IGST -> CGST -> SGST.
    """

    @staticmethod
    def _parse_fiscal_year_dates(fiscal_year: str) -> tuple[date, date, int, int]:
        parts = fiscal_year.split('-')
        start_yr = int(parts[0])
        end_yr = start_yr + 1 if len(parts[1]) == 2 else int(parts[1])
        return date(start_yr, 4, 1), date(end_yr, 3, 31), start_yr, end_yr

    @staticmethod
    def _get_period_date_range(fiscal_year: str, period_key: str) -> tuple[date, date]:
        """
        Converts period_key to (start_date, end_date).
        period_key examples:
        - '2026-04', '2026-05', etc. (Monthly)
        - 'Q1' (Apr-Jun), 'Q2' (Jul-Sep), 'Q3' (Oct-Dec), 'Q4' (Jan-Mar)
        - 'annual' (Full FY)
        """
        start_fy, end_fy, start_yr, end_yr = GSTForecastService._parse_fiscal_year_dates(fiscal_year)

        if period_key == "annual" or not period_key:
            return start_fy, end_fy

        norm_p = period_key.upper().strip()
        if norm_p == "Q1":
            return date(start_yr, 4, 1), date(start_yr, 6, 30)
        elif norm_p == "Q2":
            return date(start_yr, 7, 1), date(start_yr, 9, 30)
        elif norm_p == "Q3":
            return date(start_yr, 10, 1), date(start_yr, 12, 31)
        elif norm_p == "Q4":
            return date(end_yr, 1, 1), date(end_yr, 3, 31)

        # Monthly: format 'YYYY-MM'
        if "-" in period_key:
            try:
                y, m = map(int, period_key.split('-'))
                s_date = date(y, m, 1)
                if m == 12:
                    e_date = date(y, 12, 31)
                else:
                    next_m = date(y, m + 1, 1)
                    e_date = next_m - timedelta(days=1)
                return s_date, e_date
            except Exception:
                pass

        return start_fy, end_fy

    @staticmethod
    def apply_rule_88a_setoff(
        output_igst: Decimal,
        output_cgst: Decimal,
        output_sgst: Decimal,
        input_igst: Decimal,
        input_cgst: Decimal,
        input_sgst: Decimal
    ) -> Dict[str, Any]:
        """
        Implements statutory Section 49 / Rule 88A CGST Rules set-off order:
        Step 1: IGST Credit MUST be completely exhausted first:
                a) against IGST Output Liability
                b) remaining IGST Credit against CGST and SGST Output in any proportion.
        Step 2: CGST Credit utilized:
                a) against remaining CGST Output
                b) against remaining IGST Output (if any)
                c) NEVER against SGST.
        Step 3: SGST Credit utilized:
                a) against remaining SGST Output
                b) against remaining IGST Output (if any)
                c) NEVER against CGST.
        """
        # Step 1: Utilize IGST Credit
        rem_out_igst = output_igst
        rem_out_cgst = output_cgst
        rem_out_sgst = output_sgst

        rem_in_igst = input_igst
        rem_in_cgst = input_cgst
        rem_in_sgst = input_sgst

        igst_setoff_against_igst = min(rem_in_igst, rem_out_igst)
        rem_out_igst -= igst_setoff_against_igst
        rem_in_igst -= igst_setoff_against_igst

        # If IGST credit remains, offset against CGST, then SGST
        igst_setoff_against_cgst = min(rem_in_igst, rem_out_cgst)
        rem_out_cgst -= igst_setoff_against_cgst
        rem_in_igst -= igst_setoff_against_cgst

        igst_setoff_against_sgst = min(rem_in_igst, rem_out_sgst)
        rem_out_sgst -= igst_setoff_against_sgst
        rem_in_igst -= igst_setoff_against_sgst

        # Step 2: Utilize CGST Credit
        cgst_setoff_against_cgst = min(rem_in_cgst, rem_out_cgst)
        rem_out_cgst -= cgst_setoff_against_cgst
        rem_in_cgst -= cgst_setoff_against_cgst

        cgst_setoff_against_igst = min(rem_in_cgst, rem_out_igst)
        rem_out_igst -= cgst_setoff_against_igst
        rem_in_cgst -= cgst_setoff_against_igst

        # Step 3: Utilize SGST Credit
        sgst_setoff_against_sgst = min(rem_in_sgst, rem_out_sgst)
        rem_out_sgst -= sgst_setoff_against_sgst
        rem_in_sgst -= sgst_setoff_against_sgst

        sgst_setoff_against_igst = min(rem_in_sgst, rem_out_igst)
        rem_out_igst -= sgst_setoff_against_igst
        rem_in_sgst -= sgst_setoff_against_igst

        total_cash_payable = rem_out_igst + rem_out_cgst + rem_out_sgst
        total_credit_closing_balance = rem_in_igst + rem_in_cgst + rem_in_sgst

        return {
            "output_tax": {
                "igst": float(output_igst),
                "cgst": float(output_cgst),
                "sgst": float(output_sgst),
                "total": float(output_igst + output_cgst + output_sgst)
            },
            "input_tax_credit": {
                "igst": float(input_igst),
                "cgst": float(input_cgst),
                "sgst": float(input_sgst),
                "total": float(input_igst + input_cgst + input_sgst)
            },
            "setoff_breakdown": {
                "igst_against_igst": float(igst_setoff_against_igst),
                "igst_against_cgst": float(igst_setoff_against_cgst),
                "igst_against_sgst": float(igst_setoff_against_sgst),
                "cgst_against_cgst": float(cgst_setoff_against_cgst),
                "cgst_against_igst": float(cgst_setoff_against_igst),
                "sgst_against_sgst": float(sgst_setoff_against_sgst),
                "sgst_against_igst": float(sgst_setoff_against_igst)
            },
            "net_cash_payable": {
                "igst": float(rem_out_igst),
                "cgst": float(rem_out_cgst),
                "sgst": float(rem_out_sgst),
                "total": float(total_cash_payable)
            },
            "closing_itc_balance": {
                "igst": float(rem_in_igst),
                "cgst": float(rem_in_cgst),
                "sgst": float(rem_in_sgst),
                "total": float(total_credit_closing_balance)
            }
        }

    @staticmethod
    async def compute_gst_forecast(
        db: AsyncSession,
        tenant: Tenant,
        fiscal_year: str,
        frequency: str = "monthly",
        return_period: Optional[str] = None,
        composition_rate: Decimal = Decimal("0.01")
    ) -> Dict[str, Any]:
        """
        Computes real-time GST Forecast across selected filing frequency:
        - 'monthly' (GSTR-3B)
        - 'quarterly_qrmp' (QRMP Scheme with PMT-06 35% safe harbor)
        - 'composition' (CMP-08 flat rate)
        - 'annual' (GSTR-9 True-up)
        """
        freq_norm = frequency.lower().strip()
        if freq_norm not in ("monthly", "quarterly_qrmp", "composition", "annual"):
            freq_norm = "monthly"

        # Determine date range for the calculation
        today = date.today()
        if not return_period:
            if freq_norm == "monthly":
                return_period = f"{today.year}-{today.month:02d}"
            elif freq_norm in ("quarterly_qrmp", "composition"):
                m = today.month
                if 4 <= m <= 6:
                    return_period = "Q1"
                elif 7 <= m <= 9:
                    return_period = "Q2"
                elif 10 <= m <= 12:
                    return_period = "Q3"
                else:
                    return_period = "Q4"
            else:
                return_period = "annual"

        start_date, end_date = GSTForecastService._get_period_date_range(fiscal_year, return_period)

        # 1. Compute Output Tax from Sales Invoices
        stmt_inv = (
            select(
                func.coalesce(func.sum(Invoice.subtotal), Decimal("0.00")),
                func.coalesce(func.sum(Invoice.cgst_total), Decimal("0.00")),
                func.coalesce(func.sum(Invoice.sgst_total), Decimal("0.00")),
                func.coalesce(func.sum(Invoice.igst_total), Decimal("0.00")),
                func.coalesce(func.sum(Invoice.grand_total), Decimal("0.00")),
                func.count(Invoice.id)
            )
            .where(
                Invoice.tenant_id == tenant.id,
                Invoice.status.notin_(("cancelled", "draft")),
                Invoice.issue_date >= start_date,
                Invoice.issue_date <= end_date
            )
        )
        res_inv = await db.execute(stmt_inv)
        inv_taxable, inv_cgst, inv_sgst, inv_igst, inv_total, inv_count = res_inv.one()

        # 2. Compute Input Tax Credit (ITC) from Expenses & Vendor Bills
        stmt_exp = (
            select(
                func.coalesce(func.sum(Expense.total_amount), Decimal("0.00")),
                func.coalesce(func.sum(Expense.cgst_amount), Decimal("0.00")),
                func.coalesce(func.sum(Expense.sgst_amount), Decimal("0.00")),
                func.coalesce(func.sum(Expense.igst_amount), Decimal("0.00")),
                func.count(Expense.id)
            )
            .where(
                Expense.tenant_id == tenant.id,
                Expense.status.notin_(("rejected", "struck_off", "draft")),
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date
            )
        )
        res_exp = await db.execute(stmt_exp)
        exp_total, exp_cgst, exp_sgst, exp_igst, exp_count = res_exp.one()

        # 3. Retrieve GST challans already paid for this period
        stmt_paid = (
            select(
                func.coalesce(func.sum(GSTChallan.cgst_amount), Decimal("0.00")),
                func.coalesce(func.sum(GSTChallan.sgst_amount), Decimal("0.00")),
                func.coalesce(func.sum(GSTChallan.igst_amount), Decimal("0.00")),
                func.coalesce(func.sum(GSTChallan.total_amount), Decimal("0.00"))
            )
            .where(
                GSTChallan.tenant_id == tenant.id,
                GSTChallan.fiscal_year == fiscal_year,
                GSTChallan.period == return_period
            )
        )
        res_paid = await db.execute(stmt_paid)
        paid_cgst, paid_sgst, paid_igst, total_paid = res_paid.one()

        # 4. Mode-specific calculations
        if freq_norm == "composition":
            # Composition Scheme under Section 10: Flat % on taxable turnover, NO ITC
            total_turnover = Decimal(str(inv_taxable))
            rate = Decimal(str(composition_rate))
            comp_tax = (total_turnover * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            half_comp = (comp_tax / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            net_payable = max(Decimal("0.00"), comp_tax - total_paid)
            due_date = GSTForecastService._get_due_date(freq_norm, return_period, end_date)

            return {
                "tenant_gstin": tenant.gstin or "N/A",
                "fiscal_year": fiscal_year,
                "frequency": "composition",
                "frequency_label": "Quarterly Composition Scheme (CMP-08)",
                "return_period": return_period,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "statutory_due_date": due_date.isoformat(),
                "taxable_turnover": float(total_turnover),
                "composition_rate_percent": float(rate * 100),
                "gross_tax_liability": float(comp_tax),
                "cgst_liability": float(half_comp),
                "sgst_liability": float(half_comp),
                "igst_liability": 0.00,
                "itc_allowed": False,
                "total_paid_challans": float(total_paid),
                "net_cash_payable": float(net_payable),
                "recommended_weekly_reserve": float((net_payable / 4).quantize(Decimal("0.01"))),
                "statutory_rule": "Section 10 CGST Act / Form CMP-08 Due 18th following quarter"
            }

        # Apply Rule 88A setoff for Regular, QRMP, and Annual
        rule_88a_result = GSTForecastService.apply_rule_88a_setoff(
            output_igst=Decimal(str(inv_igst)),
            output_cgst=Decimal(str(inv_cgst)),
            output_sgst=Decimal(str(inv_sgst)),
            input_igst=Decimal(str(exp_igst)),
            input_cgst=Decimal(str(exp_cgst)),
            input_sgst=Decimal(str(exp_sgst))
        )

        gross_cash_due = Decimal(str(rule_88a_result["net_cash_payable"]["total"]))
        net_cash_after_challans = max(Decimal("0.00"), gross_cash_due - total_paid)

        # QRMP safe harbor fixed sum computation (35% Challan PMT-06)
        qrmp_pmt06_35pct = (gross_cash_due * Decimal("0.35")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        due_date = GSTForecastService._get_due_date(freq_norm, return_period, end_date)
        weekly_reserve = (net_cash_after_challans / 4).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return {
            "tenant_gstin": tenant.gstin or "N/A",
            "fiscal_year": fiscal_year,
            "frequency": freq_norm,
            "frequency_label": (
                "Monthly GSTR-3B (Regular)" if freq_norm == "monthly" else
                "Quarterly Return Monthly Payment (QRMP Scheme)" if freq_norm == "quarterly_qrmp" else
                "Annual GSTR-9 True-Up & DRC-03 Reconciliation"
            ),
            "return_period": return_period,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "statutory_due_date": due_date.isoformat(),
            "invoices_count": inv_count,
            "expenses_count": exp_count,
            "total_outward_taxable_supplies": float(inv_taxable),
            "total_inward_supplies": float(exp_total),
            "output_tax": rule_88a_result["output_tax"],
            "eligible_itc": rule_88a_result["input_tax_credit"],
            "rule_88a_setoff": rule_88a_result["setoff_breakdown"],
            "gross_cash_payable": rule_88a_result["net_cash_payable"],
            "total_challans_paid": float(total_paid),
            "net_cash_due_after_challans": float(net_cash_after_challans),
            "closing_itc_balance": rule_88a_result["closing_itc_balance"],
            "qrmp_35pct_safe_harbor_amount": float(qrmp_pmt06_35pct),
            "recommended_weekly_reserve": float(weekly_reserve),
            "is_fully_paid": net_cash_after_challans == Decimal("0.00"),
            "statutory_reference": (
                "CGST Rule 88A & Section 49 / GSTR-3B Due 20th" if freq_norm == "monthly" else
                "Notification No. 85/2020-Central Tax (QRMP Scheme & PMT-06 35% Safe Harbor)" if freq_norm == "quarterly_qrmp" else
                "Section 44 CGST Act / GSTR-9 Annual Return Due December 31"
            )
        }

    @staticmethod
    def _get_due_date(freq: str, period_key: str, period_end_date: date) -> date:
        """
        Determines the statutory GST payment / filing due date:
        - Monthly: 20th of the following month
        - QRMP: 22nd / 24th of following month (Month 3) or 25th (PMT-06 in M1/M2)
        - Composition: 18th of following month
        - Annual: December 31 following the FY
        """
        if freq == "annual":
            return date(period_end_date.year, 12, 31)

        if freq == "composition":
            # 18th of the month following quarter
            m = period_end_date.month
            y = period_end_date.year
            if m == 12:
                return date(y + 1, 1, 18)
            else:
                return date(y, m + 1, 18)

        if freq == "monthly":
            m = period_end_date.month
            y = period_end_date.year
            if m == 12:
                return date(y + 1, 1, 20)
            else:
                return date(y, m + 1, 20)

        # QRMP: GSTR-3B due on 22nd of the month following the quarter
        m = period_end_date.month
        y = period_end_date.year
        if m == 12:
            return date(y + 1, 1, 22)
        else:
            return date(y, m + 1, 22)

    @staticmethod
    def generate_pmt06_packet(
        tenant: Tenant,
        fiscal_year: str,
        period: str,
        reason: str = "monthly_payment_qrmp",
        cgst: Decimal = Decimal("0.00"),
        sgst: Decimal = Decimal("0.00"),
        igst: Decimal = Decimal("0.00"),
        cess: Decimal = Decimal("0.00")
    ) -> Dict[str, Any]:
        """
        Generates pre-filled GST Portal Challan PMT-06 JSON packet for 1-click payment creation.
        """
        total = cgst + sgst + igst + cess
        return {
            "gstin": tenant.gstin or "",
            "legal_name": tenant.legal_name,
            "trade_name": tenant.trade_name or tenant.legal_name,
            "fiscal_year": fiscal_year,
            "return_period": period,
            "challan_type": "PMT-06",
            "reason_for_challan": (
                "Monthly payment for quarterly return (35% Challan / Self-Assessment)"
                if reason == "monthly_payment_qrmp" else "Any other payment"
            ),
            "major_heads": {
                "0005_cgst": {
                    "tax": float(cgst),
                    "interest": 0.00,
                    "penalty": 0.00,
                    "fees": 0.00,
                    "other": 0.00,
                    "total": float(cgst)
                },
                "0006_sgst": {
                    "tax": float(sgst),
                    "interest": 0.00,
                    "penalty": 0.00,
                    "fees": 0.00,
                    "other": 0.00,
                    "total": float(sgst)
                },
                "0008_igst": {
                    "tax": float(igst),
                    "interest": 0.00,
                    "penalty": 0.00,
                    "fees": 0.00,
                    "other": 0.00,
                    "total": float(igst)
                },
                "0009_cess": {
                    "tax": float(cess),
                    "interest": 0.00,
                    "penalty": 0.00,
                    "fees": 0.00,
                    "other": 0.00,
                    "total": float(cess)
                }
            },
            "total_challan_amount": float(total),
            "portal_instructions": [
                "1. Log in to Services > Payments > Create Challan on gst.gov.in.",
                "2. Select Reason for Challan: Monthly payment for quarterly return.",
                "3. Enter the amounts under CGST, SGST, and IGST as specified above.",
                "4. Generate CPIN and pay via Net Banking, NEFT/RTGS, or Over the Counter."
            ]
        }

    @staticmethod
    async def record_gst_challan(
        db: AsyncSession,
        tenant: Tenant,
        fiscal_year: str,
        period: str,
        frequency: str,
        challan_type: str,
        cpin: str,
        payment_date: date,
        cgst_amount: Decimal,
        sgst_amount: Decimal,
        igst_amount: Decimal,
        cess_amount: Decimal = Decimal("0.00"),
        interest_amount: Decimal = Decimal("0.00"),
        penalty_amount: Decimal = Decimal("0.00"),
        cin: Optional[str] = None,
        bank_ref_no: Optional[str] = None,
        s3_challan_receipt_key: Optional[str] = None
    ) -> GSTChallan:
        """
        Records a verified GST tax payment challan (PMT-06, PMT-01, CMP-08).
        """
        total = cgst_amount + sgst_amount + igst_amount + cess_amount + interest_amount + penalty_amount
        if total <= Decimal("0.00"):
            raise ValueError("Challan payment amount must be greater than zero.")

        # Check for duplicate CPIN
        stmt = (
            select(GSTChallan)
            .where(
                GSTChallan.tenant_id == tenant.id,
                GSTChallan.cpin == cpin
            )
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            raise ValueError(f"GST Challan with CPIN {cpin} already recorded on {existing.payment_date}.")

        challan = GSTChallan(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            fiscal_year=fiscal_year,
            period=period,
            frequency=frequency,
            challan_type=challan_type,
            cpin=cpin,
            cin=cin,
            payment_date=payment_date,
            bank_ref_no=bank_ref_no,
            cgst_amount=cgst_amount,
            sgst_amount=sgst_amount,
            igst_amount=igst_amount,
            cess_amount=cess_amount,
            interest_amount=interest_amount,
            penalty_amount=penalty_amount,
            total_amount=total,
            s3_challan_receipt_key=s3_challan_receipt_key
        )
        db.add(challan)
        await db.commit()
        await db.refresh(challan)
        return challan

    @staticmethod
    async def list_gst_challans_for_fy(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: str
    ) -> List[GSTChallan]:
        stmt = (
            select(GSTChallan)
            .where(
                GSTChallan.tenant_id == tenant_id,
                GSTChallan.fiscal_year == fiscal_year
            )
            .order_by(GSTChallan.payment_date.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
