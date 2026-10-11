from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import uuid


class ComplianceWatchdogService:
    @staticmethod
    async def seed_initial_statutory_milestones(
        session,
        tenant_id: uuid.UUID,
        incorporation_date: Optional[date] = None
    ):
        """
        Seeds standard Indian statutory compliance obligations under the Companies Act 2013 and GST Act.
        """
        from app.models.compliance import ComplianceEvent
        today = date.today()
        inc_date = incorporation_date or today
        events = []

        # 1. INC-20A: Declaration for Commencement of Business (within 180 days of incorporation)
        inc20a_due = inc_date + timedelta(days=180)
        events.append(ComplianceEvent(
            tenant_id=tenant_id,
            category="inc_20a",
            title="Form INC-20A: Commencement of Business",
            description="Mandatory filing under Section 10A within 180 days of incorporation confirming subscription money deposited.",
            due_date=inc20a_due,
            statutory_reference="Companies Act 2013 Sec 10A",
            fine_per_day_inr=Decimal("100.00"),
            status="upcoming" if inc20a_due >= today else "overdue"
        ))

        # 2. Section 173: 120-Day Board Meeting Interval Watchdog
        bm_due = inc_date + timedelta(days=120)
        events.append(ComplianceEvent(
            tenant_id=tenant_id,
            category="board_meeting_120d",
            title="Statutory Board Meeting (120-Day Rule)",
            description="Under Section 173(1), not more than 120 days shall intervene between two consecutive board meetings.",
            due_date=bm_due,
            statutory_reference="Companies Act 2013 Sec 173(1)",
            fine_per_day_inr=Decimal("100.00"),
            status="upcoming" if bm_due >= today else "overdue"
        ))

        # 3. DIR-3 KYC: Annual Director KYC (September 30)
        current_year = today.year
        kyc_due = date(current_year, 9, 30)
        if kyc_due < today:
            kyc_due = date(current_year + 1, 9, 30)
        events.append(ComplianceEvent(
            tenant_id=tenant_id,
            category="dir3_kyc",
            title="Form DIR-3 KYC (Director KYC Filing)",
            description="Annual verification of Director Mobile & Email. Late fee is flat ₹5,000 + DIN deactivation.",
            due_date=kyc_due,
            statutory_reference="Rule 12A of Companies (Appointment & Qualification) Rules",
            fine_per_day_inr=Decimal("50.00"),
            status="upcoming"
        ))

        # 4. Form AOC-4: Filing Financial Statements (30 days from AGM, Oct 30)
        aoc4_due = date(current_year, 10, 30)
        if aoc4_due < today:
            aoc4_due = date(current_year + 1, 10, 30)
        events.append(ComplianceEvent(
            tenant_id=tenant_id,
            category="aoc_4",
            title="Form AOC-4: Annual Financial Statements",
            description="Filing of audited Balance Sheet, P&L, and Board Report. Late fees accrue at ₹100 per day indefinitely.",
            due_date=aoc4_due,
            statutory_reference="Companies Act 2013 Sec 137",
            fine_per_day_inr=Decimal("100.00"),
            status="upcoming"
        ))

        # 5. Form MGT-7: Annual Return (60 days from AGM, Nov 29)
        mgt7_due = date(current_year, 11, 29)
        if mgt7_due < today:
            mgt7_due = date(current_year + 1, 11, 29)
        events.append(ComplianceEvent(
            tenant_id=tenant_id,
            category="mgt_7",
            title="Form MGT-7 / MGT-7A: Annual Return",
            description="Annual disclosure of shareholding pattern, directors, and indebtedness. Accrues ₹100/day penalty.",
            due_date=mgt7_due,
            statutory_reference="Companies Act 2013 Sec 92(4)",
            fine_per_day_inr=Decimal("100.00"),
            status="upcoming"
        ))

        # 6. Form ITR-6: Corporate Income Tax Return (Sec 139(1), Oct 31)
        itr_due = date(current_year, 10, 31)
        if itr_due < today:
            itr_due = date(current_year + 1, 10, 31)
        events.append(ComplianceEvent(
            tenant_id=tenant_id,
            category="itr_filing",
            title="Form ITR-6: Corporate Income Tax Return",
            description="Annual Corporate Income Tax Return filing under Section 139(1). Late filing fees accrue under Section 234F.",
            due_date=itr_due,
            statutory_reference="Income Tax Act 1961 Sec 139(1)",
            fine_per_day_inr=Decimal("50.00"),
            status="upcoming"
        ))

        # 6. GSTR-3B: Monthly Summary Return (20th of upcoming month)
        if today.day <= 20:
            gst_due = date(today.year, today.month, 20)
        else:
            next_month = today.month + 1 if today.month < 12 else 1
            next_year = today.year if today.month < 12 else today.year + 1
            gst_due = date(next_year, next_month, 20)
        events.append(ComplianceEvent(
            tenant_id=tenant_id,
            category="gstr_3b",
            title="GSTR-3B Monthly Return & Tax Payment",
            description="Summary of outward supplies, input tax credit claimed, and net GST liability deposited.",
            due_date=gst_due,
            statutory_reference="CGST Act 2017 Sec 39",
            fine_per_day_inr=Decimal("50.00"),
            status="upcoming"
        ))

        session.add_all(events)
        await session.flush()
        return events

    @staticmethod
    def calculate_event_metrics(event: Any, today: date) -> Dict[str, Any]:
        delta_days = (event.due_date - today).days
        is_completed = event.status == "completed"

        if is_completed:
            status = "completed"
            accumulated_penalty = Decimal("0.00")
        elif delta_days < 0:
            status = "overdue"
            overdue_days = abs(delta_days)
            accumulated_penalty = event.fine_per_day_inr * Decimal(str(overdue_days))
        elif delta_days <= 15:
            status = "due_soon"
            accumulated_penalty = Decimal("0.00")
        else:
            status = "upcoming"
            accumulated_penalty = Decimal("0.00")

        return {
            "id": event.id,
            "tenant_id": event.tenant_id,
            "category": event.category,
            "title": event.title,
            "description": event.description,
            "due_date": event.due_date,
            "days_remaining": delta_days,
            "statutory_reference": event.statutory_reference,
            "fine_per_day_inr": event.fine_per_day_inr,
            "accumulated_penalty_inr": accumulated_penalty,
            "status": status,
            "completed_at": event.completed_at,
            "document_id": event.document_id,
            "created_at": event.created_at
        }

    @staticmethod
    def evaluate_board_meeting_cadence(
        last_meeting_date: Optional[date] = None,
        today: Optional[date] = None,
        entity_type: str = "private_limited",
        director_count: int = 2,
        incorporation_date: Optional[date] = None,
        previous_meeting_in_half_year: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Section 173(1) & Section 173(5) Compliance Evaluator (UAT-10):
        - OPC with 1 Director: Exempt from Section 173 board meeting cadence under Sec 173(5) Proviso.
        - OPC (>1 Director), Small Company, DPIIT Startup, Section 8, Dormant: Sec 173(5) applies ->
          1 meeting in each half of calendar year with a minimum gap of >= 90 days between the two meetings.
        - Newly Incorporated Company (no prior meeting): First board meeting required within 30 days of incorporation.
        - Standard Private/Public Limited Company: Max 120-day gap between consecutive board meetings (4 per year).
        """
        curr_date = today or date.today()
        norm_entity = (entity_type or "private_limited").lower().strip()

        # 1. OPC with single director exemption (Section 173(5) Proviso)
        if norm_entity in ("opc", "opc_single_director") and director_count == 1:
            return {
                "status": "exempt_opc_single_director",
                "entity_type": norm_entity,
                "days_elapsed": 0,
                "days_remaining": 365,
                "is_violation": False,
                "warning_level": "EXEMPT",
                "penalty_inr": Decimal("0.00"),
                "rule_version": "CA2013-SEC173-5-PROVISO-V2026.1",
                "statutory_reference": "Companies Act 2013 Sec 173(5) Proviso",
                "message": "Exempt: One Person Company (OPC) with a single director is exempt from Section 173 board meeting interval requirements."
            }

        # 2. First Board Meeting within 30 days of incorporation (if no meeting held yet)
        if last_meeting_date is None and incorporation_date is not None:
            days_since_inc = (curr_date - incorporation_date).days
            days_rem_first = 30 - days_since_inc
            is_viol = days_since_inc > 30
            return {
                "status": "statutory_violation" if is_viol else "compliant",
                "entity_type": norm_entity,
                "days_elapsed": days_since_inc,
                "days_remaining": days_rem_first,
                "first_meeting_deadline": incorporation_date + timedelta(days=30),
                "is_violation": is_viol,
                "warning_level": "CRITICAL" if is_viol else "NORMAL",
                "penalty_inr": Decimal(str(max(0, days_since_inc - 30) * 100)),
                "rule_version": "CA2013-SEC173-1-FIRST-BM-30D",
                "statutory_reference": "Companies Act 2013 Sec 173(1) (First Board Meeting within 30 days)",
                "message": (
                    f"First Board Meeting overdue by {days_since_inc - 30} days (incorporation: {incorporation_date})."
                    if is_viol else f"First Board Meeting due within {days_rem_first} days of incorporation."
                )
            }

        # 3. Small Company / OPC (>1 director) / DPIIT Startup / Section 8 (Sec 173(5): 1 per half-calendar-year, >= 90 days gap)
        if norm_entity in ("opc", "small_company", "dpiit_startup", "section_8", "dormant"):
            ref_date = last_meeting_date or incorporation_date or curr_date
            gap_days = (curr_date - ref_date).days
            same_half_year = (curr_date.year == ref_date.year) and ((curr_date.month <= 6) == (ref_date.month <= 6))
            min_gap_met = gap_days >= 90
            is_viol = (not same_half_year) and (gap_days > 275)
            return {
                "status": "statutory_violation" if is_viol else ("compliant" if min_gap_met or same_half_year else "min_gap_pending"),
                "entity_type": norm_entity,
                "days_elapsed": gap_days,
                "min_gap_required_days": 90,
                "min_gap_satisfied": min_gap_met,
                "is_violation": is_viol,
                "warning_level": "CRITICAL" if is_viol else "NORMAL",
                "penalty_inr": Decimal("0.00") if not is_viol else Decimal("25000.00"),
                "rule_version": "CA2013-SEC173-5-SMALL-OPC-90D",
                "statutory_reference": "Companies Act 2013 Sec 173(5)",
                "message": "Section 173(5) regime: 1 board meeting in each half of calendar year with minimum 90-day gap."
            }

        # 4. Standard Private / Public Limited Company (Max 120-day gap)
        ref_meeting = last_meeting_date or incorporation_date or curr_date
        days_elapsed = (curr_date - ref_meeting).days
        days_remaining = 120 - days_elapsed
        fine_per_day = Decimal("100.00")

        if days_elapsed > 120:
            overdue_days = days_elapsed - 120
            penalty = fine_per_day * Decimal(str(overdue_days))
            return {
                "status": "statutory_violation",
                "entity_type": norm_entity,
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "is_violation": True,
                "warning_level": "CRITICAL",
                "penalty_inr": penalty,
                "rule_version": "CA2013-SEC173-1-120D",
                "statutory_reference": "Companies Act 2013 Sec 173(1)",
                "message": f"Statutory Violation: {days_elapsed} days elapsed since last Board Meeting (exceeds 120-day limit by {overdue_days} days). Accruing ₹{penalty} penalty."
            }
        elif days_elapsed > 100:
            return {
                "status": "warning_due_soon",
                "entity_type": norm_entity,
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "is_violation": False,
                "warning_level": "WARNING",
                "penalty_inr": Decimal("0.00"),
                "rule_version": "CA2013-SEC173-1-120D",
                "statutory_reference": "Companies Act 2013 Sec 173(1)",
                "message": f"Board Meeting Warning: {days_elapsed} days elapsed (> 100 days). Meeting must be convened within {days_remaining} days."
            }
        else:
            return {
                "status": "compliant",
                "entity_type": norm_entity,
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "is_violation": False,
                "warning_level": "NORMAL",
                "penalty_inr": Decimal("0.00"),
                "rule_version": "CA2013-SEC173-1-120D",
                "statutory_reference": "Companies Act 2013 Sec 173(1)",
                "message": f"Compliant: {days_remaining} days remaining before Section 173 limit."
            }

    @staticmethod
    def calculate_statutory_calendar(
        financial_year_end: date,
        incorporation_date: Optional[date] = None,
        is_first_agm: bool = False
    ) -> Dict[str, Any]:
        """
        Computes statutory deadlines under Companies Act 2013:
        - First AGM (Sec 96(1) Proviso): within 9 months of first FY close -> Dec 31
        - Subsequent AGM (Sec 96(1)): within 6 months of FY end -> Sep 30
        - AOC-4 (Sec 137): within 30 days of AGM
        - MGT-7 (Sec 92): within 60 days of AGM
        - DIR-3 KYC: cutoff Sep 30
        """
        year = financial_year_end.year
        agm_deadline = date(year, 12, 31) if is_first_agm else date(year, 9, 30)
        aoc4_deadline = agm_deadline + timedelta(days=30)
        mgt7_deadline = agm_deadline + timedelta(days=60)
        dir3_kyc_deadline = date(year, 9, 30)

        return {
            "financial_year_end": financial_year_end,
            "incorporation_date": incorporation_date,
            "is_first_agm": is_first_agm,
            "agm_deadline": agm_deadline,
            "aoc4_filing_deadline": aoc4_deadline,
            "mgt7_filing_deadline": mgt7_deadline,
            "dir3_kyc_deadline": dir3_kyc_deadline,
            "agm_reference": "Companies Act 2013 Sec 96(1)",
            "aoc4_reference": "Companies Act 2013 Sec 137",
            "mgt7_reference": "Companies Act 2013 Sec 92(4)",
            "dir3_kyc_reference": "Rule 12A MCA Qualification Rules"
        }

    @staticmethod
    def evaluate_gst_place_of_supply(
        supplier_state_code: str,
        recipient_state_code: Optional[str] = None,
        place_of_supply_code: Optional[str] = None,
        supply_type: str = "standard_b2b",
        property_location_state_code: Optional[str] = None,
        is_export: bool = False,
        is_sez_unit: bool = False,
        is_reverse_charge: bool = False,
        has_lut_bond: bool = False
    ) -> Dict[str, Any]:
        """
        UAT-08 & Section 7 GST Place of Supply (POS) & Tax Treatment Engine (IGST Act Sec 10, 12, 13, 16):
        Determines tax regime across intrastate, interstate, export, SEZ, reverse-charge (RCM),
        and immovable-property/hotel location-specific supplies.
        """
        sup_state = (supplier_state_code or "").strip()
        if is_export or is_sez_unit:
            return {
                "tax_regime": "ZERO_RATED_EXPORT_LUT" if has_lut_bond else "IGST_EXPORT_WITH_REBATE",
                "is_interstate": True,
                "effective_pos": "96" if is_export else (recipient_state_code or "97"),
                "cgst_applicable": False,
                "sgst_applicable": False,
                "igst_applicable": not has_lut_bond,
                "reverse_charge_applicable": False,
                "requires_manual_review": False,
                "statutory_reference": "IGST Act 2017 Sec 16 (Zero-Rated Supply)"
            }

        # Section 12(3) IGST Act: Immovable property / Hotel accommodation -> POS is location of property
        if supply_type in ("hotel_accommodation", "immovable_property", "event_venue") and property_location_state_code:
            effective_pos = property_location_state_code.strip()
        else:
            effective_pos = (place_of_supply_code or recipient_state_code or "").strip()

        if not effective_pos or len(effective_pos) != 2:
            return {
                "tax_regime": "UNCERTAIN_POS_REVIEW_REQUIRED",
                "is_interstate": False,
                "effective_pos": effective_pos or None,
                "cgst_applicable": False,
                "sgst_applicable": False,
                "igst_applicable": False,
                "reverse_charge_applicable": is_reverse_charge,
                "requires_manual_review": True,
                "statutory_reference": "IGST Act 2017 Sec 12"
            }

        is_inter = effective_pos != sup_state
        return {
            "tax_regime": "IGST_INTERSTATE" if is_inter else "CGST_SGST_INTRASTATE",
            "is_interstate": is_inter,
            "effective_pos": effective_pos,
            "cgst_applicable": not is_inter,
            "sgst_applicable": not is_inter,
            "igst_applicable": is_inter,
            "reverse_charge_applicable": is_reverse_charge,
            "requires_manual_review": (
                supply_type in ("hotel_accommodation", "immovable_property")
                and recipient_state_code is not None
                and effective_pos != recipient_state_code
            ),
            "statutory_reference": "IGST Act 2017 Sec 12(3)" if property_location_state_code else "IGST Act 2017 Sec 12(2)"
        }

    @staticmethod
    def evaluate_gst_itc_eligibility(
        tenant_gstin: str,
        supplier_gstin: Optional[str],
        recipient_gstin_on_invoice: Optional[str],
        invoice_number: Optional[str],
        invoice_date: Optional[date],
        place_of_supply: Optional[str],
        expense_category: str = "general",
        gstr2b_verified: bool = False,
        charged_cgst_sgst_from_other_state: bool = False
    ) -> Dict[str, Any]:
        """
        UAT-09 & Section 4 Multi-Factor GST Input Tax Credit (ITC) Eligibility Engine (CGST Act Sec 16(2) & Sec 17(5)):
        Never approves ITC based solely on GSTIN substring presence.
        """
        import re
        gstin_regex = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
        t_gstin = (tenant_gstin or "").strip().upper()
        s_gstin = (supplier_gstin or "").strip().upper()
        r_gstin = (recipient_gstin_on_invoice or "").strip().upper()
        cat_norm = (expense_category or "").lower().strip()

        reasons = []
        if not s_gstin or not gstin_regex.match(s_gstin):
            reasons.append("Missing or invalid 15-character Supplier GSTIN.")
        if not r_gstin:
            reasons.append("Missing Recipient GSTIN on tax invoice (B2C invoice ineligible for ITC u/s 16(2)).")
        elif not gstin_regex.match(r_gstin):
            reasons.append(f"Malformed or truncated Recipient GSTIN '{r_gstin}'.")
        elif r_gstin != t_gstin:
            reasons.append(f"Recipient GSTIN '{r_gstin}' does not match Tenant GSTIN '{t_gstin}'.")
        if not invoice_number or not invoice_date:
            reasons.append("Missing statutory Tax Invoice Number or Invoice Date u/s 16(2)(a).")

        # Section 17(5) Blocked Credit check
        blocked_categories = {
            "food_beverages", "catering", "club_membership", "health_fitness",
            "personal_consumption", "motor_vehicle_non_eligible", "gifts_free_samples"
        }
        if cat_norm in blocked_categories or any(b in cat_norm for b in ("food", "restaurant", "catering", "club", "personal")):
            reasons.append("Blocked Credit under Section 17(5) of the CGST Act, 2017.")

        # Out-of-state hotel / immovable property charging local CGST/SGST of another state
        tenant_state = t_gstin[:2] if len(t_gstin) >= 2 else ""
        if charged_cgst_sgst_from_other_state or (place_of_supply and tenant_state and place_of_supply != tenant_state and s_gstin[:2] == place_of_supply):
            if "hotel" in cat_norm or "accommodation" in cat_norm or charged_cgst_sgst_from_other_state:
                reasons.append("Location-specific out-of-state CGST+SGST (Sec 12(3) IGST Act) cannot be claimed in home state.")

        if reasons:
            return {
                "itc_eligible": False,
                "itc_status": "INELIGIBLE",
                "requires_review": True,
                "reasons": reasons,
                "statutory_reference": "CGST Act 2017 Sec 16(2) / Sec 17(5)"
            }

        if not gstr2b_verified:
            return {
                "itc_eligible": False,
                "itc_status": "PROVISIONAL_PENDING_GSTR2B",
                "requires_review": True,
                "reasons": ["Invoice details valid, but final ITC claim requires GSTR-2B reflection under Sec 16(2)(aa)."],
                "statutory_reference": "CGST Act 2017 Sec 16(2)(aa)"
            }

        return {
            "itc_eligible": True,
            "itc_status": "ELIGIBLE_VERIFIED",
            "requires_review": False,
            "reasons": [],
            "statutory_reference": "CGST Act 2017 Sec 16(2)"
        }

    @staticmethod
    def evaluate_cash_payment_disallowance(
        payments_in_day: List[Dict[str, Any]],
        is_goods_carriage: bool = False,
        rule_6dd_exemption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Section 4 & Section 7 Cash-Payment Disallowance Engine (Sec 40A(3) IT Act 1961 / IT Act 2025):
        Aggregates split cash payments made to a single person in a single day.
        - Standard threshold: ₹10,000 per payee per day.
        - Goods carriage (plying, hiring, leasing): ₹35,000 per payee per day.
        - Rule 6DD exemptions (e.g. government challans, RBI/scheduled bank payments, agricultural produce) are exempt.
        """
        threshold = Decimal("35000.00") if is_goods_carriage else Decimal("10000.00")
        valid_6dd = {"government_tax_challan", "rbi_scheduled_bank", "agricultural_produce", "bank_holiday"}

        cash_total = Decimal("0.00")
        for p in payments_in_day:
            mode = (p.get("payment_mode") or "cash").lower()
            if mode in ("cash", "bearer_cheque", "crossed_cheque_non_account_payee"):
                cash_total += Decimal(str(p.get("amount", "0.00")))

        if rule_6dd_exemption and rule_6dd_exemption.lower() in valid_6dd:
            return {
                "aggregate_cash_paid": cash_total,
                "threshold_limit": threshold,
                "is_disallowed": False,
                "disallowed_amount": Decimal("0.00"),
                "rule_6dd_exempt": True,
                "statutory_reference": f"Rule 6DD ({rule_6dd_exemption})"
            }

        is_disallowed = cash_total > threshold
        return {
            "aggregate_cash_paid": cash_total,
            "threshold_limit": threshold,
            "is_disallowed": is_disallowed,
            "disallowed_amount": cash_total if is_disallowed else Decimal("0.00"),
            "rule_6dd_exempt": False,
            "statutory_reference": "Income-tax Act Sec 40A(3) / IT Act 2025 Equivalent"
        }

    @staticmethod
    def evaluate_director_balance_dpt3(
        balance_amount: Decimal,
        source_type: str = "unpaid_reimbursement",
        has_own_funds_declaration: bool = False,
        has_board_resolution: bool = False,
        is_explicitly_classified_as_loan: bool = False
    ) -> Dict[str, Any]:
        """
        Section 4 Director Balances & Form DPT-3 Classification Engine:
        Never automatically reclassifies an unpaid reimbursement into an exempt director loan at year-end.
        Requires explicit classification, signed Rule 2(1)(c)(viii) declaration of non-borrowed own funds,
        and Board Resolution.
        """
        if not is_explicitly_classified_as_loan:
            return {
                "classification": "unclassified_director_reimbursement_payable",
                "exempt_from_deposit_rules": False,
                "dpt3_reporting_status": "REVIEW_REQUIRED_NOT_AUTO_CONVERTED",
                "requires_legal_review": True,
                "missing_documents": [
                    doc for doc, present in [
                        ("Rule 2(1)(c)(viii) Own-Funds Declaration", has_own_funds_declaration),
                        ("Section 179(3)(d) Board Resolution", has_board_resolution)
                    ] if not present
                ],
                "statutory_reference": "Companies (Acceptance of Deposits) Rules, 2014 Rule 2(1)(c)(viii)"
            }

        if not (has_own_funds_declaration and has_board_resolution):
            return {
                "classification": "invalid_director_loan_missing_declaration",
                "exempt_from_deposit_rules": False,
                "dpt3_reporting_status": "DEPOSIT_VIOLATION_RISK_MISSING_DECLARATION",
                "requires_legal_review": True,
                "missing_documents": [
                    doc for doc, present in [
                        ("Rule 2(1)(c)(viii) Own-Funds Declaration", has_own_funds_declaration),
                        ("Section 179(3)(d) Board Resolution", has_board_resolution)
                    ] if not present
                ],
                "statutory_reference": "Companies Act 2013 Sec 73 & Rule 2(1)(c)(viii)"
            }

        return {
            "classification": "exempt_director_unsecured_loan",
            "exempt_from_deposit_rules": True,
            "dpt3_reporting_status": "REPORTABLE_UNDER_DPT3_EXEMPT_PARTICULARS",
            "requires_legal_review": False,
            "missing_documents": [],
            "statutory_reference": "Companies (Acceptance of Deposits) Rules, 2014 Rule 2(1)(c)(viii) & Rule 16 (Form DPT-3)"
        }

    @staticmethod
    def calculate_form_specific_penalty(
        form_code: str,
        overdue_days: int,
        entity_type: str = "private_limited",
        tax_or_tds_amount: Decimal = Decimal("0.00"),
        is_nil_return: bool = False
    ) -> Dict[str, Any]:
        """
        Section 4 Form-Specific Penalty & Cap Engine (with Section 446B Small Company / OPC Relief):
        Replaces universal ₹100/day assumption with form-specific daily rates, caps, and statutory citations.
        """
        days = max(0, int(overdue_days))
        code = (form_code or "").upper().strip()
        is_small_or_opc = (entity_type or "").lower() in ("opc", "small_company", "dpiit_startup")

        if code in ("AOC-4", "MGT-7", "MGT-7A"):
            raw_penalty = Decimal(str(days * 100))
            if is_small_or_opc:
                # Section 446B: 50% of normal penalty, capped at ₹2,00,000 for company
                effective_penalty = min(raw_penalty * Decimal("0.50"), Decimal("200000.00"))
                ref = "Companies Act 2013 Sec 92(5)/137(3) read with Sec 446B (Small/OPC Relief)"
            else:
                effective_penalty = raw_penalty
                ref = "Companies Act 2013 Sec 92(4)/137(1) (₹100/day)"
            return {"form_code": code, "overdue_days": days, "penalty_inr": effective_penalty, "statutory_reference": ref}

        if code in ("24Q", "26Q", "27Q", "TDS_234E"):
            # Section 234E: ₹200/day capped at total TDS amount
            raw_fee = Decimal(str(days * 200))
            capped_fee = min(raw_fee, tax_or_tds_amount) if tax_or_tds_amount > 0 else raw_fee
            return {
                "form_code": code,
                "overdue_days": days,
                "penalty_inr": capped_fee,
                "cap_applied": capped_fee < raw_fee,
                "statutory_reference": "Income-tax Act Sec 234E (₹200/day capped at TDS deductible)"
            }

        if code in ("GSTR-3B", "GSTR-1"):
            daily_rate = Decimal("20.00") if is_nil_return else Decimal("50.00")
            cap = Decimal("500.00") if is_nil_return else Decimal("5000.00")
            fee = min(Decimal(str(days)) * daily_rate, cap)
            return {
                "form_code": code,
                "overdue_days": days,
                "penalty_inr": fee,
                "statutory_reference": "CGST Act 2017 Sec 47 (Notification 19/2021-CT Capped Late Fee)"
            }

        if code == "DIR-3-KYC":
            return {
                "form_code": code,
                "overdue_days": days,
                "penalty_inr": Decimal("5000.00") if days > 0 else Decimal("0.00"),
                "statutory_reference": "Companies (Registration Offices and Fees) Rules (Flat ₹5,000 after due date)"
            }

        return {
            "form_code": code,
            "overdue_days": days,
            "penalty_inr": Decimal(str(days * 100)),
            "statutory_reference": "Companies Act 2013 General Filing Provision"
        }

    @staticmethod
    def validate_board_minutes_and_dsc(
        meeting_payload: Dict[str, Any],
        dsc_result: Dict[str, Any],
        authorized_director_dins: List[str]
    ) -> Dict[str, Any]:
        """
        UAT-12 & Section 4 DSC and Board Minutes Governance Validator (SS-1 & Sec 118):
        Validates notice period (>= 7 days or shorter notice consent), quorum (>= 1/3 or 2 directors,
        or 1 for single-director OPC), signer DIN authorization, and explicitly separates
        SIMULATED vs HARDWARE_VERIFIED cryptographic signatures.
        """
        errors = []
        notice_days = int(meeting_payload.get("notice_days", 7))
        shorter_notice_consent = bool(meeting_payload.get("shorter_notice_consent", False))
        total_directors = int(meeting_payload.get("total_directors", 2))
        directors_present = meeting_payload.get("directors_present", [])
        signer_din = str(dsc_result.get("signer_din") or meeting_payload.get("signer_din") or "").strip()
        is_simulated = bool(dsc_result.get("simulation", False) or dsc_result.get("is_simulated", False))

        if notice_days < 7 and not shorter_notice_consent:
            errors.append("SS-1 Clause 1.3.7 Violation: Less than 7 days notice without recorded shorter-notice consent.")

        required_quorum = 1 if total_directors == 1 else max(2, (total_directors + 2) // 3)
        if len(directors_present) < required_quorum:
            errors.append(f"Section 174 Quorum Failure: {len(directors_present)} present, minimum {required_quorum} required.")

        if authorized_director_dins and signer_din not in authorized_director_dins:
            errors.append(f"Unauthorized Signer DIN '{signer_din}': Not in active authorized director roster.")

        sig_mode = "SIMULATED_DEV_MOCK" if is_simulated else "HARDWARE_PKCS11_VERIFIED"
        return {
            "governance_valid": len(errors) == 0,
            "is_simulated_signature": is_simulated,
            "signature_mode": sig_mode,
            "legal_filing_ready": (len(errors) == 0) and (not is_simulated),
            "watermark_required": "SIMULATED SIGNATURE - NOT VALID FOR STATUTORY FILING" if is_simulated else None,
            "errors": errors,
            "statutory_reference": "ICSI Secretarial Standard SS-1 & Companies Act 2013 Sec 118 / Sec 174"
        }


