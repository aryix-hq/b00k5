"""
b00k5 - Statutory Bill & Invoice Analysis Model (Indian Accounting & Tax Standards)
Compliant with:
- Companies Act, 2013 (Schedule III Division I/II Nominal Ledger Accounts)
- Central Goods and Services Tax (CGST) Act, 2017 (Section 16(2) ITC Verification)
- Income Tax Act, 1961 (Section 2(41) Financial Year & Section 40A(3) Cash Limits)
"""

import io
import re
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, Tuple, List

from app.core.fiscal_year import get_financial_year, get_assessment_year, is_date_in_fy, get_fy_date_bounds
from app.services.gst_calculator import validate_gstin_checksum, INDIAN_STATE_CODES

GSTIN_REGEX = re.compile(r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b')
PAN_REGEX = re.compile(r'\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b')
TAN_REGEX = re.compile(r'\b([A-Z]{4}[0-9]{5}[A-Z]{1})\b')
HSN_SAC_REGEX = re.compile(r'\b(99[0-9]{4}|[0-9]{4,8})\b')

INVOICE_NUM_PATTERNS = [
    re.compile(r'(?:Invoice\s*Number|Invoice\s*No\.?|Invoice\s*#|Bill\s*Number|Bill\s*No\.?|Bill\s*#|Inv\s*No\.?|Inv\s*#|Tax\s*Invoice\s*(?:No\.?|Number)|Receipt\s*(?:No\.?|Number)|Ref\s*(?:No\.?|Number)|Doc\s*(?:No\.?|Number))[.:\s]*([A-Za-z0-9\-\/]+)', re.I),
    re.compile(r'#\s*([A-Za-z0-9\-\/]{4,20})', re.I)
]

STANDARD_EXPENSE_CATEGORIES = [
    {
        "code": "4010",
        "name": "Cloud Infrastructure & Hosting (AWS/GCP)",
        "schedule_iii": "Other Expenses - Cloud & Hosting",
        "keywords": ["AWS", "AMAZON WEB SERVICES", "GCP", "GOOGLE CLOUD", "AZURE", "HOSTING", "DIGITALOCEAN", "HETZNER", "LINODE", "SERVER", "COMPUTE", "S3", "CLOUDFLARE", "HEROKU", "VERCEL"],
        "display": "[4010] Cloud Infrastructure & Hosting (AWS/GCP)"
    },
    {
        "code": "4020",
        "name": "Software Licenses & SaaS Subscriptions",
        "schedule_iii": "Other Expenses - Software & IT Tools",
        "keywords": ["SOFTWARE", "ZOOM", "GITHUB", "SLACK", "NOTION", "MICROSOFT", "GOOGLE WORKSPACE", "JETBRAINS", "FIGMA", "OPENAI", "ANTHROPIC", "ATLASSIAN", "JIRA", "CONFLUENCE", "ADOBE", "CANVA", "SUBSCRIPTION"],
        "display": "[4020] Software Licenses & SaaS Subscriptions"
    },
    {
        "code": "4030",
        "name": "Payment Gateway & Bank Wire Charges",
        "schedule_iii": "Finance Costs - Bank Charges",
        "keywords": ["RAZORPAY", "STRIPE", "PAYU", "CASHFREE", "HDFC BANK", "ICICI BANK", "WIRE CHARGE", "PROCESSING FEE", "GATEWAY", "MERCHANT FEE", "BANK CHARGES"],
        "display": "[4030] Payment Gateway & Bank Wire Charges"
    },
    {
        "code": "4040",
        "name": "Legal, MCA Compliance & Professional Fees",
        "schedule_iii": "Other Expenses - Legal & Professional",
        "keywords": ["CHARTERED ACCOUNTANT", "LEGAL", "ADVOCATE", "CONSULTING", "COMPANY SECRETARY", "ROC FILING", "MCA", "MINISTRY OF CORPORATE AFFAIRS", "CORPORATE AFFAIRS", "REGISTRAR OF COMPANIES", "CHALLAN", "AUDITOR", "ADVISORY", "SHASTRY", "PROFESSIONAL FEE", "LEGAL EXPENSES"],
        "display": "[4040] Legal, MCA Compliance & Professional Fees"
    },
    {
        "code": "4050",
        "name": "Rent & Office Utilities",
        "schedule_iii": "Other Expenses - Rent, Rates & Taxes",
        "keywords": ["RENT", "CO-WORKING", "WEWORK", "AWFIS", "OFFICE LEASE", "ELECTRICITY", "POWER", "WATER BILL", "MAINTENANCE CHARGES", "SOCIETY"],
        "display": "[4050] Rent & Office Utilities"
    },
    {
        "code": "4060",
        "name": "Office Equipment, Computers & IT Hardware",
        "schedule_iii": "Other Expenses - Office Upkeep",
        "keywords": ["HARDWARE", "LAPTOP", "DESKTOP", "APPLE", "APPLE INDIA", "DELL", "LENOVO", "MONITOR", "CHAIR", "TABLE", "CROMA", "RELIANCE DIGITAL", "PRINTER", "MACBOOK", "IPAD", "IPHONE", "KEYBOARD", "MOUSE"],
        "display": "[4060] Office Equipment, Computers & IT Hardware"
    },
    {
        "code": "4070",
        "name": "Travel, Lodging & Local Conveyance",
        "schedule_iii": "Other Expenses - Travelling & Conveyance",
        "keywords": ["UBER", "OLA", "FLIGHT", "HOTEL", "INDIGO", "AIR INDIA", "MAKEMYTRIP", "IRCTC", "RAILWAY", "CAB", "CONVEYANCE", "BOARDING", "LODGING", "TRAVEL"],
        "display": "[4070] Travel, Lodging & Local Conveyance"
    },
    {
        "code": "4080",
        "name": "Food & Staff Welfare Expenses",
        "schedule_iii": "Employee Benefits Expense - Staff Welfare",
        "keywords": ["SWIGGY", "ZOMATO", "FOOD", "PANTRY", "SNACKS", "BEVERAGE", "CHAI", "COFFEE", "CATERING", "MEAL", "STAFF WELFARE", "DINING"],
        "display": "[4080] Food & Staff Welfare Expenses"
    },
    {
        "code": "4090",
        "name": "Advertising & Digital Marketing",
        "schedule_iii": "Other Expenses - Business Promotion",
        "keywords": ["GOOGLE ADS", "FACEBOOK ADS", "META ADS", "LINKEDIN ADS", "MARKETING", "PROMOTION", "CAMPAIGN", "ADVERTISING", "SEO", "BRANDING"],
        "display": "[4090] Advertising & Digital Marketing"
    },
    {
        "code": "4100",
        "name": "Books, Periodicals & Research",
        "schedule_iii": "Other Expenses - Research & Training",
        "keywords": ["BOOK", "PERIODICAL", "RESEARCH", "MAGAZINE", "JOURNAL", "TRAINING", "UDEMY", "COURSERA", "KINDLE", "O'REILLY"],
        "display": "[4100] Books, Periodicals & Research"
    },
    {
        "code": "4110",
        "name": "Director Remuneration & Board Sitting Fees",
        "schedule_iii": "Employee Benefits Expense - Managerial",
        "keywords": ["DIRECTOR REMUNERATION", "SITTING FEE", "BOARD MEETING FEE", "MANAGERIAL REMUNERATION"],
        "display": "[4110] Director Remuneration & Board Sitting Fees"
    },
    {
        "code": "4120",
        "name": "Repairs & Maintenance",
        "schedule_iii": "Other Expenses - Repairs & Maintenance",
        "keywords": ["REPAIR", "SERVICING", "AMC", "ANNUAL MAINTENANCE", "CLEANING", "PEST CONTROL", "AC SERVICE"],
        "display": "[4120] Repairs & Maintenance"
    },
    {
        "code": "4130",
        "name": "Communication & Internet Charges",
        "schedule_iii": "Other Expenses - Communication",
        "keywords": ["AIRTEL", "JIO", "VODAFONE", "ACT FIBERNET", "BROADBAND", "INTERNET", "TELEPHONE", "CELLULAR", "DATA PLAN"],
        "display": "[4130] Communication & Internet Charges"
    },
    {
        "code": "4140",
        "name": "Auditor Retainer & Certification Fees",
        "schedule_iii": "Other Expenses - Payment to Auditors",
        "keywords": ["STATUTORY AUDIT", "TAX AUDIT", "AUDITOR CERTIFICATE", "AUDIT EXPENSE", "CARO 2020"],
        "display": "[4140] Auditor Retainer & Certification Fees"
    },
    {
        "code": "4150",
        "name": "Printing & Office Stationery",
        "schedule_iii": "Other Expenses - Printing & Stationery",
        "keywords": ["PRINTING", "STATIONERY", "PAPER", "CARTRIDGE", "ENVELOPE", "LETTERHEAD", "OFFICE SUPPLIES"],
        "display": "[4150] Printing & Office Stationery"
    },
    {
        "code": "4160",
        "name": "Marketplace, E-Commerce & Platform Fees",
        "schedule_iii": "Other Expenses - Marketplace & Selling Fees",
        "keywords": ["AMAZON SELLER", "AMAZON SELLER SERVICES", "MARKETPLACE", "SELLER FEE", "FLIPKART", "MEESHO", "COMMISSION", "PLATFORM FEE", "E-COMMERCE"],
        "display": "[4160] Marketplace, E-Commerce & Platform Fees"
    },
    {
        "code": "4199",
        "name": "Miscellaneous Operating Expenses",
        "schedule_iii": "Other Expenses - Miscellaneous",
        "keywords": ["MISCELLANEOUS", "SUNDRY", "OPERATING", "OTHER"],
        "display": "[4199] Miscellaneous Operating Expenses"
    }
]

SCHEDULE_III_EXPENSE_CATEGORIES = STANDARD_EXPENSE_CATEGORIES


class StatutoryBillAnalyzer:
    """
    Intelligent analysis model for Indian bills, tax invoices, receipts, and vouchers.
    Extracts vendor details, GSTIN, invoice numbers, line items, taxes, dates, and computes
    statutory Financial Year and Year Book routing under Indian Accounting Standards.
    """

    @staticmethod
    def extract_text(file_bytes: bytes, filename: str = "", password: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Extracts raw textual stream using layout-aware PDF extraction + Tesseract OCR fallback for scanned images.
        """
        # 1. Image formats (PNG, JPG, JPEG, TIFF, WEBP)
        if file_bytes.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"II*\x00", b"MM\x00*")):
            return StatutoryBillAnalyzer._ocr_image_bytes(file_bytes), None

        # 2. PDF Documents
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            if reader.is_encrypted:
                if not password:
                    return "", {
                        "needs_password": True,
                        "message": "This PDF document is encrypted. Please provide password to unlock."
                    }
                try:
                    dec = reader.decrypt(password)
                    if not dec:
                        return "", {
                            "needs_password": True,
                            "message": "Incorrect password. Please verify and re-enter."
                        }
                except Exception:
                    return "", {
                        "needs_password": True,
                        "message": "Failed to decrypt PDF with the provided password."
                    }

            # First pass: try pdfplumber or pypdf layout text
            pages_text = []
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(file_bytes), password=password) as pdf:
                    for page in pdf.pages:
                        pt = page.extract_text(layout=True) or ""
                        if pt:
                            pages_text.append(pt)
            except Exception:
                for p in reader.pages:
                    pt = p.extract_text() or ""
                    if pt:
                        pages_text.append(pt)

            full_text = "\n".join(pages_text)
            if len(re.sub(r'\s+', '', full_text)) >= 40:
                return full_text, None

            # Second pass: Scanned PDF -> rasterize with pdf2image and run Tesseract OCR
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(file_bytes, first_page=1, last_page=3, userpw=password)
                ocr_pages = []
                for img in images:
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    ocr_pages.append(StatutoryBillAnalyzer._ocr_image_bytes(img_byte_arr.getvalue()))
                scanned_text = "\n".join(ocr_pages)
                if len(scanned_text.strip()) > 10:
                    return scanned_text, None
            except Exception:
                pass

            return full_text, None

        except Exception:
            # Fallback raw character decode
            try:
                decoded = file_bytes.decode("utf-8", errors="ignore")
                return decoded, None
            except Exception:
                return "", None

    @staticmethod
    def _ocr_image_bytes(image_bytes: bytes) -> str:
        """Runs OpenCV enhancement and Tesseract OCR on image bytes."""
        try:
            import cv2
            import numpy as np
            import pytesseract
            from PIL import Image

            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                # Try PIL open
                pil_img = Image.open(io.BytesIO(image_bytes))
                return pytesseract.image_to_string(pil_img) or ""

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Enhance contrast via CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            # Resize if small
            h, w = enhanced.shape
            if w < 1000:
                enhanced = cv2.resize(enhanced, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

            text = pytesseract.image_to_string(enhanced, config='--oem 3 --psm 6')
            return text or ""
        except Exception:
            try:
                import pytesseract
                from PIL import Image
                return pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes))) or ""
            except Exception:
                return ""

    @staticmethod
    def parse_bill_or_invoice(
        file_bytes: bytes,
        filename: str = "",
        password: Optional[str] = None,
        company_gstin: Optional[str] = None,
        closed_fiscal_years: Optional[Dict[str, Any]] = None,
        is_customer_invoice: bool = False
    ) -> Dict[str, Any]:
        """
        Executes end-to-end analysis on vendor bill or customer invoice.
        Extracts vendor/customer, invoice #, date, amounts, taxes, validates FY & Year Book.
        """
        text, pwd_err = StatutoryBillAnalyzer.extract_text(file_bytes, filename=filename, password=password)
        if pwd_err:
            return pwd_err

        # 1. Extract GSTINs
        gstins = GSTIN_REGEX.findall(text.upper())
        valid_gstins = [g for g in gstins if validate_gstin_checksum(g)]
        supplier_gstin = None
        recipient_gstin = None

        clean_company_gstin = (company_gstin or "").strip().upper()
        if clean_company_gstin.startswith("29AABCK9012") or clean_company_gstin.startswith("29AABCA1234"):
            clean_company_gstin = ""

        if valid_gstins:
            for g in valid_gstins:
                if clean_company_gstin and g == clean_company_gstin:
                    recipient_gstin = g
                elif not supplier_gstin:
                    supplier_gstin = g
                elif not recipient_gstin and g != supplier_gstin:
                    recipient_gstin = g

        if not recipient_gstin and clean_company_gstin and clean_company_gstin in text.upper():
            recipient_gstin = clean_company_gstin

        # 2. Extract Invoice / Bill Number
        bill_number = None
        for pat in INVOICE_NUM_PATTERNS:
            m = pat.search(text)
            if m:
                cand = m.group(1).strip().rstrip('.,;')
                if len(cand) >= 2 and not any(w in cand.upper() for w in ["DATE", "TOTAL", "GSTIN", "STATE", "PAGE"]):
                    bill_number = cand
                    break

        if not bill_number:
            bill_number = f"BILL-{uuid.uuid4().hex[:6].upper()}" if not is_customer_invoice else f"INV-{uuid.uuid4().hex[:6].upper()}"

        # 3. Multi-format Date Extraction & Validation
        bill_date = StatutoryBillAnalyzer._extract_date(text)

        # 4. Indian Financial Year & Year Book Routing
        today = date.today()
        is_future = bill_date > (today + timedelta(days=1))
        calc_fy = get_financial_year(bill_date)
        calc_ay = get_assessment_year(bill_date)
        start_dt, end_dt = get_fy_date_bounds(calc_fy)

        # Verify closed year status
        is_closed_fy = False
        prior_period_notice = None
        if closed_fiscal_years and calc_fy in closed_fiscal_years:
            if closed_fiscal_years[calc_fy].get("is_closed"):
                is_closed_fy = True
                prior_period_notice = f"Statutory Notice (AS 5 / Ind AS 8): Financial Year {calc_fy} books are closed. This transaction will be routed to Prior Period Adjustments."

        date_validation = {
            "is_valid": not is_future,
            "parsed_date": bill_date.isoformat(),
            "financial_year": calc_fy,
            "assessment_year": calc_ay,
            "fy_start": start_dt.isoformat(),
            "fy_end": end_dt.isoformat(),
            "is_future_date": is_future,
            "is_prior_period_closed": is_closed_fy,
            "warning": "Date cannot be in the future." if is_future else prior_period_notice
        }

        # 5. Extract Amounts and Taxes
        amounts = StatutoryBillAnalyzer._extract_financial_amounts(text)
        total_amount = amounts["total_amount"]
        taxable_amount = amounts["taxable_amount"]
        cgst_amount = amounts["cgst_amount"]
        sgst_amount = amounts["sgst_amount"]
        igst_amount = amounts["igst_amount"]
        gst_rate = amounts["inferred_gst_rate"]

        # 6. Extract Merchant / Vendor Name
        merchant_name = StatutoryBillAnalyzer._extract_merchant_name(text, filename, is_customer_invoice)

        # 7. Classify into Indian Accounting Standard Nominal Code
        category_meta = StatutoryBillAnalyzer._classify_category(text, merchant_name)
        category_code = category_meta["code"]
        category_name = category_meta["name"]
        category_display = category_meta["display"]

        # 8. ITC Eligibility Check (Section 16(2) CGST Act)
        itc_eligible = False
        itc_reason = ""
        if is_customer_invoice:
            itc_eligible = False
            itc_reason = "Outward Customer Invoice (Sales). Generates Output GST liability."
        elif not clean_company_gstin:
            itc_eligible = False
            itc_reason = "Company is not registered under GST / No Form REG-06 verified. Input Tax Credit (ITC) cannot be claimed."
        elif recipient_gstin == clean_company_gstin:
            itc_eligible = True
            itc_reason = f"Eligible for ITC under Section 16(2) CGST Act (Company GSTIN {clean_company_gstin} matched on supplier invoice)."
        else:
            itc_eligible = False
            itc_reason = "Ineligible for ITC: Company GSTIN is missing on supplier receipt. Full gross booked as business expense."

        # Year Book Navigation metadata
        year_book = {
            "financial_year": calc_fy,
            "assessment_year": calc_ay,
            "label": f"FY {calc_fy} Year Book",
            "tab": "invoices" if is_customer_invoice else "bills",
            "target_url": f"/yearbook?fy={calc_fy}&tab={'invoices' if is_customer_invoice else 'bills'}"
        }

        return {
            "success": True,
            "merchant_name": merchant_name,
            "vendor_name": merchant_name,
            "customer_name": merchant_name if is_customer_invoice else None,
            "bill_number": bill_number,
            "invoice_number": bill_number,
            "bill_date": bill_date.isoformat(),
            "expense_date": bill_date.isoformat(),
            "issue_date": bill_date.isoformat(),
            "date": bill_date.isoformat(),
            "merchant_gstin": supplier_gstin,
            "supplier_gstin": supplier_gstin,
            "recipient_gstin": recipient_gstin,
            "total_amount": float(total_amount),
            "taxable_amount": float(taxable_amount),
            "cgst_amount": float(cgst_amount),
            "sgst_amount": float(sgst_amount),
            "igst_amount": float(igst_amount),
            "gst_rate": gst_rate,
            "category": category_display,
            "category_code": category_code,
            "category_name": category_name,
            "schedule_iii_head": category_meta["schedule_iii"],
            "itc_eligible": itc_eligible,
            "itc_message": itc_reason,
            "date_validation": date_validation,
            "year_book": year_book,
            "raw_text_length": len(text)
        }

    @staticmethod
    def _extract_date(text: str) -> date:
        """
        Multi-pattern statutory date extractor recognizing Indian and international date formats.
        Prioritizes explicit labeled dates (e.g. 'Invoice Date:', 'Date of Issue:', 'Bill Date:'),
        handles month names in both Day-Month-Year and Month-Day-Year orders, dot/slash/hyphen delimiters,
        and converts 2-digit financial years (e.g., '25' -> 2025).
        """
        month_names = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
        }

        def _try_parse_parts(p0: str, p1: str, p2: str) -> Optional[date]:
            p0_clean = p0.strip().rstrip(',')
            p1_clean = p1.strip().rstrip(',')
            p2_clean = p2.strip().rstrip(',')
            # Check if p0 is month name: e.g. Oct 1, 2025 or October 15, 2025
            if p0_clean.lower() in month_names:
                try:
                    m = month_names[p0_clean.lower()]
                    d = int(p1_clean)
                    y = int(p2_clean)
                    if y < 100: y += 2000
                    if 1 <= d <= 31 and 2000 <= y <= 2050:
                        return date(y, m, d)
                except Exception:
                    pass

            # Check if p1 is month name: e.g. 15-Oct-2025 or 1 October 2025
            if p1_clean.lower() in month_names:
                try:
                    m = month_names[p1_clean.lower()]
                    d = int(p0_clean)
                    y = int(p2_clean)
                    if y < 100: y += 2000
                    if 1 <= d <= 31 and 2000 <= y <= 2050:
                        return date(y, m, d)
                except Exception:
                    pass

            # Numeric components
            try:
                # Format: YYYY-MM-DD
                if len(p0_clean) == 4 and p0_clean.isdigit():
                    y = int(p0_clean)
                    m = int(p1_clean)
                    d = int(p2_clean)
                    if 1 <= m <= 12 and 1 <= d <= 31 and 2000 <= y <= 2050:
                        return date(y, m, d)
                # Format: DD-MM-YYYY or DD-MM-YY (Standard Indian)
                elif p0_clean.isdigit() and p1_clean.isdigit() and p2_clean.isdigit():
                    d = int(p0_clean)
                    m = int(p1_clean)
                    y = int(p2_clean)
                    if y < 100: y += 2000
                    if 1 <= m <= 12 and 1 <= d <= 31 and 2000 <= y <= 2050:
                        return date(y, m, d)
            except Exception:
                pass
            return None

        # 1. High Priority: Explicitly labeled date strings
        labeled_regexes = [
            re.compile(r'(?:Invoice\s*Date|Bill\s*Date|Date\s*of\s*Invoice|Date\s*of\s*Issue|Doc\s*Date|Tax\s*Invoice\s*Date|Dated|Date\s*of\s*Payment|Challan\s*Date|Payment\s*Date|\bDate\b)[.:\s]+([0-9]{1,2}[\s\-\/\.][A-Za-z]{3,9}[\s\-\/\.][0-9]{2,4})', re.I),
            re.compile(r'(?:Invoice\s*Date|Bill\s*Date|Date\s*of\s*Invoice|Date\s*of\s*Issue|Doc\s*Date|Tax\s*Invoice\s*Date|Dated|Date\s*of\s*Payment|Challan\s*Date|Payment\s*Date|\bDate\b)[.:\s]+([A-Za-z]{3,9}[\s\-\/\.][0-9]{1,2},?[\s\-\/\.][0-9]{2,4})', re.I),
            re.compile(r'(?:Invoice\s*Date|Bill\s*Date|Date\s*of\s*Invoice|Date\s*of\s*Issue|Doc\s*Date|Tax\s*Invoice\s*Date|Dated|Date\s*of\s*Payment|Challan\s*Date|Payment\s*Date|\bDate\b)[.:\s]+([0-9]{1,2}[\-\/\.][0-9]{1,2}[\-\/\.][0-9]{2,4})', re.I),
            re.compile(r'(?:Invoice\s*Date|Bill\s*Date|Date\s*of\s*Invoice|Date\s*of\s*Issue|Doc\s*Date|Tax\s*Invoice\s*Date|Dated|Date\s*of\s*Payment|Challan\s*Date|Payment\s*Date|\bDate\b)[.:\s]+([0-9]{4}[\-\/\.][0-9]{1,2}[\-\/\.][0-9]{1,2})', re.I),
        ]
        for pat in labeled_regexes:
            match = pat.search(text)
            if match:
                raw_chunk = match.group(1).replace(',', ' ').strip()
                parts = [p for p in re.split(r'[\s\-\/\.]+', raw_chunk) if p]
                if len(parts) == 3:
                    parsed = _try_parse_parts(parts[0], parts[1], parts[2])
                    if parsed:
                        return parsed

        # 2. Unlabeled Text Month (DD Month YYYY or DD-Month-YYYY)
        mon_pat = re.search(r'\b(0?[1-9]|[12][0-9]|3[01])[\s\-\/\.]([A-Za-z]{3,9})[\s\-\/\.](\d{2,4})\b', text)
        if mon_pat:
            parsed = _try_parse_parts(mon_pat.group(1), mon_pat.group(2), mon_pat.group(3))
            if parsed:
                return parsed

        # 3. Unlabeled Month first (Month DD, YYYY e.g. October 1, 2025)
        mon_first_pat = re.search(r'\b([A-Za-z]{3,9})[\s\-\/\.](0?[1-9]|[12][0-9]|3[01]),?[\s\-\/\.](\d{2,4})\b', text)
        if mon_first_pat:
            parsed = _try_parse_parts(mon_first_pat.group(1), mon_first_pat.group(2), mon_first_pat.group(3))
            if parsed:
                return parsed

        # 4. Standard Indian Numeric Format (DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY or DD/MM/YY)
        ind_pat = re.search(r'\b(0?[1-9]|[12][0-9]|3[01])[-/.](0?[1-9]|1[012])[-/.](20[2-3][0-9]|[2-3][0-9])\b', text)
        if ind_pat:
            parsed = _try_parse_parts(ind_pat.group(1), ind_pat.group(2), ind_pat.group(3))
            if parsed:
                return parsed

        # 5. ISO Format: YYYY-MM-DD
        iso_pat = re.search(r'\b(20[2-3][0-9])[-/.](0?[1-9]|1[012])[-/.](0?[1-9]|[12][0-9]|3[01])\b', text)
        if iso_pat:
            parsed = _try_parse_parts(iso_pat.group(1), iso_pat.group(2), iso_pat.group(3))
            if parsed:
                return parsed

        # Default fallback to today
        return date.today()

    @staticmethod
    def _extract_financial_amounts(text: str) -> Dict[str, Any]:
        """Extracts and balances Grand Total, Taxable Amount, and CGST/SGST/IGST breakdown."""
        total_amount = Decimal("0.00")
        taxable_amount = Decimal("0.00")
        cgst_amount = Decimal("0.00")
        sgst_amount = Decimal("0.00")
        igst_amount = Decimal("0.00")

        # Extract Grand Total / Net Payable
        total_matches = re.findall(
            r'(?:Grand\s*Total|Total\s*Amount(?:\s*Due)?|Amount\s*Due|Net\s*Payable|Invoice\s*Total|Amount\s*Payable|Total\s*INR|Total\s*Rs\.?|\bTotal\b)[^\d\n\r]*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)',
            text,
            re.I
        )
        if total_matches:
            # Pick highest reasonable total match
            for cand in total_matches:
                clean = cand.replace(',', '')
                try:
                    val = Decimal(clean)
                    if val > total_amount:
                        total_amount = val
                except Exception:
                    pass

        # If no explicit "Grand Total" label, search currency symbols or last number
        if total_amount == Decimal("0.00"):
            all_amounts = re.findall(r'(?:₹|INR|Rs\.?)\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)', text, re.I)
            for cand in all_amounts:
                clean = cand.replace(',', '')
                try:
                    val = Decimal(clean)
                    if val > total_amount:
                        total_amount = val
                except Exception:
                    pass

        # Extract Taxable Amount / Subtotal
        subtotal_match = re.search(
            r'(?:Taxable\s*Amount|Taxable\s*Value|Sub\s*Total|Subtotal|Base\s*Amount)[^\d\n\r]*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)',
            text,
            re.I
        )
        if subtotal_match:
            try:
                taxable_amount = Decimal(subtotal_match.group(1).replace(',', ''))
            except Exception:
                pass

        # Extract CGST, SGST, IGST (skipping tax rate e.g. @ 18% or 18% or (9%))
        cgst_m = re.search(
            r'(?:CGST|Central\s*GST)(?:\s*\(?(?:@|\bat\b)?\s*\d+(?:\.\d+)?%\)?)?[^\d\n\r]*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)',
            text,
            re.I
        )
        sgst_m = re.search(
            r'(?:SGST|UTGST|State\s*GST)(?:\s*\(?(?:@|\bat\b)?\s*\d+(?:\.\d+)?%\)?)?[^\d\n\r]*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)',
            text,
            re.I
        )
        igst_m = re.search(
            r'(?:IGST|Integrated\s*GST)(?:\s*\(?(?:@|\bat\b)?\s*\d+(?:\.\d+)?%\)?)?[^\d\n\r]*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)',
            text,
            re.I
        )

        if cgst_m:
            try: cgst_amount = Decimal(cgst_m.group(1).replace(',', ''))
            except Exception: pass
        if sgst_m:
            try: sgst_amount = Decimal(sgst_m.group(1).replace(',', ''))
            except Exception: pass
        if igst_m:
            try: igst_amount = Decimal(igst_m.group(1).replace(',', ''))
            except Exception: pass

        tax_sum = cgst_amount + sgst_amount + igst_amount
        inferred_rate = 18

        # Arithmetic balancing
        if total_amount > Decimal("0.00"):
            if taxable_amount > Decimal("0.00"):
                diff = total_amount - taxable_amount
                if tax_sum == Decimal("0.00") and diff > Decimal("0.00"):
                    # Calculate rate and allocate
                    ratio = (diff / taxable_amount) * 100
                    if 17.0 <= ratio <= 19.0:
                        inferred_rate = 18
                        igst_amount = diff
                    elif 11.0 <= ratio <= 13.0:
                        inferred_rate = 12
                        igst_amount = diff
                    elif 4.0 <= ratio <= 6.0:
                        inferred_rate = 5
                        igst_amount = diff
                    elif 27.0 <= ratio <= 29.0:
                        inferred_rate = 28
                        igst_amount = diff
            else:
                if tax_sum > Decimal("0.00") and total_amount > tax_sum:
                    taxable_amount = total_amount - tax_sum
                else:
                    # Reverse calculate standard 18% GST
                    taxable_amount = (total_amount / Decimal("1.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    igst_amount = total_amount - taxable_amount

        return {
            "total_amount": total_amount,
            "taxable_amount": taxable_amount,
            "cgst_amount": cgst_amount,
            "sgst_amount": sgst_amount,
            "igst_amount": igst_amount,
            "inferred_gst_rate": inferred_rate
        }

    @staticmethod
    def _extract_merchant_name(text: str, filename: str = "", is_customer_invoice: bool = False) -> str:
        """Extracts genuine vendor or customer legal name while discarding metadata noise."""
        # For outward customer invoices (including Razorpay-generated invoices), check "Bill To" / "Billed To" / "Customer" first
        if is_customer_invoice:
            bill_to_patterns = [
                r'(?:Billed\s*To|Bill\s*To|Customer\s*Name|Customer\s*Details|Issued\s*To|Buyer|Client)[.:\s]*\n?\s*([^\n\r]+)',
                r'BILLING\s*ADDRESS\s*\n\s*([^\n\r]+)',
            ]
            for pat in bill_to_patterns:
                bill_to_m = re.search(pat, text, re.I)
                if bill_to_m:
                    cand = bill_to_m.group(1).strip()
                    if len(cand) > 2 and not any(w in cand.upper() for w in ["GSTIN", "STATE", "DATE", "ADDRESS", "INVOICE", "RAZORPAY"]):
                        return cand

        # Check known common vendors
        text_upper = text.upper()
        known_vendors = [
            ("AMAZON WEB SERVICES", "Amazon Web Services India Pvt Ltd"),
            ("AWS", "Amazon Web Services India Pvt Ltd"),
            ("GOOGLE CLOUD", "Google Cloud India Private Limited"),
            ("GOOGLE IRELAND", "Google Ireland Limited"),
            ("MICROSOFT", "Microsoft Corporation (India) Pvt Ltd"),
            ("GITHUB", "GitHub, Inc."),
            ("ZOOM", "Zoom Video Communications"),
            ("SLACK", "Slack Technologies LLC"),
            ("NOTION", "Notion Labs, Inc."),
            ("ATLASSIAN", "Atlassian Pty Ltd"),
            ("CLOUDFLARE", "Cloudflare, Inc."),
            ("RAZORPAY", "Razorpay Software Private Limited"),
            ("STRIPE", "Stripe India Private Limited"),
            ("AIRTEL", "Bharti Airtel Limited"),
            ("JIO", "Reliance Jio Infocomm Limited"),
            ("UBER", "Uber India Systems Private Limited"),
            ("OLA", "ANI Technologies Private Limited (Ola)"),
            ("SWIGGY", "Bundl Technologies Pvt Ltd (Swiggy)"),
            ("ZOMATO", "Zomato Limited"),
            ("MAKEMYTRIP", "MakeMyTrip India Pvt Ltd"),
            ("INDIGO", "InterGlobe Aviation Limited (IndiGo)"),
            ("WEWORK", "WeWork India Management Pvt Ltd"),
            ("AWFIS", "Awfis Space Solutions Limited"),
            ("APPLE", "Apple India Private Limited"),
            ("DELL", "Dell India Private Limited"),
            ("S SHASTRY", "S Shastry & Co (Chartered Accountants)"),
            ("RAMAN & ASSOCIATES", "M/s S. Raman & Associates (Statutory Auditors)")
        ]
        if not is_customer_invoice:
            for kw, vname in known_vendors:
                if kw in text_upper:
                    return vname

        # Heuristic line scan: top 12 lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        ignored_keywords = [
            "TAX INVOICE", "ORIGINAL FOR RECIPIENT", "DUPLICATE", "TRIPLICATE", "INVOICE",
            "BILL", "GSTIN", "CIN", "PAN", "DATE", "PAGE", "SUPPLY", "REVERSE CHARGE",
            "HSN", "SAC", "STATE CODE", "TOTAL", "AMOUNT", "DESCRIPTION", "PARTICULARS"
        ]
        for line in lines[:12]:
            clean = re.sub(r'[^A-Za-z0-9\s\.\&,\-]', '', line).strip()
            if len(clean) > 3 and not any(k in clean.upper() for k in ignored_keywords):
                # Ensure contains letters
                if re.search(r'[A-Za-z]{3,}', clean):
                    return clean

        # Filename fallback
        if filename:
            clean_fn = re.sub(r'[\._\-](pdf|png|jpg|jpeg|bill|invoice)', '', filename, flags=re.I).replace('_', ' ').replace('-', ' ').strip()
            if len(clean_fn) > 3:
                return clean_fn.title()

        return "Vendor" if not is_customer_invoice else "Client Enterprise"

    @staticmethod
    def _classify_category(text: str, merchant_name: str) -> Dict[str, Any]:
        """Classifies text into Indian Schedule III accounting category with 4-digit code."""
        combined = f"{text} {merchant_name}".upper()

        # 1. High priority deterministic vendor / activity routing
        if "AMAZON SELLER" in combined or "AMAZON SELLER SERVICES" in combined:
            return next(c for c in STANDARD_EXPENSE_CATEGORIES if c["code"] == "4160")
        if any(k in combined for k in ["MINISTRY OF CORPORATE AFFAIRS", "CORPORATE AFFAIRS", "MCA21", "ROC FILING", "REGISTRAR OF COMPANIES"]):
            return next(c for c in STANDARD_EXPENSE_CATEGORIES if c["code"] == "4040")
        if any(k in combined for k in ["APPLE INDIA", "APPLE.COM", "MACBOOK", "IPAD", "IPHONE", "APPLE "]):
            return next(c for c in STANDARD_EXPENSE_CATEGORIES if c["code"] == "4060")
        if any(k in combined for k in ["RAZORPAY", "STRIPE", "PAYU", "CASHFREE"]):
            return next(c for c in STANDARD_EXPENSE_CATEGORIES if c["code"] == "4030")
        if any(k in combined for k in ["AMAZON WEB SERVICES", " AWS", "AWS ", "GOOGLE CLOUD", "GCP", "AZURE", "DIGITALOCEAN"]):
            return next(c for c in STANDARD_EXPENSE_CATEGORIES if c["code"] == "4010")

        # 2. General keyword scan
        for cat in STANDARD_EXPENSE_CATEGORIES:
            for kw in cat["keywords"]:
                if kw in combined:
                    return cat

        # Default fallback to 4199 Miscellaneous Operating Expenses
        return STANDARD_EXPENSE_CATEGORIES[-1]
