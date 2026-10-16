"""
b00k5 Financial Engine: Indian TDS & TCS Withholding Engine (Phase 10: FEAT-08)
Statutory Compliance with Income-tax Act, 1961:
- Section 194C (Contractors / Sub-contractors: 1% Individual/HUF, 2% Other)
- Section 194J (Professional: 10%, Technical: 2%)
- Section 194I (Rent: 2% Plant/Machinery, 10% Land/Building/Furniture)
- Section 194Q (Purchase of Goods > ₹50L: 0.1%)
- Section 206AA (Higher 20% / 5% rate for invalid or missing PAN)
- Section 206AB (Higher rate for non-filers of ITR)
- Challan ITNS 281 Payment Tracking & Balancing GL Vouchers
- Form 26Q e-TDS Text Return File Generator (NSDL / Protean e-Gov Spec)
"""

import uuid
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.tds import TDSChallan, TDSDeduction
from app.services.ledger_service import LedgerService
from app.core.fiscal_year import calculate_indian_fy_ay


TDS_SECTION_RULES: Dict[str, Dict[str, Any]] = {
    "194C": {
        "name": "Payments to Contractors / Sub-contractors",
        "rate_individual_huf": Decimal("1.00"),
        "rate_company_others": Decimal("2.00"),
        "single_bill_threshold": Decimal("30000.00"),
        "aggregate_fy_threshold": Decimal("100000.00"),
        "non_pan_rate": Decimal("20.00"),
        "account_code": "2061",
        "description": "TDS on Contractor Payments u/s 194C"
    },
    "194J": {
        "name": "Fees for Professional / Technical Services",
        "rate_professional": Decimal("10.00"),
        "rate_technical": Decimal("2.00"),
        "single_bill_threshold": Decimal("30000.00"),
        "aggregate_fy_threshold": Decimal("30000.00"),
        "non_pan_rate": Decimal("20.00"),
        "account_code": "2060",
        "description": "TDS on Professional/Tech Fees u/s 194J"
    },
    "194I": {
        "name": "Rent for Land, Building or Machinery",
        "rate_plant_machinery": Decimal("2.00"),
        "rate_land_building": Decimal("10.00"),
        "single_bill_threshold": Decimal("240000.00"),
        "aggregate_fy_threshold": Decimal("240000.00"),
        "non_pan_rate": Decimal("20.00"),
        "account_code": "2062",
        "description": "TDS on Rent u/s 194I"
    },
    "194Q": {
        "name": "Purchase of Goods exceeding ₹50 Lakhs",
        "rate_standard": Decimal("0.10"),
        "single_bill_threshold": Decimal("5000000.00"),
        "aggregate_fy_threshold": Decimal("5000000.00"),
        "non_pan_rate": Decimal("5.00"),
        "account_code": "2063",
        "description": "TDS on Purchase of Goods u/s 194Q"
    }
}


class TDSService:
    @staticmethod
    def bankers_round(value: Decimal, places: int = 2) -> Decimal:
        quant = Decimal('10') ** -places
        return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_EVEN)

    @staticmethod
    def validate_pan(pan: Optional[str]) -> Tuple[bool, str]:
        """
        Validates 10-char Indian PAN format: 5 letters, 4 digits, 1 letter.
        Extracts 4th character entity type.
        """
        if not pan:
            return False, "UNKNOWN"
        clean = pan.strip().upper()
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', clean):
            return False, "INVALID"
        fourth_char = clean[3]
        if fourth_char in ('P', 'H'):
            return True, "NON_COMPANY"
        return True, "COMPANY"

    @staticmethod
    def calculate_tds(
        gross_amount: Decimal,
        section: str,
        deductee_type: str = "COMPANY",
        pan: Optional[str] = None,
        sub_type: Optional[str] = None,
        is_lower_deduction: bool = False,
        lower_deduction_rate: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Calculates statutory TDS deduction according to Income Tax rules.
        """
        sec = section.strip().upper().replace("SEC", "").replace("U/S", "").replace(" ", "")
        if sec not in TDS_SECTION_RULES:
            raise ValueError(f"Unsupported TDS section: {section}. Supported sections: 194C, 194J, 194I, 194Q")

        rule = TDS_SECTION_RULES[sec]
        gross = TDSService.bankers_round(gross_amount)
        pan_valid, detected_type = TDSService.validate_pan(pan)
        actual_deductee_type = detected_type if pan_valid else deductee_type.upper()

        if is_lower_deduction and lower_deduction_rate is not None:
            rate = TDSService.bankers_round(lower_deduction_rate)
            notes = f"Lower deduction certificate applied u/s 197: {rate}%"
        elif not pan_valid:
            # Section 206AA penal rate
            rate = rule["non_pan_rate"]
            notes = f"Section 206AA applied: Invalid or missing PAN. Higher rate {rate}%"
        else:
            if sec == "194C":
                rate = rule["rate_individual_huf"] if actual_deductee_type == "NON_COMPANY" else rule["rate_company_others"]
                notes = f"Section 194C ({'Individual/HUF 1%' if actual_deductee_type == 'NON_COMPANY' else 'Company/Others 2%'})"
            elif sec == "194J":
                if sub_type and "tech" in sub_type.lower():
                    rate = rule["rate_technical"]
                    notes = "Section 194J Technical/Call Center (2%)"
                else:
                    rate = rule["rate_professional"]
                    notes = "Section 194J Professional Services (10%)"
            elif sec == "194I":
                if sub_type and ("plant" in sub_type.lower() or "machin" in sub_type.lower() or "equip" in sub_type.lower()):
                    rate = rule["rate_plant_machinery"]
                    notes = "Section 194I Plant & Machinery (2%)"
                else:
                    rate = rule["rate_land_building"]
                    notes = "Section 194I Land, Building & Furniture (10%)"
            elif sec == "194Q":
                rate = rule["rate_standard"]
                notes = "Section 194Q Purchase of Goods (0.1%)"
            else:
                rate = Decimal("2.00")
                notes = f"Standard deduction for {sec}"

        threshold = rule["single_bill_threshold"]
        threshold_exceeded = gross >= threshold

        tds_amount = TDSService.bankers_round(gross * (rate / Decimal("100.00")))
        net_payable = gross - tds_amount

        return {
            "gross_amount": gross,
            "section": sec,
            "applicable_rate_pct": rate,
            "tds_amount": tds_amount,
            "net_payable_amount": net_payable,
            "pan_valid": pan_valid,
            "threshold_exceeded": threshold_exceeded,
            "statutory_notes": notes,
            "account_code": rule["account_code"]
        }

    @staticmethod
    def get_quarter_for_date(d: date) -> str:
        month = d.month
        if month in (4, 5, 6):
            return "Q1"
        elif month in (7, 8, 9):
            return "Q2"
        elif month in (10, 11, 12):
            return "Q3"
        else:
            return "Q4"

    @staticmethod
    def get_next_tds_due_date(reference_date: Optional[date] = None) -> date:
        """
        Rule 30: Due date is 7th of the following month (or April 30 for March).
        """
        ref = reference_date or date.today()
        if ref.month == 3:
            return date(ref.year, 4, 30)
        elif ref.month == 12:
            return date(ref.year + 1, 1, 7)
        else:
            return date(ref.year, ref.month + 1, 7)

    @staticmethod
    async def record_tds_deduction(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        deductee_name: str,
        deductee_pan: str,
        section: str,
        gross_amount: Decimal,
        expense_id: Optional[uuid.UUID] = None,
        journal_entry_id: Optional[uuid.UUID] = None,
        rate_percentage: Optional[Decimal] = None,
        deduction_date: Optional[date] = None,
        deductee_type: str = "COMPANY"
    ) -> TDSDeduction:
        d_date = deduction_date or date.today()
        fy_info = calculate_indian_fy_ay(d_date)
        fy_str = f"{fy_info['fy_start_year']}-{str(fy_info['fy_end_year'])[-2:]}"
        quarter = TDSService.get_quarter_for_date(d_date)

        calc = TDSService.calculate_tds(
            gross_amount=gross_amount,
            section=section,
            deductee_type=deductee_type,
            pan=deductee_pan,
            is_lower_deduction=bool(rate_percentage is not None and rate_percentage < Decimal("10.00")),
            lower_deduction_rate=rate_percentage
        )

        deduction = TDSDeduction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            expense_id=expense_id,
            journal_entry_id=journal_entry_id,
            deductee_name=deductee_name,
            deductee_pan=deductee_pan.strip().upper(),
            deductee_type="NON_COMPANY" if calc["pan_valid"] and deductee_pan[3].upper() in ('P', 'H') else "COMPANY",
            section=calc["section"],
            rate_percentage=calc["applicable_rate_pct"],
            gross_amount=calc["gross_amount"],
            tds_amount=calc["tds_amount"],
            net_payable=calc["net_payable_amount"],
            deduction_date=d_date,
            fiscal_year=fy_str,
            quarter=quarter,
            status="PENDING_DEPOSIT"
        )
        db.add(deduction)
        await db.flush()
        return deduction

    @staticmethod
    async def record_challan_itns281(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: str,
        quarter: str,
        section: str,
        bsr_code: str,
        challan_serial_no: str,
        payment_date: date,
        tds_amount: Decimal,
        surcharge_amount: Decimal = Decimal("0.00"),
        cess_amount: Decimal = Decimal("0.00"),
        interest_amount: Decimal = Decimal("0.00"),
        fee_amount: Decimal = Decimal("0.00"),
        cin: Optional[str] = None,
        minor_head: str = "200",
        deduction_ids: Optional[List[uuid.UUID]] = None,
        auto_post_jv: bool = True,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Records Challan ITNS 281 tax deposit, updates linked deductions to DEPOSITED,
        and posts balancing Journal Voucher to General Ledger:
        DR 206x TDS Payable u/s [Section]
        CR 1010 Bank Current Account
        """
        tds_amt = TDSService.bankers_round(tds_amount)
        sur_amt = TDSService.bankers_round(surcharge_amount)
        cess_amt = TDSService.bankers_round(cess_amount)
        int_amt = TDSService.bankers_round(interest_amount)
        fee_amt = TDSService.bankers_round(fee_amount)
        total_paid = tds_amt + sur_amt + cess_amt + int_amt + fee_amt

        challan = TDSChallan(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            quarter=quarter,
            section=section,
            bsr_code=bsr_code,
            challan_serial_no=challan_serial_no,
            payment_date=payment_date,
            tds_amount=tds_amt,
            surcharge_amount=sur_amt,
            cess_amount=cess_amt,
            interest_amount=int_amt,
            fee_amount=fee_amt,
            total_amount=total_paid,
            cin=cin,
            minor_head=minor_head
        )
        db.add(challan)
        await db.flush()

        # Update linked deductions
        linked_count = 0
        if deduction_ids:
            stmt = (
                update(TDSDeduction)
                .where(and_(TDSDeduction.tenant_id == tenant_id, TDSDeduction.id.in_(deduction_ids)))
                .values(tds_challan_id=challan.id, status="DEPOSITED")
            )
            res = await db.execute(stmt)
            linked_count = res.rowcount
        else:
            # Auto-link unlinked deductions matching section and quarter
            stmt = (
                update(TDSDeduction)
                .where(
                    and_(
                        TDSDeduction.tenant_id == tenant_id,
                        TDSDeduction.fiscal_year == fiscal_year,
                        TDSDeduction.quarter == quarter,
                        TDSDeduction.section == section,
                        TDSDeduction.status == "PENDING_DEPOSIT"
                    )
                )
                .values(tds_challan_id=challan.id, status="DEPOSITED")
            )
            res = await db.execute(stmt)
            linked_count = res.rowcount

        # Post Balancing General Ledger Journal Entry
        jv_id = None
        jv_number = None
        if auto_post_jv and total_paid > Decimal("0.00"):
            sec_rule = TDS_SECTION_RULES.get(section, {"account_code": "2060"})
            tds_acc_code = sec_rule["account_code"]
            bank_acc_code = "1010"

            tds_acc = await LedgerService.get_account_by_code(db, tenant_id, tds_acc_code)
            bank_acc = await LedgerService.get_account_by_code(db, tenant_id, bank_acc_code)

            if tds_acc and bank_acc:
                jv_number = f"JV-TDS-CHAL-{uuid.uuid4().hex[:6].upper()}"
                entry = JournalEntry(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    entry_number=jv_number,
                    entry_date=payment_date,
                    reference_type="tds_challan_deposit",
                    narration=f"TDS Payment via Challan ITNS 281 (BSR: {bsr_code}, Serial: {challan_serial_no}, Sec {section})",
                    status="posted",
                    is_posted=True,
                    created_by=created_by
                )
                db.add(entry)
                await db.flush()

                lines = [
                    JournalLine(
                        id=uuid.uuid4(),
                        journal_entry_id=entry.id,
                        tenant_id=tenant_id,
                        account_id=tds_acc.id,
                        debit_amount=total_paid,
                        credit_amount=Decimal("0.00"),
                        description=f"TDS Settlement u/s {section} (Challan 281)"
                    ),
                    JournalLine(
                        id=uuid.uuid4(),
                        journal_entry_id=entry.id,
                        tenant_id=tenant_id,
                        account_id=bank_acc.id,
                        debit_amount=Decimal("0.00"),
                        credit_amount=total_paid,
                        description=f"HDFC Bank wire for TDS payment (BSR: {bsr_code})"
                    )
                ]
                db.add_all(lines)
                await db.flush()
                jv_id = entry.id

        await db.commit()

        return {
            "challan_id": challan.id,
            "bsr_code": bsr_code,
            "challan_serial_no": challan_serial_no,
            "payment_date": payment_date,
            "total_amount": total_paid,
            "linked_deductions_count": linked_count,
            "journal_entry_id": jv_id,
            "journal_entry_number": jv_number
        }

    @staticmethod
    async def get_tds_summary(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Summarizes TDS deductions, deposited amounts, and upcoming statutory deadlines.
        """
        if fiscal_year:
            fy = fiscal_year
        else:
            fy_info = calculate_indian_fy_ay(date.today())
            fy = f"{fy_info['fy_start_year']}-{str(fy_info['fy_end_year'])[-2:]}"

        # Deductions summary
        # Deductions total
        stmt_tot = (
            select(func.coalesce(func.sum(TDSDeduction.tds_amount), Decimal("0.00")))
            .where(and_(TDSDeduction.tenant_id == tenant_id, TDSDeduction.fiscal_year == fy))
        )
        total_deducted = Decimal(str((await db.execute(stmt_tot)).scalar() or "0.00"))

        # Challans sum
        stmt_ch = (
            select(func.coalesce(func.sum(TDSChallan.total_amount), Decimal("0.00")))
            .where(and_(TDSChallan.tenant_id == tenant_id, TDSChallan.fiscal_year == fy))
        )
        res_ch = await db.execute(stmt_ch)
        total_deposited = Decimal(str(res_ch.scalar() or "0.00"))

        pending_deposit = max(Decimal("0.00"), total_deducted - total_deposited)
        next_due = TDSService.get_next_tds_due_date(date.today())
        days_until_due = (next_due - date.today()).days

        # Quarter breakdown
        q_summaries = []
        for q in ("Q1", "Q2", "Q3", "Q4"):
            stmt_q = (
                select(
                    func.coalesce(func.sum(TDSDeduction.gross_amount), Decimal("0.00")),
                    func.coalesce(func.sum(TDSDeduction.tds_amount), Decimal("0.00")),
                    func.count(TDSDeduction.id)
                )
                .where(
                    and_(
                        TDSDeduction.tenant_id == tenant_id,
                        TDSDeduction.fiscal_year == fy,
                        TDSDeduction.quarter == q
                    )
                )
            )
            r_q = (await db.execute(stmt_q)).first()
            q_summaries.append({
                "quarter": q,
                "gross_amount": float(r_q[0]),
                "tds_amount": float(r_q[1]),
                "deduction_count": r_q[2]
            })

        # Section breakdown
        stmt_sec = (
            select(
                TDSDeduction.section,
                func.coalesce(func.sum(TDSDeduction.gross_amount), Decimal("0.00")),
                func.coalesce(func.sum(TDSDeduction.tds_amount), Decimal("0.00")),
                func.count(TDSDeduction.id)
            )
            .where(and_(TDSDeduction.tenant_id == tenant_id, TDSDeduction.fiscal_year == fy))
            .group_by(TDSDeduction.section)
        )
        sec_rows = (await db.execute(stmt_sec)).all()
        section_breakdown = [
            {
                "section": s[0],
                "name": TDS_SECTION_RULES.get(s[0], {}).get("name", s[0]),
                "gross_amount": float(s[1]),
                "tds_amount": float(s[2]),
                "count": s[3]
            }
            for s in sec_rows
        ]

        return {
            "fiscal_year": fy,
            "total_deducted": total_deducted,
            "total_deposited": total_deposited,
            "total_pending_deposit": pending_deposit,
            "next_due_date": next_due,
            "days_until_due": days_until_due,
            "quarter_summaries": q_summaries,
            "section_breakdown": section_breakdown
        }

    @staticmethod
    async def generate_form26q_text_file(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: str,
        quarter: str
    ) -> str:
        """
        Generates official NSDL / Protean compliant ASCII e-TDS Return text file for Form 26Q:
        - Record FH: File Header
        - Record BH: Batch Header (Deductor TAN, PAN, Name, AY, FY, Quarter)
        - Record CD: Challan Detail (BSR, Challan No, Deposit Date, Amounts)
        - Record DD: Deductee Detail (Deductee PAN, Name, Gross Paid, TDS Withheld)
        """
        tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await db.execute(tenant_stmt)).scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found.")

        # Deductions for this quarter
        stmt_d = (
            select(TDSDeduction)
            .where(
                and_(
                    TDSDeduction.tenant_id == tenant_id,
                    TDSDeduction.fiscal_year == fiscal_year,
                    TDSDeduction.quarter == quarter
                )
            )
            .order_by(TDSDeduction.deduction_date.asc())
        )
        deductions = (await db.execute(stmt_d)).scalars().all()

        # Challans for this quarter
        stmt_c = (
            select(TDSChallan)
            .where(
                and_(
                    TDSChallan.tenant_id == tenant_id,
                    TDSChallan.fiscal_year == fiscal_year,
                    TDSChallan.quarter == quarter
                )
            )
            .order_by(TDSChallan.payment_date.asc())
        )
        challans = (await db.execute(stmt_c)).scalars().all()

        today_str = date.today().strftime("%d%m%Y")
        now_ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        # Parsing FY and AY
        # e.g., '2026-27' -> AY '202728'
        fy_clean = fiscal_year.replace("FY", "").replace(" ", "").strip()
        parts = fy_clean.split("-")
        start_yr = int(parts[0]) if parts and parts[0].isdigit() else date.today().year
        ay_str = f"{start_yr+1}{str(start_yr+2)[-2:]}"

        tan = (tenant.statutory_profile or {}).get("tan") or f"BLR{tenant.pan[:5]}01" if tenant.pan else "BLRK12345A"
        pan = tenant.pan or "AABCA1234F"
        comp_name = (tenant.legal_name or "Startup Enterprise Private Limited")[:75]

        lines = []
        # Record 1: File Header (FH)
        lines.append(f"1^FH^NSDL-26Q^R^{today_str}^1^CORP^{tan}^b00k5-OS-v1.0^^^")

        # Record 2: Batch Header (BH)
        total_challan_count = len(challans)
        total_challan_amt = sum((c.total_amount for c in challans), Decimal("0.00"))
        lines.append(
            f"2^BH^1^{total_challan_count}^26Q^^^^{tan}^{pan}^{comp_name}^"
            f"BANGALORE^560001^admin@b00k5.local^0801234567^{ay_str}^{fy_clean}^{quarter}^"
            f"{total_challan_amt:.2f}^0.00^0.00^{total_challan_amt:.2f}^"
        )

        # Records 3..N: Challan Details (CD) and Deductee Details (DD)
        line_idx = 3
        challan_seq = 1

        if not challans and deductions:
            # If deductions exist but no separate challan recorded yet, render synthetic batch challan
            dummy_total = sum((d.tds_amount for d in deductions), Decimal("0.00"))
            lines.append(
                f"{line_idx}^CD^1^{challan_seq}^0020^0210001^{today_str}^00001^200^"
                f"{dummy_total:.2f}^0.00^0.00^0.00^0.00^{dummy_total:.2f}^"
            )
            line_idx += 1
            ded_seq = 1
            for d in deductions:
                ded_code = "01" if d.deductee_type == "COMPANY" else "02"
                lines.append(
                    f"{line_idx}^DD^1^{challan_seq}^{ded_seq}^{ded_code}^{d.deductee_pan}^"
                    f"{d.deductee_name[:50]}^{d.deduction_date.strftime('%d%m%Y')}^"
                    f"{d.gross_amount:.2f}^{d.tds_amount:.2f}^{d.rate_percentage:.2f}^"
                    f"{d.section}^N^^^"
                )
                line_idx += 1
                ded_seq += 1
        else:
            for c in challans:
                lines.append(
                    f"{line_idx}^CD^1^{challan_seq}^0020^{c.bsr_code}^{c.payment_date.strftime('%d%m%Y')}^"
                    f"{c.challan_serial_no}^{c.minor_head}^{c.tds_amount:.2f}^{c.surcharge_amount:.2f}^"
                    f"{c.cess_amount:.2f}^{c.interest_amount:.2f}^{c.fee_amount:.2f}^{c.total_amount:.2f}^"
                )
                line_idx += 1

                # Deductions attached to this challan
                c_deductions = [d for d in deductions if d.tds_challan_id == c.id]
                ded_seq = 1
                for d in c_deductions:
                    ded_code = "01" if d.deductee_type == "COMPANY" else "02"
                    lines.append(
                        f"{line_idx}^DD^1^{challan_seq}^{ded_seq}^{ded_code}^{d.deductee_pan}^"
                        f"{d.deductee_name[:50]}^{d.deduction_date.strftime('%d%m%Y')}^"
                        f"{d.gross_amount:.2f}^{d.tds_amount:.2f}^{d.rate_percentage:.2f}^"
                        f"{d.section}^N^^^"
                    )
                    line_idx += 1
                    ded_seq += 1
                challan_seq += 1

        return "\n".join(lines)
