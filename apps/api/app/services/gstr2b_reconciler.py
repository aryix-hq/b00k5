"""
b00k5 - Statutory GSTR-2B Monthly JSON Reconciliation Engine
Compliant with:
- Central Goods and Services Tax (CGST) Act, 2017: Section 16(2)(aa) & Section 17(5)
- CGST Rules, 2017: Rule 36(4) (Mandatory matching of ITC with auto-drafted GSTR-2B)
"""

import re
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.expense import Expense
from app.models.tenant import Tenant
from app.services.compliance_watchdog import ComplianceWatchdogService

def normalize_alphanumeric(val: Optional[str]) -> str:
    """Normalizes invoice numbers and codes for robust reconciliation."""
    if not val:
        return ""
    cleaned = re.sub(r'[^A-Za-z0-9]', '', str(val)).upper()
    return cleaned.lstrip('0')

class GSTR2BReconciler:
    """
    Statutory GSTR-2B Reconciler adhering to Section 16(2)(aa) of the CGST Act, 2017.
    """

    @staticmethod
    def parse_gstr2b_json(raw_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses official GSTN GSTR-2B JSON payload into structured invoice records.
        """
        recipient_gstin = (raw_json.get("gstin") or "").strip().upper()
        return_period = str(raw_json.get("fp") or "").strip() # e.g. "072026"
        data_block = raw_json.get("data") or {}

        invoices_2b: List[Dict[str, Any]] = []

        # 1. Parse B2B Invoices (Standard business-to-business purchases)
        b2b_list = data_block.get("b2b") or []
        for supplier_entry in b2b_list:
            supplier_gstin = (supplier_entry.get("ctin") or "").strip().upper()
            cfs = supplier_entry.get("cfs", "Y") # Filing status of supplier

            for inv in supplier_entry.get("inv", []):
                inum = str(inv.get("inum") or "").strip()
                idt_str = str(inv.get("idt") or "").strip() # DD-MM-YYYY
                val = Decimal(str(inv.get("val") or "0.00"))
                pos = str(inv.get("pos") or "").strip()
                itcavl = str(inv.get("itcavl") or "Y").upper()
                rsn = str(inv.get("rsn") or "").strip()

                parsed_date = None
                if idt_str:
                    try:
                        parsed_date = datetime.strptime(idt_str, "%d-%m-%Y").date()
                    except ValueError:
                        try:
                            parsed_date = datetime.strptime(idt_str, "%Y-%m-%d").date()
                        except ValueError:
                            pass

                # Aggregate line items
                tot_txval = Decimal("0.00")
                tot_iamt = Decimal("0.00")
                tot_camt = Decimal("0.00")
                tot_samt = Decimal("0.00")
                tot_csamt = Decimal("0.00")

                for itm in inv.get("items", []):
                    tot_txval += Decimal(str(itm.get("txval") or "0.00"))
                    tot_iamt += Decimal(str(itm.get("iamt") or "0.00"))
                    tot_camt += Decimal(str(itm.get("camt") or "0.00"))
                    tot_samt += Decimal(str(itm.get("samt") or "0.00"))
                    tot_csamt += Decimal(str(itm.get("csamt") or "0.00"))

                tot_tax = tot_iamt + tot_camt + tot_samt + tot_csamt

                invoices_2b.append({
                    "supplier_gstin": supplier_gstin,
                    "supplier_filing_status": cfs,
                    "invoice_number": inum,
                    "invoice_number_norm": normalize_alphanumeric(inum),
                    "invoice_date": parsed_date,
                    "invoice_date_str": idt_str,
                    "total_value": val,
                    "taxable_value": tot_txval,
                    "igst_amount": tot_iamt,
                    "cgst_amount": tot_camt,
                    "sgst_amount": tot_samt,
                    "cess_amount": tot_csamt,
                    "total_tax_amount": tot_tax,
                    "place_of_supply": pos,
                    "itc_available_in_portal": itcavl == "Y",
                    "ineligibility_reason": rsn,
                    "raw_doc_type": "B2B"
                })

        # 2. Parse CDNR (Credit/Debit Notes)
        cdnr_list = data_block.get("cdnr") or []
        for supplier_entry in cdnr_list:
            supplier_gstin = (supplier_entry.get("ctin") or "").strip().upper()
            cfs = supplier_entry.get("cfs", "Y")

            for nt in supplier_entry.get("nt", []):
                nt_num = str(nt.get("nt_num") or "").strip()
                nt_dt = str(nt.get("nt_dt") or "").strip()
                val = Decimal(str(nt.get("val") or "0.00"))
                pos = str(nt.get("pos") or "").strip()
                itcavl = str(nt.get("itcavl") or "Y").upper()

                tot_txval = Decimal("0.00")
                tot_iamt = Decimal("0.00")
                tot_camt = Decimal("0.00")
                tot_samt = Decimal("0.00")
                tot_csamt = Decimal("0.00")

                for itm in nt.get("items", []):
                    tot_txval += Decimal(str(itm.get("txval") or "0.00"))
                    tot_iamt += Decimal(str(itm.get("iamt") or "0.00"))
                    tot_camt += Decimal(str(itm.get("camt") or "0.00"))
                    tot_samt += Decimal(str(itm.get("samt") or "0.00"))
                    tot_csamt += Decimal(str(itm.get("csamt") or "0.00"))

                tot_tax = tot_iamt + tot_camt + tot_samt + tot_csamt

                invoices_2b.append({
                    "supplier_gstin": supplier_gstin,
                    "supplier_filing_status": cfs,
                    "invoice_number": nt_num,
                    "invoice_number_norm": normalize_alphanumeric(nt_num),
                    "invoice_date_str": nt_dt,
                    "total_value": val,
                    "taxable_value": tot_txval,
                    "igst_amount": tot_iamt,
                    "cgst_amount": tot_camt,
                    "sgst_amount": tot_samt,
                    "cess_amount": tot_csamt,
                    "total_tax_amount": tot_tax,
                    "place_of_supply": pos,
                    "itc_available_in_portal": itcavl == "Y",
                    "ineligibility_reason": str(nt.get("rsn") or ""),
                    "raw_doc_type": "CDNR"
                })

        return {
            "recipient_gstin": recipient_gstin,
            "return_period": return_period,
            "total_records": len(invoices_2b),
            "invoices": invoices_2b
        }

    @staticmethod
    async def reconcile_against_books(
        db: AsyncSession,
        tenant: Tenant,
        parsed_2b: Dict[str, Any],
        auto_update_eligible_itc: bool = False
    ) -> Dict[str, Any]:
        """
        Executes cross-reconciliation between parsed GSTR-2B and Books of Accounts (expenses table).
        Applies Section 16(2)(aa) validation and Section 17(5) blocked credit rules.
        """
        tenant_id = tenant.id
        tenant_gstin = (tenant.gstin or "").strip().upper()
        return_period = parsed_2b.get("return_period", "")

        # 1. Query recorded expenses from books
        stmt = (
            select(Expense)
            .where(
                Expense.tenant_id == tenant_id,
                Expense.status != "struck_off"
            )
        )
        res = await db.execute(stmt)
        books_expenses = list(res.scalars().all())

        matched: List[Dict[str, Any]] = []
        tax_mismatches: List[Dict[str, Any]] = []
        missing_in_books: List[Dict[str, Any]] = []
        missing_in_2b: List[Dict[str, Any]] = []
        blocked_credit: List[Dict[str, Any]] = []

        # Index books expenses by (normalized_supplier_gstin, normalized_invoice_num)
        books_map: Dict[Tuple[str, str], Expense] = {}
        books_by_gstin: Dict[str, List[Expense]] = {}

        for exp in books_expenses:
            s_gst = (exp.merchant_gstin or "").strip().upper()
            inv_nums = []
            if exp.notes:
                # Check for extracted invoice number pattern in notes
                m = re.search(r'INV(?:OICE)?[:\s#\-]*([A-Za-z0-9\-\/]+)', exp.notes, re.I)
                if m:
                    inv_nums.append(normalize_alphanumeric(m.group(1)))
            if exp.journal_entry_number:
                inv_nums.append(normalize_alphanumeric(exp.journal_entry_number))
            if exp.merchant_name:
                # Also check merchant name in case invoice was embedded
                m2 = re.search(r'#([A-Za-z0-9\-]+)', exp.merchant_name)
                if m2:
                    inv_nums.append(normalize_alphanumeric(m2.group(1)))

            # Register in maps
            for num in inv_nums:
                if num and s_gst:
                    books_map[(s_gst, num)] = exp

            if s_gst:
                books_by_gstin.setdefault(s_gst, []).append(exp)

        matched_expense_ids = set()
        matched_2b_indices = set()

        # 2. Iterate through GSTR-2B invoices and match against books
        for idx, item_2b in enumerate(parsed_2b["invoices"]):
            s_gst = item_2b["supplier_gstin"]
            num_norm = item_2b["invoice_number_norm"]

            matched_exp: Optional[Expense] = None

            # Attempt 1: Exact match on (Supplier GSTIN + Normalized Invoice Number)
            if (s_gst, num_norm) in books_map:
                matched_exp = books_map[(s_gst, num_norm)]

            # Attempt 2: Fallback match on Supplier GSTIN + Total Amount tolerance (within ₹1.00)
            if not matched_exp and s_gst in books_by_gstin:
                for cand in books_by_gstin[s_gst]:
                    if cand.id not in matched_expense_ids:
                        if abs(cand.total_amount - item_2b["total_value"]) <= Decimal("1.00"):
                            matched_exp = cand
                            break

            # Attempt 3: Match on total value and merchant name substring if GSTIN was missing in book entry
            if not matched_exp:
                for cand in books_expenses:
                    if cand.id not in matched_expense_ids:
                        if abs(cand.total_amount - item_2b["total_value"]) <= Decimal("1.00"):
                            # Check if merchant names or notes resemble
                            m_clean = (cand.merchant_name or "").upper()
                            if s_gst[:5] in m_clean or any(token in m_clean for token in s_gst[2:10].split()):
                                matched_exp = cand
                                break

            if matched_exp:
                matched_expense_ids.add(matched_exp.id)
                matched_2b_indices.add(idx)

                # Check Section 17(5) blocked credit
                sec17_check = ComplianceWatchdogService.evaluate_gst_itc_eligibility(
                    tenant_gstin=tenant_gstin,
                    supplier_gstin=s_gst,
                    recipient_gstin_on_invoice=tenant_gstin,
                    invoice_number=item_2b["invoice_number"],
                    invoice_date=item_2b.get("invoice_date"),
                    place_of_supply=item_2b["place_of_supply"],
                    expense_category=matched_exp.category,
                    gstr2b_verified=True
                )

                if not sec17_check["itc_eligible"] and "Section 17(5)" in str(sec17_check.get("reasons")):
                    blocked_credit.append({
                        "expense_id": str(matched_exp.id),
                        "merchant_name": matched_exp.merchant_name,
                        "supplier_gstin": s_gst,
                        "invoice_number": item_2b["invoice_number"],
                        "total_value": item_2b["total_value"],
                        "tax_amount_in_2b": item_2b["total_tax_amount"],
                        "reason": sec17_check["reasons"][0] if sec17_check["reasons"] else "Section 17(5) Blocked Credit",
                        "status": "BLOCKED_CREDIT_SEC_17_5"
                    })
                    continue

                # Compare tax amounts
                book_tax = (matched_exp.cgst_amount or Decimal("0.00")) + (matched_exp.sgst_amount or Decimal("0.00")) + (matched_exp.igst_amount or Decimal("0.00"))
                gstr2b_tax = item_2b["total_tax_amount"]
                tax_diff = abs(book_tax - gstr2b_tax)

                if tax_diff > Decimal("2.00"):
                    tax_mismatches.append({
                        "expense_id": str(matched_exp.id),
                        "merchant_name": matched_exp.merchant_name,
                        "supplier_gstin": s_gst,
                        "invoice_number": item_2b["invoice_number"],
                        "book_total": matched_exp.total_amount,
                        "gstr2b_total": item_2b["total_value"],
                        "book_tax": book_tax,
                        "gstr2b_tax": gstr2b_tax,
                        "tax_variance": tax_diff,
                        "status": "TAX_MISMATCH",
                        "message": f"Tax in books (₹{book_tax}) differs from GSTR-2B (₹{gstr2b_tax}) by ₹{tax_diff}"
                    })
                else:
                    matched.append({
                        "expense_id": str(matched_exp.id),
                        "merchant_name": matched_exp.merchant_name,
                        "supplier_gstin": s_gst,
                        "invoice_number": item_2b["invoice_number"],
                        "total_value": item_2b["total_value"],
                        "tax_amount": gstr2b_tax,
                        "status": "MATCHED",
                        "statutory_compliance": "Section 16(2)(aa) CGST Act Invariant Held"
                    })
                    if auto_update_eligible_itc:
                        matched_exp.itc_eligible = True
                        matched_exp.has_company_gstin = True
            else:
                missing_in_books.append({
                    "supplier_gstin": s_gst,
                    "invoice_number": item_2b["invoice_number"],
                    "invoice_date": item_2b["invoice_date_str"],
                    "total_value": item_2b["total_value"],
                    "taxable_value": item_2b["taxable_value"],
                    "tax_amount": item_2b["total_tax_amount"],
                    "status": "MISSING_IN_BOOKS",
                    "opportunity": f"Unclaimed ITC of ₹{item_2b['total_tax_amount']} available under Section 16(2)"
                })

        # 3. Check for expenses in books with GSTIN that did NOT appear in GSTR-2B
        for exp in books_expenses:
            if exp.id not in matched_expense_ids:
                s_gst = (exp.merchant_gstin or "").strip().upper()
                total_tax = (exp.cgst_amount or Decimal("0.00")) + (exp.sgst_amount or Decimal("0.00")) + (exp.igst_amount or Decimal("0.00"))
                if s_gst or total_tax > Decimal("0.00"):
                    missing_in_2b.append({
                        "expense_id": str(exp.id),
                        "merchant_name": exp.merchant_name,
                        "supplier_gstin": s_gst or "Unrecorded",
                        "expense_date": str(exp.expense_date),
                        "total_amount": exp.total_amount,
                        "tax_amount": total_tax,
                        "status": "MISSING_IN_2B",
                        "statutory_risk": "Cannot claim in GSTR-3B under Sec 16(2)(aa) until supplier files GSTR-1"
                    })

        if auto_update_eligible_itc:
            await db.flush()

        # Compute summary metrics
        total_2b_itc = sum(item["total_tax_amount"] for item in parsed_2b["invoices"])
        total_matched_itc = sum(m["tax_amount"] for m in matched)
        total_missing_books_itc = sum(mb["tax_amount"] for mb in missing_in_books)
        total_missing_2b_itc = sum(m2["tax_amount"] for m2 in missing_in_2b)
        total_blocked_itc = sum(b["tax_amount_in_2b"] for b in blocked_credit)

        return {
            "recipient_gstin": tenant_gstin,
            "return_period": return_period,
            "reconciliation_summary": {
                "total_gstr2b_invoices": len(parsed_2b["invoices"]),
                "matched_count": len(matched),
                "tax_mismatch_count": len(tax_mismatches),
                "missing_in_books_count": len(missing_in_books),
                "missing_in_2b_count": len(missing_in_2b),
                "blocked_credit_count": len(blocked_credit),
                "total_gstr2b_itc_inr": total_2b_itc,
                "reconciled_eligible_itc_inr": total_matched_itc,
                "unclaimed_itc_inr": total_missing_books_itc,
                "provisional_at_risk_itc_inr": total_missing_2b_itc,
                "blocked_credit_sec17_5_inr": total_blocked_itc
            },
            "matched_records": matched,
            "tax_mismatches": tax_mismatches,
            "missing_in_books": missing_in_books,
            "missing_in_2b": missing_in_2b,
            "blocked_credit": blocked_credit
        }

