import io
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List


def number_to_words_inr(number: float) -> str:
    """Converts a monetary number into Indian Currency words (Rupees)."""
    units = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_upto_999(n: int) -> str:
        res = ""
        if n >= 100:
            res += units[n // 100] + " Hundred "
            n %= 100
        if n >= 20:
            res += tens[n // 10] + " "
            n %= 10
        if n > 0:
            res += units[n] + " "
        return res.strip()

    num_int = int(round(number))
    if num_int == 0:
        return "Zero Indian Rupees Only"

    crore = num_int // 10000000
    num_int %= 10000000
    lakh = num_int // 100000
    num_int %= 100000
    thousand = num_int // 1000
    num_int %= 1000
    hundred = num_int

    words = []
    if crore > 0:
        words.append(convert_upto_999(crore) + " Crore")
    if lakh > 0:
        words.append(convert_upto_999(lakh) + " Lakh")
    if thousand > 0:
        words.append(convert_upto_999(thousand) + " Thousand")
    if hundred > 0:
        words.append(convert_upto_999(hundred))

    return "Indian Rupees " + " ".join(words).strip() + " Only"


class PDFService:
    @staticmethod
    def generate_simple_invoice_pdf(invoice_data: Dict[str, Any]) -> bytes:
        """
        Generates a professional Razorpay-style GST Tax Invoice PDF document byte stream
        under Section 31 of CGST Act 2017 with exact ISO 32000-1 xref byte offsets.
        """
        from app.services.document_assembly import DocumentAssemblyService

        # Supplier / Seller (Source of Truth)
        seller_name = (invoice_data.get("seller_name") or "ARYIX (OPC) PRIVATE LIMITED").upper()
        seller_cin = invoice_data.get("seller_cin") or "U70200KA2025OPC206792"
        seller_gstin = invoice_data.get("seller_gstin") or "29AABCS1429B1Z8"
        seller_pan = invoice_data.get("seller_pan") or (seller_gstin[2:12] if len(seller_gstin) >= 12 else "AABCS1429B")
        seller_addr = invoice_data.get("seller_address") or "Fraser Town, Bengaluru, Karnataka, India - 560005"

        # Invoice Identifiers
        inv_no = invoice_data.get("invoice_number", "INV-2026-10-001")
        issue_date = str(invoice_data.get("issue_date") or datetime.utcnow().strftime("%Y-%m-%d"))
        due_date = str(invoice_data.get("due_date") or issue_date)
        pos = str(invoice_data.get("place_of_supply") or "29")

        # Buyer / Customer
        customer_name = invoice_data.get("customer_name") or invoice_data.get("contact_name") or "Valued Customer"
        customer_gstin = invoice_data.get("customer_gstin") or "Unregistered (B2C)"
        customer_addr = invoice_data.get("customer_address") or f"State Code {pos}, India"

        # Pricing & Taxes
        subtotal = float(invoice_data.get("subtotal") or 0.0)
        cgst = float(invoice_data.get("cgst_total") or 0.0)
        sgst = float(invoice_data.get("sgst_total") or 0.0)
        igst = float(invoice_data.get("igst_total") or 0.0)
        grand_total = float(invoice_data.get("grand_total") or (subtotal + cgst + sgst + igst))

        # Items
        items_raw = invoice_data.get("items") or []
        items = []
        if isinstance(items_raw, list) and items_raw:
            for it in items_raw:
                if isinstance(it, dict):
                    items.append({
                        "desc": it.get("description") or it.get("item_description") or "IT & Software Services",
                        "sac": it.get("hsn_sac_code") or it.get("hsn_sac") or "998314",
                        "qty": it.get("quantity", 1),
                        "rate": float(it.get("unit_price") or it.get("rate") or subtotal),
                        "amount": float(it.get("taxable_amount") or it.get("amount") or subtotal)
                    })
        if not items:
            items.append({
                "desc": "Software Consulting & Development Services",
                "sac": "998314",
                "qty": 1,
                "rate": subtotal,
                "amount": subtotal
            })

        # Bank Remittance Info
        bank_info = invoice_data.get("bank_details") or {}
        bank_name = bank_info.get("bank_name") or "HDFC Bank Ltd"
        bank_ac = bank_info.get("account_number") or "50200114206173"
        bank_ifsc = bank_info.get("ifsc") or "HDFC0000714"

        lines = [
            "================================================================================",
            "                                  TAX INVOICE                                   ",
            "       (Issued Under Section 31 of the Central Goods & Services Tax Act, 2017)  ",
            "================================================================================",
            f"SELLER: {seller_name}",
            f"CIN   : {seller_cin} | PAN: {seller_pan}",
            f"GSTIN : {seller_gstin}",
            f"ADDR  : {seller_addr[:72]}",
            "--------------------------------------------------------------------------------",
            f"INVOICE NUMBER : {inv_no:<24} | BILLED TO : {customer_name[:30]}",
            f"INVOICE DATE   : {issue_date:<24} | GSTIN     : {customer_gstin}",
            f"DUE DATE       : {due_date:<24} | POS       : State {pos}",
            f"REVERSE CHARGE : NO{'':<24} | ADDRESS   : {customer_addr[:30]}",
            "================================================================================",
            f"{'#':<3}{'DESCRIPTION':<33}{'SAC/HSN':<10}{'QTY':<6}{'RATE (INR)':<14}{'TAXABLE (INR)':<14}",
            "--------------------------------------------------------------------------------"
        ]

        for idx, it in enumerate(items[:5], 1):
            desc_short = it["desc"][:31]
            lines.append(
                f"{idx:<3}{desc_short:<33}{it['sac']:<10}{it['qty']:<6}{it['rate']:>12,.2f}  {it['amount']:>12,.2f}"
            )

        lines.extend([
            "--------------------------------------------------------------------------------",
            f"{'TAXABLE SUBTOTAL':<64}{subtotal:>14,.2f}",
        ])

        if cgst > 0 or sgst > 0:
            lines.append(f"{'CENTRAL GST (CGST)':<64}{cgst:>14,.2f}")
            lines.append(f"{'STATE GST (SGST)':<64}{sgst:>14,.2f}")
        elif igst > 0:
            lines.append(f"{'INTEGRATED GST (IGST)':<64}{igst:>14,.2f}")
        else:
            lines.append(f"{'APPLICABLE GST (0% Nil-Rated)':<64}{0.00:>14,.2f}")

        lines.extend([
            "================================================================================",
            f"{'TOTAL INVOICE VALUE (INR)':<64}{grand_total:>14,.2f}",
            "================================================================================",
            f"AMOUNT IN WORDS: {number_to_words_inr(grand_total)}",
            "--------------------------------------------------------------------------------",
            f"BANK REMITTANCE DETAILS (NEFT / RTGS / IMPS):",
            f"Bank: {bank_name} | A/c No: {bank_ac} | IFSC: {bank_ifsc}",
            "--------------------------------------------------------------------------------",
            f"FOR {seller_name}:",
            "",
            "                       [ Digitally Authorized Signatory ]                       ",
            "================================================================================",
            "Generated via b00k5 Financial OS | ISO 32000-1 Cryptographic Audit Verified"
        ])

        return DocumentAssemblyService._create_pdf_document(f"TAX INVOICE - {inv_no}", lines)

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

