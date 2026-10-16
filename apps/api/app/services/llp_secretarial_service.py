"""
b00k5 - MCA Secretarial Standards & Compliance Engine for Limited Liability Partnerships (LLPs)
Compliant with:
- Limited Liability Partnership (LLP) Act, 2008
- LLP Rules, 2009: Rule 24 (Form 8 Statement of Account & Solvency) & Rule 25 (Form 11 Annual Return)
- ICSI Secretarial Standards on Meetings of Partners & Governance
"""

import uuid
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Tenant, User, TenantUser
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.schedule_iii_service import ScheduleIIIService

LLPIN_REGEX = re.compile(r'\b([A-Z]{3}-?[0-9]{4})\b')

class LLPSecretarialService:
    """
    Statutory Engine for LLP Compliance, Form 11, Form 8, and Partners Governance.
    """

    @staticmethod
    def is_llp_entity(tenant: Tenant) -> bool:
        """Determines if the tenant is a Limited Liability Partnership."""
        legal_name = (tenant.legal_name or "").upper()
        prof = tenant.statutory_profile or {}
        llpin = prof.get("llpin") or tenant.cin or ""
        entity_type = (prof.get("entity_type") or "").upper()

        if "LLP" in legal_name or "LIMITED LIABILITY PARTNERSHIP" in legal_name:
            return True
        if "LLP" in entity_type:
            return True
        if LLPIN_REGEX.match(llpin):
            return True
        return False

    @staticmethod
    async def get_designated_partners(db: AsyncSession, tenant: Tenant) -> List[Dict[str, Any]]:
        """
        Retrieves Designated Partners and Partners with DPIN, Contribution, and Profit Share.
        """
        prof = tenant.statutory_profile or {}
        mca_partners = prof.get("partners") or prof.get("directors") or []

        stmt = (
            select(User.first_name, User.last_name, User.email, TenantUser.role, TenantUser.din)
            .join(TenantUser, TenantUser.user_id == User.id)
            .where(TenantUser.tenant_id == tenant.id)
        )
        res = await db.execute(stmt)
        rows = res.all()

        partners: List[Dict[str, Any]] = []
        for fn, ln, email, role, din in rows:
            full_name = f"{fn or ''} {ln or ''}".strip()
            # Match against profile if available
            matched_prof = next(
                (p for p in mca_partners if (isinstance(p, dict) and (p.get("din") == din or p.get("name", "").lower() in full_name.lower()))),
                {}
            )
            is_designated = (role and "partner" in role.lower()) or matched_prof.get("is_designated", True)
            dpin = din or matched_prof.get("dpin") or matched_prof.get("din") or "DPIN-PENDING"
            contrib = Decimal(str(matched_prof.get("contribution_inr", "50000.00")))
            profit_share = Decimal(str(matched_prof.get("profit_sharing_ratio", "50.00")))

            partners.append({
                "name": full_name or matched_prof.get("name", "Partner"),
                "email": email,
                "dpin": dpin,
                "role": "Designated Partner" if is_designated else "Partner",
                "is_designated": is_designated,
                "contribution_inr": contrib,
                "profit_sharing_ratio_pct": profit_share
            })

        # Merge remaining statutory partners from profile who are not yet tenant users
        existing_dpins = {p["dpin"] for p in partners if p.get("dpin") and p["dpin"] not in ("N/A", "DPIN-PENDING")}
        existing_names = {p["name"].lower() for p in partners if p.get("name")}
        for p in mca_partners:
            if isinstance(p, dict):
                p_dpin = p.get("dpin") or p.get("din")
                p_name = (p.get("name") or "").strip()
                if (p_dpin and p_dpin not in existing_dpins) or (p_name and p_name.lower() not in existing_names):
                    partners.append({
                        "name": p_name or "Partner",
                        "email": p.get("email", ""),
                        "dpin": p_dpin or "N/A",
                        "role": "Designated Partner" if p.get("is_designated", True) else "Partner",
                        "is_designated": p.get("is_designated", True),
                        "contribution_inr": Decimal(str(p.get("contribution_inr", "50000.00"))),
                        "profit_sharing_ratio_pct": Decimal(str(p.get("profit_sharing_ratio", "50.00")))
                    })

        return partners

    @staticmethod
    async def generate_form11_packet(
        db: AsyncSession,
        tenant: Tenant,
        fy: str = "2025-26"
    ) -> Dict[str, Any]:
        """
        Generates statutory Form 11 (Annual Return of LLP) under Rule 25(1) of LLP Rules, 2009.
        Statutory Due Date: 30th May (within 60 days of FY close).
        """
        prof = tenant.statutory_profile or {}
        llpin = prof.get("llpin") or tenant.cin or "AAA-0000"
        partners = await LLPSecretarialService.get_designated_partners(db, tenant)

        # Calculate turnover from general ledger
        sch_summary = await ScheduleIIIService.get_schedule_iii_summary(db, tenant, fy=fy)
        total_turnover = Decimal(str(sch_summary.get("revenue_statement", {}).get("total_revenue", "0.00")))
        total_contribution = sum(p["contribution_inr"] for p in partners) if partners else Decimal("100000.00")

        # Certification Rule 25(2):
        # Mandatory Company Secretary in Practice certification if turnover > ₹5 Crore or contribution > ₹50 Lakhs
        requires_cs_certification = (total_turnover > Decimal("50000000.00")) or (total_contribution > Decimal("5000000.00"))

        parts = fy.split("-")
        end_year = int(parts[0]) + 1 if len(parts) == 2 else date.today().year
        due_date = date(end_year, 5, 30)
        today = date.today()
        days_remaining = (due_date - today).days

        return {
            "form_name": "Form 11 (Annual Return of Limited Liability Partnership)",
            "statutory_rule": "Rule 25(1) of LLP Rules, 2009 & Section 35 of LLP Act, 2008",
            "llpin": llpin,
            "legal_name": tenant.legal_name,
            "registered_address": tenant.statutory_profile.get("registered_address", "Registered Office Address"),
            "financial_year": fy,
            "statutory_due_date": str(due_date),
            "days_remaining": days_remaining,
            "is_overdue": days_remaining < 0,
            "fine_per_day_inr": Decimal("100.00"),
            "total_turnover_inr": total_turnover,
            "total_partner_contribution_inr": total_contribution,
            "requires_cs_certification": requires_cs_certification,
            "certification_trigger_reason": (
                "Turnover exceeds ₹5 Crore or Contribution exceeds ₹50 Lakhs (Rule 25(2))"
                if requires_cs_certification else
                "Exempt from PCS Certification (Certified by Designated Partners)"
            ),
            "partners_summary": {
                "total_partners": len(partners),
                "designated_partners_count": sum(1 for p in partners if p["is_designated"]),
                "partners_roster": partners
            },
            "declaration_text": (
                f"We, the Designated Partners of {tenant.legal_name}, hereby confirm that the annual return reflects "
                f"a true and fair view of the state of affairs of the LLP for FY {fy} pursuant to Section 35 of the LLP Act, 2008."
            )
        }

    @staticmethod
    async def generate_form8_packet(
        db: AsyncSession,
        tenant: Tenant,
        fy: str = "2025-26"
    ) -> Dict[str, Any]:
        """
        Generates statutory Form 8 (Statement of Account & Solvency) under Rule 24 of LLP Rules, 2009.
        Statutory Due Date: 30th October (within 30 days from end of 6 months of FY).
        Checks Rule 24(8) audit thresholds: Turnover > ₹40 Lakhs or Contribution > ₹25 Lakhs.
        """
        prof = tenant.statutory_profile or {}
        llpin = prof.get("llpin") or tenant.cin or "AAA-0000"
        partners = await LLPSecretarialService.get_designated_partners(db, tenant)

        sch_summary = await ScheduleIIIService.get_schedule_iii_summary(db, tenant, fy=fy)
        total_turnover = Decimal(str(sch_summary.get("revenue_statement", {}).get("total_revenue", "0.00")))
        total_contribution = sum(p["contribution_inr"] for p in partners) if partners else Decimal("100000.00")

        # Mandatory Statutory Audit under Rule 24(8) of LLP Rules 2009:
        # Turnover > ₹40 Lakhs OR Contribution > ₹25 Lakhs
        audit_required = (total_turnover > Decimal("4000000.00")) or (total_contribution > Decimal("2500000.00"))

        parts = fy.split("-")
        end_year = int(parts[0]) + 1 if len(parts) == 2 else date.today().year
        due_date = date(end_year, 10, 30)
        today = date.today()
        days_remaining = (due_date - today).days

        # Part A: Statement of Solvency
        solvency_declaration = {
            "part_a_title": "Part A: Statement of Solvency",
            "solvency_confirmed": True,
            "statutory_declaration": (
                f"We, being the Designated Partners of {tenant.legal_name}, do solemnly declare that we have made a full inquiry into the affairs "
                f"of the LLP, and that, in our opinion, the LLP is able to pay its debts as and when they become due in the normal course of business "
                f"for a period of not less than one year from the date of this statement."
            ),
            "creation_of_charges": prof.get("charges", []),
            "unregistered_partners_loans": False
        }

        # Part B: Statement of Account
        balance_sheet = sch_summary.get("balance_sheet", {})
        revenue_stmt = sch_summary.get("revenue_statement", {})

        statement_of_account = {
            "part_b_title": "Part B: Statement of Account",
            "financial_year": fy,
            "statement_of_assets_and_liabilities": {
                "partners_contribution": total_contribution,
                "reserves_and_surplus": balance_sheet.get("shareholders_funds", {}).get("reserves_and_surplus", 0.0),
                "total_liabilities": balance_sheet.get("total_equity_and_liabilities", 0.0),
                "total_assets": balance_sheet.get("total_assets", 0.0)
            },
            "statement_of_income_and_expenditure": {
                "turnover": total_turnover,
                "total_expenses": revenue_stmt.get("total_expenses", 0.0),
                "profit_before_tax": revenue_stmt.get("profit_before_tax", 0.0),
                "profit_transferred_to_partners": revenue_stmt.get("profit_after_tax", 0.0)
            }
        }

        return {
            "form_name": "Form 8 (Statement of Account & Solvency)",
            "statutory_rule": "Rule 24 of LLP Rules, 2009 & Section 34(2) of LLP Act, 2008",
            "llpin": llpin,
            "legal_name": tenant.legal_name,
            "financial_year": fy,
            "statutory_due_date": str(due_date),
            "days_remaining": days_remaining,
            "is_overdue": days_remaining < 0,
            "fine_per_day_inr": Decimal("100.00"),
            "audit_required": audit_required,
            "audit_reason": (
                "Turnover exceeds ₹40 Lakhs or Contribution exceeds ₹25 Lakhs (Rule 24(8) Mandate)"
                if audit_required else
                "Exempt from Statutory Audit (Turnover <= ₹40 Lakhs and Contribution <= ₹25 Lakhs)"
            ),
            "solvency_statement": solvency_declaration,
            "statement_of_account": statement_of_account,
            "signatories": [p for p in partners if p["is_designated"]]
        }

    @staticmethod
    def generate_partners_resolution_draft(
        tenant: Tenant,
        resolution_type: str = "approval_of_accounts",
        fy: str = "2025-26",
        designated_partners: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Drafts a formal Meeting of Partners resolution conforming to ICSI Secretarial Standards.
        """
        legal_name = tenant.legal_name or "LLP"
        dp_names = [p["name"] for p in (designated_partners or [])] or ["Designated Partners"]
        dp_str = ", ".join(dp_names)

        templates = {
            "approval_of_accounts": {
                "title": f"Resolution of the Designated Partners of {legal_name}",
                "subject": f"Approval of Statement of Account & Solvency (Form 8) for FY {fy}",
                "resolution_text": (
                    f"RESOLVED THAT the Statement of Assets and Liabilities as at 31st March {fy[-2:]} and the "
                    f"Statement of Income and Expenditure for the year ended on that date, together with the Statement of "
                    f"Solvency pursuant to Section 34(2) of the LLP Act, 2008 and Rule 24 of the LLP Rules, 2009, "
                    f"be and are hereby approved and taken on record.\n\n"
                    f"RESOLVED FURTHER THAT {dp_str} be and are hereby jointly and severally authorized to sign the "
                    f"Statement of Account & Solvency on behalf of the LLP and submit Form 8 to the Registrar of Companies."
                )
            },
            "annual_return_form11": {
                "title": f"Resolution of the Designated Partners of {legal_name}",
                "subject": f"Approval of Annual Return (Form 11) for FY {fy}",
                "resolution_text": (
                    f"RESOLVED THAT the Annual Return of the LLP for the Financial Year ended 31st March {fy[-2:]} "
                    f"prepared in Form 11 pursuant to Section 35 of the LLP Act, 2008 and Rule 25 of the LLP Rules, 2009 "
                    f"be and is hereby approved.\n\n"
                    f"RESOLVED FURTHER THAT {dp_str} be authorized to digitally sign and e-file Form 11 on the MCA Portal."
                )
            },
            "bank_signatory_mandate": {
                "title": f"Resolution of the Partners of {legal_name}",
                "subject": "Authorization of Bank Account Operations & Signatory Powers",
                "resolution_text": (
                    f"RESOLVED THAT the current account of {legal_name} maintained with the Bank be operated by "
                    f"{dp_str}, who are hereby authorized to sign cheques, bills, and electronic fund transfers on behalf of the LLP."
                )
            }
        }

        template = templates.get(resolution_type, templates["approval_of_accounts"])
        return {
            "resolution_id": f"RES-LLP-{uuid.uuid4().hex[:8].upper()}",
            "tenant_name": legal_name,
            "financial_year": fy,
            "resolution_type": resolution_type,
            "title": template["title"],
            "subject": template["subject"],
            "resolution_text": template["resolution_text"],
            "drafted_at": datetime.utcnow().isoformat(),
            "signatories": dp_names
        }
