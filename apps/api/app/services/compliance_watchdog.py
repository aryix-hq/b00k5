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
    def evaluate_board_meeting_cadence(last_meeting_date: date, today: Optional[date] = None) -> Dict[str, Any]:
        """
        Section 173(1) Compliance Evaluator:
        Not more than 120 days shall intervene between two consecutive board meetings.
        - Warning raised if > 100 days elapsed.
        - Statutory violation flagged if > 120 days elapsed.
        """
        curr_date = today or date.today()
        days_elapsed = (curr_date - last_meeting_date).days
        days_remaining = 120 - days_elapsed
        fine_per_day = Decimal("100.00")

        if days_elapsed > 120:
            overdue_days = days_elapsed - 120
            penalty = fine_per_day * Decimal(str(overdue_days))
            return {
                "status": "statutory_violation",
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "is_violation": True,
                "warning_level": "CRITICAL",
                "penalty_inr": penalty,
                "statutory_reference": "Companies Act 2013 Sec 173(1)",
                "message": f"Statutory Violation: {days_elapsed} days elapsed since last Board Meeting (exceeds 120-day limit by {overdue_days} days). Accruing ₹{penalty} penalty."
            }
        elif days_elapsed > 100:
            return {
                "status": "warning_due_soon",
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "is_violation": False,
                "warning_level": "WARNING",
                "penalty_inr": Decimal("0.00"),
                "statutory_reference": "Companies Act 2013 Sec 173(1)",
                "message": f"Board Meeting Warning: {days_elapsed} days elapsed (> 100 days). Meeting must be convened within {days_remaining} days."
            }
        else:
            return {
                "status": "compliant",
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "is_violation": False,
                "warning_level": "NORMAL",
                "penalty_inr": Decimal("0.00"),
                "statutory_reference": "Companies Act 2013 Sec 173(1)",
                "message": f"Compliant: {days_remaining} days remaining before Section 173 limit."
            }

    @staticmethod
    def calculate_statutory_calendar(financial_year_end: date) -> Dict[str, Any]:
        """
        Computes statutory deadlines under Companies Act 2013:
        - AGM (Sec 96): within 6 months of FY end -> Sep 30
        - AOC-4 (Sec 137): within 30 days of AGM -> Oct 30
        - MGT-7 (Sec 92): within 60 days of AGM -> Nov 29
        - DIR-3 KYC: cutoff Sep 30
        """
        year = financial_year_end.year
        agm_deadline = date(year, 9, 30)
        aoc4_deadline = date(year, 10, 30)
        mgt7_deadline = date(year, 11, 29)
        dir3_kyc_deadline = date(year, 9, 30)

        return {
            "financial_year_end": financial_year_end,
            "agm_deadline": agm_deadline,
            "aoc4_filing_deadline": aoc4_deadline,
            "mgt7_filing_deadline": mgt7_deadline,
            "dir3_kyc_deadline": dir3_kyc_deadline,
            "agm_reference": "Companies Act 2013 Sec 96",
            "aoc4_reference": "Companies Act 2013 Sec 137",
            "mgt7_reference": "Companies Act 2013 Sec 92(4)",
            "dir3_kyc_reference": "Rule 12A MCA Qualification Rules"
        }

