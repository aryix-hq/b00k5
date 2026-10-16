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
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

