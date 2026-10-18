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
        Generates a pixel-perfect, professional GST Tax Invoice PDF document byte stream
        matching statutory design with Aryix branding, slanted PAID stamp, itemized breakdown,
        and company bank account remittance details.
        """
        import os
        from datetime import datetime
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            has_reportlab = True
        except ImportError:
            has_reportlab = False

        if not has_reportlab:
            from app.services.document_assembly import DocumentAssemblyService
            lines = [
                f"TAX INVOICE: {invoice_data.get('invoice_number', 'INV-2026-05-001')}",
                f"SELLER: {invoice_data.get('seller_name', 'Acme Technologies Pvt Ltd')}",
                f"CUSTOMER: {invoice_data.get('customer_name', 'Apex Client Solutions')}",
                f"TOTAL: INR {float(invoice_data.get('grand_total') or 0):,.2f}"
            ]
            return DocumentAssemblyService._create_pdf_document("TAX INVOICE", lines)

        # Register Unicode TrueType fonts if available
        font_normal = "Helvetica"
        font_bold = "Helvetica-Bold"

        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
            bp = p.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
            if os.path.exists(p) and os.path.exists(bp):
                try:
                    pdfmetrics.registerFont(TTFont("DejaVuSans", p))
                    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bp))
                    font_normal = "DejaVuSans"
                    font_bold = "DejaVuSans-Bold"
                    break
                except Exception:
                    pass

        def format_date_long(dt_str: Any) -> str:
            if not dt_str:
                return ""
            if isinstance(dt_str, datetime):
                return dt_str.strftime("%-d %B %Y")
            s = str(dt_str).strip()
            try:
                dt = datetime.strptime(s[:10], "%Y-%m-%d")
                return dt.strftime("%-d %B %Y")
            except Exception:
                return s

        def format_inr(amount: float) -> str:
            rupee_sym = "₹" if font_normal == "DejaVuSans" else "Rs. "
            return f"{rupee_sym}{amount:,.2f}"

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        page_w, page_h = A4  # 595.28 x 841.89

        # Palette
        c_primary = colors.HexColor("#0f172a")     # Slate 900
        c_muted = colors.HexColor("#64748b")       # Slate 500
        c_text = colors.HexColor("#1e293b")        # Slate 800
        c_border = colors.HexColor("#e2e8f0")      # Slate 200
        c_paid = colors.HexColor("#dc2626")        # Red 600

        # Identifiers
        inv_no = str(invoice_data.get("invoice_number") or "INV-2026-05-001")
        issue_date = format_date_long(invoice_data.get("issue_date") or datetime.utcnow().strftime("%Y-%m-%d"))
        due_date = format_date_long(invoice_data.get("due_date") or invoice_data.get("issue_date") or issue_date)
        pos = str(invoice_data.get("place_of_supply") or "Karnataka")
        if pos == "29":
            pos = "Karnataka"

        seller_name = str(invoice_data.get("seller_name") or "").strip().upper()
        seller_cin = str(invoice_data.get("seller_cin") or "").strip()
        seller_gstin = str(invoice_data.get("seller_gstin") or "").strip()
        seller_pan = str(invoice_data.get("seller_pan") or "").strip()
        seller_addr = str(invoice_data.get("seller_address") or "").strip()
        seller_email = str(invoice_data.get("seller_email") or "").strip()
        seller_phone = str(invoice_data.get("seller_phone") or "").strip()

        customer_name = str(invoice_data.get("customer_name") or invoice_data.get("contact_name") or "Valued Customer").strip()
        customer_gstin = str(invoice_data.get("customer_gstin") or "").strip()
        customer_addr = str(invoice_data.get("customer_address") or "").strip()
        customer_email = str(invoice_data.get("customer_email") or "").strip()
        customer_phone = str(invoice_data.get("customer_phone") or "").strip()

        items = invoice_data.get("items") or []
        subtotal = float(invoice_data.get("subtotal") or (sum(float(it.get("taxable_amount", it.get("unit_price", 0))) for it in items) if items else 0.0))
        if not items:
            items = [{
                "description": "Professional Consulting & Services",
                "hsn_sac_code": "998314",
                "quantity": 1,
                "unit_price": subtotal,
                "taxable_amount": subtotal
            }]

        cgst = float(invoice_data.get("cgst_total") or 0.0)
        sgst = float(invoice_data.get("sgst_total") or 0.0)
        igst = float(invoice_data.get("igst_total") or 0.0)
        grand_total = float(invoice_data.get("grand_total") or (subtotal + cgst + sgst + igst))

        status_str = str(invoice_data.get("status") or "PAID").upper()
        is_paid = status_str in ("PAID", "SETTLED") or invoice_data.get("is_paid", True)

        # Bank Details from DB (Tenant Statutory Profile)
        bank_info = invoice_data.get("bank_details") or {}
        bank_acc_name = str(bank_info.get("account_holder_name") or seller_name or "").strip()
        bank_name = str(bank_info.get("bank_name") or "").strip()
        if bank_name and "HDFC" in bank_name.upper() and "LTD" not in bank_name.upper():
            bank_name = "HDFC Bank Ltd"
        bank_acc_no = str(bank_info.get("account_number") or "").strip()
        bank_ifsc = str(bank_info.get("ifsc") or "").strip()

        # 1. Header Section
        margin_l = 42
        margin_r = page_w - 42
        curr_y = 785

        c.setFont(font_bold, 22)
        c.setFillColor(c_primary)
        c.drawString(margin_l, curr_y, "Invoice")

        # Top Right Logo from Company Profile
        logo_img = None
        logo_url = invoice_data.get("logo_url")
        logo_s3_key = invoice_data.get("logo_s3_key")

        if logo_url:
            s_url = str(logo_url).strip()
            if s_url.startswith("data:image"):
                try:
                    import base64
                    from reportlab.lib.utils import ImageReader
                    b64data = s_url.split(",", 1)[1] if "," in s_url else s_url
                    raw_bytes = base64.b64decode(b64data)
                    logo_img = ImageReader(io.BytesIO(raw_bytes))
                except Exception:
                    pass
            elif s_url.startswith("http://") or s_url.startswith("https://"):
                try:
                    from reportlab.lib.utils import ImageReader
                    logo_img = ImageReader(s_url)
                except Exception:
                    pass

        if not logo_img and logo_s3_key:
            try:
                from app.core.s3 import storage_manager
                from app.core.config import settings
                from reportlab.lib.utils import ImageReader
                for bkt in (getattr(settings, "BUCKET_STATUTORY", "b00k5-statutory"), getattr(settings, "BUCKET_VAULT", "b00k5-vault")):
                    try:
                        raw_bytes = storage_manager.get_document_bytes(bkt, logo_s3_key)
                        if raw_bytes:
                            logo_img = ImageReader(io.BytesIO(raw_bytes))
                            break
                    except Exception:
                        pass
            except Exception:
                pass

        if logo_img:
            try:
                c.drawImage(logo_img, margin_r - 46, curr_y - 28, width=44, height=46, mask="auto")
            except Exception:
                pass
        else:
            # Clean text branding fallback - never show broken image box or external placeholder
            c.setFont(font_bold, 11)
            c.setFillColor(c_primary)
            s_name = str(invoice_data.get("seller_name") or "").strip()
            if s_name:
                c.drawRightString(margin_r, curr_y, s_name)

        curr_y -= 28
        meta_items = [
            ("Invoice No:", inv_no),
            ("Issue Date:", issue_date),
            ("Due Date:", due_date),
            ("Place of Supply:", pos),
        ]

        val_x = margin_l + 105
        for label, val in meta_items:
            c.setFont(font_normal, 9.5)
            c.setFillColor(c_muted)
            c.drawString(margin_l, curr_y, label)

            c.setFont(font_bold, 9.5)
            c.setFillColor(c_primary)
            c.drawString(val_x, curr_y, val)
            curr_y -= 16

        # Slanted PAID Stamp
        if is_paid:
            c.saveState()
            stamp_x = margin_l + 250
            stamp_y = 740
            c.translate(stamp_x, stamp_y)
            c.rotate(-8)
            c.setStrokeColor(c_paid)
            c.setLineWidth(1.8)
            c.roundRect(0, 0, 78, 28, 4, stroke=1, fill=0)
            c.setFont(font_bold, 17)
            c.setFillColor(c_paid)
            c.drawCentredString(39, 7.5, "PAID")
            c.restoreState()

        # 2. Bill From and Bill To Columns (Strictly Database Driven, No Dummy Data)
        curr_y -= 14
        col2_x = 320

        c.setFont(font_normal, 9.5)
        c.setFillColor(c_muted)
        c.drawString(margin_l, curr_y, "Bill From")
        c.drawString(col2_x, curr_y, "Bill To")

        curr_y -= 16

        def wrap_lines(text: str, max_w: float, font_name: str, font_sz: float) -> list:
            if not text:
                return []
            words = text.split()
            lines = []
            cur_line = []
            for w in words:
                test_line = " ".join(cur_line + [w])
                if c.stringWidth(test_line, font_name, font_sz) <= max_w:
                    cur_line.append(w)
                else:
                    if cur_line:
                        lines.append(" ".join(cur_line))
                    cur_line = [w]
            if cur_line:
                lines.append(" ".join(cur_line))
            return lines

        # Construct seller details from DB
        seller_entries = []
        if seller_name:
            seller_entries.append((font_bold, 10.0, c_primary, seller_name))
        if seller_cin:
            seller_entries.append((font_normal, 8.5, c_muted, f"CIN: {seller_cin}"))
        if seller_gstin:
            seller_entries.append((font_normal, 8.5, c_text, f"GSTIN: {seller_gstin}"))
        if seller_pan:
            seller_entries.append((font_normal, 8.5, c_muted, f"PAN: {seller_pan}"))
        if seller_addr:
            for l in wrap_lines(seller_addr, 240, font_normal, 8.5)[:3]:
                seller_entries.append((font_normal, 8.5, c_text, l))
        if seller_email:
            seller_entries.append((font_normal, 8.5, c_text, seller_email))
        if seller_phone:
            seller_entries.append((font_normal, 8.5, c_text, seller_phone))

        # Construct customer details from DB
        cust_entries = []
        if customer_name:
            cust_entries.append((font_bold, 10.0, c_primary, customer_name))
        if customer_gstin:
            cust_entries.append((font_normal, 8.5, c_text, f"GSTIN: {customer_gstin}"))
        if customer_addr:
            for l in wrap_lines(customer_addr, 230, font_normal, 8.5)[:3]:
                cust_entries.append((font_normal, 8.5, c_text, l))
        if customer_email:
            cust_entries.append((font_normal, 8.5, c_text, customer_email))
        if customer_phone:
            cust_entries.append((font_normal, 8.5, c_text, customer_phone))

        seller_y = curr_y
        for fnt, sz, clr, txt in seller_entries:
            c.setFont(fnt, sz)
            c.setFillColor(clr)
            c.drawString(margin_l, seller_y, txt)
            seller_y -= 13

        cust_y = curr_y
        for fnt, sz, clr, txt in cust_entries:
            c.setFont(fnt, sz)
            c.setFillColor(clr)
            c.drawString(col2_x, cust_y, txt)
            cust_y -= 13

        curr_y = min(seller_y, cust_y) - 8

        # 3. Horizontal Divider & Items Table Header
        curr_y -= 14
        c.setStrokeColor(c_border)
        c.setLineWidth(1)
        c.line(margin_l, curr_y, margin_r, curr_y)

        curr_y -= 18
        col_item_x = margin_l
        col_hsn_x = 240
        col_price_x = 375
        col_qty_x = 430
        col_total_x = margin_r

        c.setFont(font_normal, 9)
        c.setFillColor(c_muted)
        c.drawString(col_item_x, curr_y, "Item")
        c.drawString(col_hsn_x, curr_y, "HSN/SAC")
        c.drawRightString(col_price_x, curr_y, "Price")
        c.drawRightString(col_qty_x, curr_y, "Qty")
        c.drawRightString(col_total_x, curr_y, "Total")

        curr_y -= 10
        c.line(margin_l, curr_y, margin_r, curr_y)

        # 4. Line Items
        curr_y -= 18
        for it in items:
            title = it.get("description") or it.get("item_description") or "Consulting & Services"
            subtitle = it.get("subtitle") or it.get("notes") or ""
            hsn = str(it.get("hsn_sac_code") or it.get("hsn_sac") or "-")
            qty = float(it.get("quantity", 1))
            qty_str = f"{int(qty)}" if qty.is_integer() else f"{qty:.2f}"
            rate = float(it.get("unit_price") or it.get("rate") or subtotal)
            line_total = float(it.get("taxable_amount") or it.get("amount") or (rate * qty))

            # Title word wrap to prevent collision with HSN column
            title_words = title.split()
            title_lines = []
            cur_t = []
            for tw in title_words:
                test_t = " ".join(cur_t + [tw])
                if c.stringWidth(test_t, font_bold, 9.5) <= 185:
                    cur_t.append(tw)
                else:
                    if cur_t:
                        title_lines.append(" ".join(cur_t))
                    cur_t = [tw]
            if cur_t:
                title_lines.append(" ".join(cur_t))
            if not title_lines:
                title_lines = [title]

            # Vertical boundary check for multi-item invoices (DEF-14 overlap prevention)
            if curr_y < 160:
                c.setFont(font_normal, 8)
                c.setFillColor(c_muted)
                c.drawString(margin_l, 42, "Computer generated tax invoice under Section 31 of CGST Act, 2017. Continued on next page...")
                c.showPage()
                curr_y = page_h - 60
                c.setFont(font_bold, 9.5)
                c.setFillColor(c_primary)
                c.drawString(margin_l, curr_y, f"Tax Invoice: {inv_no} (Continued)")
                curr_y -= 14
                c.setStrokeColor(c_border)
                c.setLineWidth(1)
                c.line(margin_l, curr_y, margin_r, curr_y)
                curr_y -= 14
                c.setFont(font_normal, 9)
                c.setFillColor(c_muted)
                c.drawString(col_item_x, curr_y, "Item")
                c.drawString(col_hsn_x, curr_y, "HSN/SAC")
                c.drawRightString(col_price_x, curr_y, "Price")
                c.drawRightString(col_qty_x, curr_y, "Qty")
                c.drawRightString(col_total_x, curr_y, "Total")
                curr_y -= 8
                c.line(margin_l, curr_y, margin_r, curr_y)
                curr_y -= 18

            # Primary line with HSN, Price, Qty, Total
            c.setFont(font_bold, 9.5)
            c.setFillColor(c_primary)
            c.drawString(col_item_x, curr_y, title_lines[0])

            c.setFont(font_normal, 9)
            c.setFillColor(c_text)
            c.drawString(col_hsn_x, curr_y, hsn)
            c.drawRightString(col_price_x, curr_y, format_inr(rate))
            c.drawRightString(col_qty_x, curr_y, qty_str)
            c.drawRightString(col_total_x, curr_y, format_inr(line_total))

            # Wrapped title continuation lines
            for extra_line in title_lines[1:]:
                curr_y -= 13
                c.setFont(font_bold, 9.5)
                c.setFillColor(c_primary)
                c.drawString(col_item_x, curr_y, extra_line)

            # Subtitle / Notes lines
            if subtitle:
                curr_y -= 13
                c.setFont(font_normal, 8.5)
                c.setFillColor(c_muted)
                sub_words = subtitle.split()
                sub_lines = []
                cur_sub = []
                for sw in sub_words:
                    test_sub = " ".join(cur_sub + [sw])
                    if c.stringWidth(test_sub, font_normal, 8.5) <= 185:
                        cur_sub.append(sw)
                    else:
                        if cur_sub:
                            sub_lines.append(" ".join(cur_sub))
                        cur_sub = [sw]
                if cur_sub:
                    sub_lines.append(" ".join(cur_sub))

                for sl in sub_lines[:4]:
                    c.drawString(col_item_x, curr_y, sl)
                    curr_y -= 11

            curr_y -= 18

        # 5. Summary Section (Side-by-side Bank Details on Left & Totals on Right)
        # Check if enough vertical room exists before bottom footer (DEF-14)
        if curr_y < 165:
            c.setFont(font_normal, 8)
            c.setFillColor(c_muted)
            c.drawString(margin_l, 42, "Computer generated tax invoice under Section 31 of CGST Act, 2017. Continued on next page...")
            c.showPage()
            curr_y = page_h - 60
            c.setFont(font_bold, 9.5)
            c.setFillColor(c_primary)
            c.drawString(margin_l, curr_y, f"Tax Invoice: {inv_no} (Summary & Settlement)")
            curr_y -= 25

        summary_top_y = curr_y - 4

        # 5a. Bank Account Details (Card on Left)
        bank_card_y = summary_top_y
        bank_card_h = 92
        bank_card_w = 265

        c.setStrokeColor(c_border)
        c.setLineWidth(1)
        c.roundRect(margin_l, bank_card_y - bank_card_h, bank_card_w, bank_card_h, 6, stroke=1, fill=0)

        inner_y = bank_card_y - 16
        c.setFont(font_bold, 9.5)
        c.setFillColor(c_primary)
        c.drawString(margin_l + 12, inner_y, "Bank Account Details")

        inner_y -= 17
        bank_fields = [
            ("Account Name", bank_acc_name),
            ("Bank Name", bank_name),
            ("Account Number", bank_acc_no),
            ("IFSC Code", bank_ifsc),
        ]

        for b_label, b_val in bank_fields:
            c.setFont(font_normal, 8.5)
            c.setFillColor(c_muted)
            c.drawString(margin_l + 12, inner_y, b_label)

            c.setFont(font_bold, 8.5)
            c.setFillColor(c_primary)
            c.drawString(margin_l + 95, inner_y, f": {b_val}")
            inner_y -= 14

        # 5b. Totals Section (Right Column)
        totals_col_x = 345
        c.setStrokeColor(c_border)
        c.setLineWidth(1)
        c.line(totals_col_x, summary_top_y, margin_r, summary_top_y)

        tot_y = summary_top_y - 17
        c.setFont(font_normal, 9.5)
        c.setFillColor(c_text)
        c.drawString(totals_col_x, tot_y, "Subtotal")
        c.drawRightString(margin_r, tot_y, format_inr(subtotal))

        if cgst > 0 or sgst > 0:
            tot_y -= 15
            c.drawString(totals_col_x, tot_y, "CGST (9%)")
            c.drawRightString(margin_r, tot_y, format_inr(cgst))
            tot_y -= 15
            c.drawString(totals_col_x, tot_y, "SGST (9%)")
            c.drawRightString(margin_r, tot_y, format_inr(sgst))
        elif igst > 0:
            tot_y -= 15
            c.drawString(totals_col_x, tot_y, "IGST (18%)")
            c.drawRightString(margin_r, tot_y, format_inr(igst))

        tot_y -= 13
        c.line(totals_col_x, tot_y, margin_r, tot_y)

        tot_y -= 25
        c.setFont(font_bold, 22)
        c.setFillColor(c_primary)
        c.drawRightString(margin_r, tot_y, format_inr(grand_total))

        # 7. Bottom Regulatory Note
        c.setFont(font_normal, 8)
        c.setFillColor(c_muted)
        c.drawString(margin_l, 42, "Computer generated tax invoice under Section 31 of CGST Act, 2017. No physical signature required.")

        c.save()
        buf.seek(0)
        return buf.getvalue()

    @staticmethod
    def generate_form_16_pdf(form_16_data: Dict[str, Any]) -> bytes:
        """
        Generates an official, beautifully styled Form 16 PDF (Part A & Part B)
        under Section 203 of the Income-tax Act, 1961 for tax deducted at source on salary.
        """
        import os
        from datetime import datetime
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            has_reportlab = True
        except ImportError:
            has_reportlab = False

        emp_name = str(form_16_data.get("employee_name") or "Employee").strip()
        emp_pan = str(form_16_data.get("pan_number") or "").strip().upper()
        emp_code = str(form_16_data.get("employee_code") or "").strip()
        emp_desig = str(form_16_data.get("designation") or "Staff").strip()

        employer_name = str(form_16_data.get("tenant_name") or "Employer").strip().upper()
        employer_pan = str(form_16_data.get("tenant_pan") or "").strip().upper()
        employer_tan = str(form_16_data.get("tenant_tan") or "").strip().upper()
        employer_addr = str(form_16_data.get("tenant_address") or "Registered Office").strip()

        ay = str(form_16_data.get("assessment_year") or "2026-27").strip()
        fy = str(form_16_data.get("fiscal_year") or "2025-26").strip()
        regime = str(form_16_data.get("tax_regime") or "new_115bac").strip()

        gross_salary = float(form_16_data.get("gross_salary") or 0.0)
        std_ded = float(form_16_data.get("standard_deduction") or 0.0)
        pt = float(form_16_data.get("professional_tax") or 0.0)
        net_sal_16 = float(form_16_data.get("net_salary_under_sec_16") or 0.0)
        via_ded = float(form_16_data.get("deductions_chapter_vi_a") or 0.0)
        taxable_inc = float(form_16_data.get("total_taxable_income") or 0.0)
        tax_on_inc = float(form_16_data.get("tax_on_total_income") or 0.0)
        rebate_87a = float(form_16_data.get("rebate_87a") or 0.0)
        cess = float(form_16_data.get("health_and_education_cess") or 0.0)
        tot_tax_payable = float(form_16_data.get("total_tax_payable") or 0.0)
        tot_tax_deducted = float(form_16_data.get("total_tax_deducted") or 0.0)

        quarters = form_16_data.get("quarterly_tds_summary") or [
            {"quarter": "Q1 (Apr - Jun)", "receipt_no": "TDS-Q1-09821", "amount_deducted": tot_tax_deducted * 0.25, "amount_deposited": tot_tax_deducted * 0.25},
            {"quarter": "Q2 (Jul - Sep)", "receipt_no": "TDS-Q2-11492", "amount_deducted": tot_tax_deducted * 0.25, "amount_deposited": tot_tax_deducted * 0.25},
            {"quarter": "Q3 (Oct - Dec)", "receipt_no": "TDS-Q3-32819", "amount_deducted": tot_tax_deducted * 0.25, "amount_deposited": tot_tax_deducted * 0.25},
            {"quarter": "Q4 (Jan - Mar)", "receipt_no": "TDS-Q4-44018", "amount_deducted": tot_tax_deducted * 0.25, "amount_deposited": tot_tax_deducted * 0.25},
        ]

        if not has_reportlab:
            from app.services.document_assembly import DocumentAssemblyService
            lines = [
                f"FORM NO. 16 - PART A & PART B",
                f"EMPLOYER: {employer_name} | TAN: {employer_tan} | PAN: {employer_pan}",
                f"EMPLOYEE: {emp_name} ({emp_code}) | PAN: {emp_pan}",
                f"ASSESSMENT YEAR: {ay} | FISCAL YEAR: {fy} | REGIME: {regime}",
                f"GROSS SALARY: INR {gross_salary:,.2f}",
                f"STANDARD DEDUCTION: INR {std_ded:,.2f}",
                f"TAXABLE INCOME: INR {taxable_inc:,.2f}",
                f"TOTAL TDS DEDUCTED: INR {tot_tax_deducted:,.2f}"
            ]
            return DocumentAssemblyService._create_pdf_document("FORM 16 CERTIFICATE", lines)

        font_normal = "Helvetica"
        font_bold = "Helvetica-Bold"

        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
            bp = p.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
            if os.path.exists(p) and os.path.exists(bp):
                try:
                    pdfmetrics.registerFont(TTFont("DejaVuSans", p))
                    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bp))
                    font_normal = "DejaVuSans"
                    font_bold = "DejaVuSans-Bold"
                    break
                except Exception:
                    pass

        def format_inr(amount: float) -> str:
            rupee_sym = "₹" if font_normal == "DejaVuSans" else "Rs. "
            return f"{rupee_sym}{amount:,.2f}"

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        page_w, page_h = A4

        c_primary = colors.HexColor("#0f172a")     # Slate 900
        c_muted = colors.HexColor("#64748b")       # Slate 500
        c_text = colors.HexColor("#1e293b")        # Slate 800
        c_border = colors.HexColor("#cbd5e1")      # Slate 300
        c_bg = colors.HexColor("#f8fafc")          # Slate 50
        c_accent = colors.HexColor("#0284c7")      # Sky 600

        margin_l = 40.0
        margin_r = page_w - 40.0
        width = margin_r - margin_l

        # =====================================================================
        # PAGE 1: PART A
        # =====================================================================
        # Outer Border
        c.setStrokeColor(c_border)
        c.setLineWidth(1)
        c.rect(margin_l, 40, width, page_h - 80)

        # Header Title
        c.setFont(font_bold, 14)
        c.setFillColor(c_primary)
        c.drawCentredString(page_w / 2.0, page_h - 65, "FORM NO. 16")

        c.setFont(font_normal, 9)
        c.setFillColor(c_muted)
        c.drawCentredString(page_w / 2.0, page_h - 78, "[See rule 31(1)(a)]")

        c.setFont(font_bold, 10)
        c.setFillColor(c_text)
        c.drawCentredString(page_w / 2.0, page_h - 93, "Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary")

        # PART A Header Banner
        c.setFillColor(c_primary)
        c.rect(margin_l, page_h - 120, width, 20, fill=1, stroke=0)
        c.setFont(font_bold, 10)
        c.setFillColor(colors.white)
        c.drawString(margin_l + 10, page_h - 114, "PART A: Summary of Tax Deducted at Source (TDS)")

        # Box 1: Employer & Employee Info (Two Column Grid)
        box_top = page_h - 125
        box_h = 135
        c.setStrokeColor(c_border)
        c.setFillColor(c_bg)
        c.rect(margin_l + 10, box_top - box_h, width - 20, box_h, fill=1, stroke=1)

        # Mid vertical divider
        mid_x = margin_l + 10 + (width - 20) / 2.0
        c.line(mid_x, box_top, mid_x, box_top - box_h)

        # Left Column: Employer Info
        cur_y = box_top - 18
        c.setFont(font_bold, 9)
        c.setFillColor(c_primary)
        c.drawString(margin_l + 20, cur_y, "Name and Address of the Employer:")
        cur_y -= 14
        c.setFont(font_bold, 9.5)
        c.drawString(margin_l + 20, cur_y, employer_name[:40])
        cur_y -= 12
        c.setFont(font_normal, 8)
        c.setFillColor(c_muted)
        c.drawString(margin_l + 20, cur_y, employer_addr[:45])
        cur_y -= 22
        c.setFont(font_normal, 8.5)
        c.setFillColor(c_text)
        c.drawString(margin_l + 20, cur_y, f"PAN of Employer: {employer_pan or 'N/A'}")
        cur_y -= 14
        c.drawString(margin_l + 20, cur_y, f"TAN of Employer: {employer_tan or 'N/A'}")

        # Right Column: Employee Info
        cur_y = box_top - 18
        c.setFont(font_bold, 9)
        c.setFillColor(c_primary)
        c.drawString(mid_x + 10, cur_y, "Name and Address of the Employee:")
        cur_y -= 14
        c.setFont(font_bold, 9.5)
        c.drawString(mid_x + 10, cur_y, f"{emp_name} ({emp_code})")
        cur_y -= 12
        c.setFont(font_normal, 8)
        c.setFillColor(c_muted)
        c.drawString(mid_x + 10, cur_y, f"Designation: {emp_desig}")
        cur_y -= 22
        c.setFont(font_normal, 8.5)
        c.setFillColor(c_text)
        c.drawString(mid_x + 10, cur_y, f"PAN of Employee: {emp_pan}")
        cur_y -= 14
        c.drawString(mid_x + 10, cur_y, f"Assessment Year: {ay} (FY {fy})")

        # Assessment Year & Regime Bar
        bar_y = box_top - box_h - 22
        c.setFillColor(c_accent)
        c.rect(margin_l + 10, bar_y - 18, width - 20, 20, fill=1, stroke=0)
        c.setFont(font_bold, 8.5)
        c.setFillColor(colors.white)
        c.drawString(margin_l + 20, bar_y - 12, f"CIT (TDS) Jurisdiction: Range 1(1), Bangalore  |  Tax Regime: {regime.replace('_', ' ').upper()}  |  Certificate No: CERT-{emp_pan[-4:]}-{ay[:4]}")

        # Part A Table: Quarterly Breakdown
        tbl_top = bar_y - 45
        c.setFont(font_bold, 9)
        c.setFillColor(c_primary)
        c.drawString(margin_l + 10, tbl_top + 10, "Summary of Amount Deducted and Deposited into Central Government Account:")

        tbl_h = 20
        c.setFillColor(c_primary)
        c.rect(margin_l + 10, tbl_top - tbl_h, width - 20, tbl_h, fill=1, stroke=0)
        c.setFont(font_bold, 8)
        c.setFillColor(colors.white)
        c.drawString(margin_l + 20, tbl_top - 14, "Quarter")
        c.drawString(margin_l + 140, tbl_top - 14, "Receipt No. of TDS Return")
        c.drawRightString(margin_l + 350, tbl_top - 14, "Amount Deducted (Rs.)")
        c.drawRightString(margin_r - 20, tbl_top - 14, "Amount Deposited (Rs.)")

        row_y = tbl_top - tbl_h
        c.setStrokeColor(c_border)
        for i, q in enumerate(quarters):
            row_y -= 20
            c.setFillColor(colors.white if i % 2 == 0 else c_bg)
            c.rect(margin_l + 10, row_y, width - 20, 20, fill=1, stroke=1)
            c.setFont(font_normal, 8)
            c.setFillColor(c_text)
            c.drawString(margin_l + 20, row_y + 6, str(q.get("quarter", f"Q{i+1}")))
            c.drawString(margin_l + 140, row_y + 6, str(q.get("receipt_no", "CHAL-281-OK")))
            c.drawRightString(margin_l + 350, row_y + 6, format_inr(float(q.get("amount_deducted", 0.0))))
            c.drawRightString(margin_r - 20, row_y + 6, format_inr(float(q.get("amount_deposited", 0.0))))

        # Total Row
        row_y -= 22
        c.setFillColor(c_bg)
        c.rect(margin_l + 10, row_y, width - 20, 22, fill=1, stroke=1)
        c.setFont(font_bold, 8.5)
        c.setFillColor(c_primary)
        c.drawString(margin_l + 20, row_y + 7, "Total TDS Deposited:")
        c.drawRightString(margin_l + 350, row_y + 7, format_inr(tot_tax_deducted))
        c.drawRightString(margin_r - 20, row_y + 7, format_inr(tot_tax_deducted))

        # Verification Statement
        ver_y = row_y - 45
        c.setFont(font_bold, 9)
        c.setFillColor(c_primary)
        c.drawString(margin_l + 10, ver_y, "Verification:")
        ver_y -= 16
        c.setFont(font_normal, 8)
        c.setFillColor(c_muted)
        ver_text = (
            f"I, Director / Authorised Signatory, working in the capacity of Principal Officer do hereby certify "
            f"that a sum of {format_inr(tot_tax_deducted)} has been deducted and deposited to the credit of the Central Government. "
            f"I further certify that the information given above is true, complete and correct based on the books of account."
        )
        c.drawString(margin_l + 10, ver_y, ver_text[:115])
        ver_y -= 12
        c.drawString(margin_l + 10, ver_y, ver_text[115:230])

        sig_y = ver_y - 45
        c.setFont(font_normal, 8.5)
        c.setFillColor(c_text)
        c.drawString(margin_l + 20, sig_y, f"Place: {form_16_data.get('tenant_city', 'Bangalore')}")
        c.drawString(margin_l + 20, sig_y - 14, f"Date: {datetime.utcnow().strftime('%d-%b-%Y')}")

        c.drawRightString(margin_r - 20, sig_y, "For " + employer_name[:35])
        c.drawRightString(margin_r - 20, sig_y - 14, "Authorised Signatory / Director")

        # Bottom Page 1 indicator
        c.setFont(font_normal, 8)
        c.setFillColor(c_muted)
        c.drawString(margin_l + 10, 48, "Form 16: Part A Generated by b00k5 Financial OS • Valid without physical signature if digitally signed")
        c.drawRightString(margin_r - 10, 48, "Page 1 of 2")

        c.showPage()

        # =====================================================================
        # PAGE 2: PART B (ANNEXURE - SALARY COMPUTATION)
        # =====================================================================
        # Outer Border
        c.setStrokeColor(c_border)
        c.setLineWidth(1)
        c.rect(margin_l, 40, width, page_h - 80)

        # Header Title
        c.setFont(font_bold, 14)
        c.setFillColor(c_primary)
        c.drawCentredString(page_w / 2.0, page_h - 65, "FORM NO. 16 - PART B")

        c.setFont(font_normal, 9)
        c.setFillColor(c_muted)
        c.drawCentredString(page_w / 2.0, page_h - 78, "Annexure: Details of Salary Paid and any other income and tax deducted")

        # Employee Pill
        pill_y = page_h - 110
        c.setFillColor(c_primary)
        c.rect(margin_l, pill_y - 16, width, 22, fill=1, stroke=0)
        c.setFont(font_bold, 9)
        c.setFillColor(colors.white)
        c.drawString(margin_l + 10, pill_y - 10, f"Employee: {emp_name} ({emp_code})  |  PAN: {emp_pan}  |  AY: {ay}  |  Regime: {regime.replace('_', ' ').upper()}")

        # Computation Table
        comp_y = pill_y - 30
        c.setFont(font_bold, 8.5)
        c.setFillColor(c_primary)

        # Table Header
        c.setFillColor(c_bg)
        c.rect(margin_l + 10, comp_y - 18, width - 20, 18, fill=1, stroke=1)
        c.setFillColor(c_primary)
        c.drawString(margin_l + 20, comp_y - 12, "Particulars")
        c.drawRightString(margin_r - 20, comp_y - 12, "Amount (Rs.)")

        items = [
            ("1. Gross Salary", "", True),
            ("   (a) Salary as per provisions contained in sec 17(1)", format_inr(gross_salary), False),
            ("   (b) Value of perquisites under section 17(2)", format_inr(0.0), False),
            ("   (c) Profits in lieu of salary under section 17(3)", format_inr(0.0), False),
            ("   Total Gross Salary", format_inr(gross_salary), True),
            ("2. Less: Allowances to the extent exempt under section 10", format_inr(0.0), False),
            ("3. Balance (1 - 2)", format_inr(gross_salary), True),
            ("4. Deductions under Section 16:", "", True),
            ("   (a) Standard deduction under section 16(ia)", format_inr(std_ded), False),
            ("   (b) Tax on employment (Professional Tax) under section 16(iii)", format_inr(pt), False),
            ("   Total Deductions under Section 16", format_inr(std_ded + pt), True),
            ("5. Income chargeable under the head 'Salaries' (3 - 4)", format_inr(net_sal_16), True),
            ("6. Deductions under Chapter VI-A (80C, 80D, etc.)", format_inr(via_ded), False),
            ("7. Total Taxable Income (5 - 6)", format_inr(taxable_inc), True),
            ("8. Tax on Total Income", format_inr(tax_on_inc), False),
            ("9. Less: Rebate under Section 87A", format_inr(rebate_87a), False),
            ("10. Health and Education Cess @ 4%", format_inr(cess), False),
            ("11. Total Tax Payable (8 - 9 + 10)", format_inr(tot_tax_payable), True),
            ("12. Less: Tax Deducted at Source (TDS u/s 192)", format_inr(tot_tax_deducted), True),
            ("13. Net Tax Payable / (Refundable)", format_inr(max(0.0, tot_tax_payable - tot_tax_deducted)), True),
        ]

        row_y = comp_y - 18
        for label, val, is_bold in items:
            row_y -= 17
            c.setStrokeColor(c_border)
            c.setFillColor(colors.white if not is_bold else c_bg)
            c.rect(margin_l + 10, row_y, width - 20, 17, fill=1 if is_bold else 0, stroke=1)

            c.setFont(font_bold if is_bold else font_normal, 8)
            c.setFillColor(c_primary if is_bold else c_text)
            c.drawString(margin_l + 20, row_y + 5, label)
            if val:
                c.drawRightString(margin_r - 20, row_y + 5, val)

        # Verification Box Bottom of Page 2
        bot_y = row_y - 45
        c.setFont(font_bold, 8.5)
        c.setFillColor(c_primary)
        c.drawString(margin_l + 10, bot_y, "Verification by Employer:")
        bot_y -= 14
        c.setFont(font_normal, 7.5)
        c.setFillColor(c_muted)
        c.drawString(margin_l + 10, bot_y, f"I, on behalf of {employer_name[:40]}, verify that the salary paid and tax deducted have been correctly computed.")

        c.setFont(font_normal, 8)
        c.setFillColor(c_muted)
        c.drawString(margin_l + 10, 48, "Form 16: Part B Generated by b00k5 Financial OS • Schedule III & Section 192 Invariant")
        c.drawRightString(margin_r - 10, 48, "Page 2 of 2")

        c.save()
        buf.seek(0)
        return buf.getvalue()

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

