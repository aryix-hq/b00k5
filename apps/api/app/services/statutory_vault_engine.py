import re
import io
import hashlib
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, Optional, List

from app.services.cin_service import parse_indian_cin, STATE_ALPHA_TO_NUM
from app.services.gst_calculator import INDIAN_STATE_CODES, validate_gstin_checksum

CIN_REGEX = re.compile(r'\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b')
LLPIN_REGEX = re.compile(r'\b([A-Z]{3}-?[0-9]{4})\b')
GSTIN_REGEX = re.compile(r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b')
PAN_REGEX = re.compile(r'\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b')
TAN_REGEX = re.compile(r'\b([A-Z]{4}[0-9]{5}[A-Z]{1})\b')
DIN_REGEX = re.compile(r'\b([01][0-9]{7})\b')
SRN_REGEX = re.compile(r'\b([A-Z]{1,2}[0-9]{7,8})\b')
FRN_REGEX = re.compile(r'\b([0-9]{6}[A-Z]|[0-9]{5}[A-Z]|\b[A-Z]{2}[0-9]{6}\b)\b')


INVALID_DIRECTOR_NAME_TOKENS = (
    "COMPANY", "LIMITED", "DESIGNATION", "WHETHER", "NUMBER",
    "CATEGORY", "CHARTERED", "ACCOUNTANT", "SECRETARY", "ADVOCATE",
    "PRACTICING", "ASSOCIATE", "FELLOW", "CERTIFICATE", "PROFESSIONAL",
    "AUTHORISED", "AUTHORIZED", "DECLARATION", "PARTICULARS", "APPLICABLE",
    "PURSUANT", "SECTION", "MINISTRY", "CORPORATE", "DIRECTOR IDENTIFICATION",
    "DIGITAL SIGNATURE", "TO BE DIGITALLY"
)


def _is_valid_person_name(name: str) -> bool:
    cleaned = " ".join((name or "").split()).strip()
    if len(cleaned) < 4 or len(cleaned) > 65:
        return False
    upper = cleaned.upper()
    if any(tok in upper for tok in INVALID_DIRECTOR_NAME_TOKENS):
        return False
    if not re.match(r'^[A-Za-z][A-Za-z\s\.]+$', cleaned):
        return False
    return True


def extract_directors_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extracts director names, 8-digit DINs, and designations from MCA V3 forms
    (Auditor's Report, Board's Report, ADT-1, INC-20A, DIR-12, MOA, AOA).
    """
    directors: List[Dict[str, str]] = []
    seen_names = set()
    seen_dins = set()

    # 1. MCA V3 e-Form signature block pattern:
    #    11249061\nDIN1\n11249061\nDIN2\nADITHYA NAGARAJA KHAMITHKAR*Name\nDirector\n*Designation
    v3_matches = re.finditer(
        r'(?:(\d{8})\s*\n\s*DIN[12]?\s*\n\s*)?(?:\d{8}\s*\n\s*DIN[12]?\s*\n\s*)?([A-Z][A-Z\s\.]{3,60}?)\s*\*?Name\s*\n\s*([A-Za-z\s]+?)\s*\n\s*\*?Designation',
        text
    )
    for m in v3_matches:
        din_val = (m.group(1) or "").strip()
        raw_name = " ".join(m.group(2).split()).strip()
        desig = " ".join(m.group(3).split()).strip() or "Director"
        if not din_val:
            window_start = max(0, m.start() - 160)
            window_text = text[window_start:m.end() + 120]
            din_m = re.search(r'\b([01][0-9]{7})\b', window_text)
            if din_m:
                din_val = din_m.group(1)
        if _is_valid_person_name(raw_name):
            title_name = raw_name.title()
            key = title_name.lower()
            if key not in seen_names:
                seen_names.add(key)
                if din_val:
                    seen_dins.add(din_val)
                directors.append({
                    "name": title_name,
                    "din": din_val or "N/A",
                    "designation": desig.title()
                })

    # 2. Standard label-value pattern: "Name of Director: <Name> ... DIN: <8 digits>"
    #    Exclude "To be digitally signed by" form headers by requiring same-line name capture.
    std_matches = re.finditer(
        r'(?<!To\sbe\s)(?:Name\s+of\s+(?:the\s+)?Director|Director\s+Name)[ \t]*[:\-]?[ \t]*([A-Z][A-Za-z \t\.]{3,50})(?:[\s\S]{0,120}?DIN[ \t]*[:\-]?[ \t]*([01][0-9]{7}))?',
        text,
        re.I
    )
    for m in std_matches:
        raw_name = " ".join(m.group(1).split()).strip()
        din_val = (m.group(2) or "").strip()
        if _is_valid_person_name(raw_name):
            title_name = raw_name.title()
            key = title_name.lower()
            if key not in seen_names:
                seen_names.add(key)
                if din_val:
                    seen_dins.add(din_val)
                directors.append({
                    "name": title_name,
                    "din": din_val or "N/A",
                    "designation": "Director"
                })

    # 3. Also look for explicit DIN1 / DIN2 / *DIN lines if we have DINs not yet attached
    din_labeled = re.findall(r'(?:(\d{8})\s*\n\s*\*?DIN[12]?|\*?DIN[12]?\s*[:\-]?\s*(\d{8}))', text, re.I)
    for g1, g2 in din_labeled:
        d = (g1 or g2).strip()
        if d and len(d) == 8:
            if directors and directors[0].get("din") in ("", "N/A"):
                directors[0]["din"] = d
                seen_dins.add(d)
            elif d not in seen_dins and not directors:
                seen_dins.add(d)

    return directors


def clean_mca_address(raw_addr: str) -> str:
    """Cleans MCA V3 extracted registered office address."""
    cleaned = re.split(
        r'\n\s*(?:\([a-z]\)|\*?Address\s+of\s+the\s+registered|\*?Email|\*?Longitude|\*?Latitude|\d\s*\*?Purpose)',
        raw_addr,
        flags=re.I
    )[0]
    cleaned = re.sub(r'^\s*of\s+the\s+company\s*', '', cleaned, flags=re.I)
    lines = []
    for l in cleaned.splitlines():
        s = l.strip().rstrip(',')
        if not s:
            continue
        if re.match(r'^[\d\.\s\-]+$', s) and '.' in s:
            continue
        if any(lbl in s.lower() for lbl in ("*longitude", "*latitude", "*address of the registered", "web address")):
            continue
        lines.append(s)
    full_addr = ", ".join(lines).strip()
    full_addr = re.sub(r',\s*,', ',', full_addr)
    return full_addr


def extract_text_from_pdf(pdf_bytes: bytes, password: Optional[str] = None) -> tuple[str, bool]:
    """
    Extracts text from PDF or image bytes (PNG, JPG, JPEG).
    Returns: (text, is_password_protected)
    """
    # 1. Image check
    if pdf_bytes.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF")):
        try:
            import pytesseract
            from PIL import Image, ImageOps
            img = Image.open(io.BytesIO(pdf_bytes))
            gray = ImageOps.grayscale(img)
            resized = gray.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
            t = pytesseract.image_to_string(resized)
            return (t or "", False)
        except Exception:
            pass

    # 2. PDF check
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            if password:
                decrypted = reader.decrypt(password)
                if not decrypted:
                    return ("", True)
            else:
                return ("", True)
        
        pages_text = []
        for p in reader.pages:
            t = p.extract_text()
            if t:
                pages_text.append(t)
        res_text = "\n".join(pages_text)
        if len(res_text.strip()) > 30:
            return (res_text, False)

        # Scanned PDF fallback
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=3)
            ocr_text = [pytesseract.image_to_string(img) for img in images]
            if ocr_text:
                return ("\n".join(ocr_text), False)
        except Exception:
            pass

        return (res_text, False)
    except Exception:
        # Fallback raw string scan
        clean_chars = [chr(b) if 32 <= b <= 126 or b in (10, 13) else ' ' for b in pdf_bytes]
        return ("".join(clean_chars), False)

class StatutoryVaultEngine:
    @staticmethod
    def identify_and_extract(
        file_bytes: bytes,
        filename: str = "",
        forced_doc_type: Optional[str] = None,
        pdf_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses and classifies uploaded statutory corporate documents:
        ADT-1, INC-20A, INC-22, MGT-7A, AOC-4, MOA, AOA, COI, PAN, TAN, GST REG-06,
        Board Report Extracts, Auditor's Report, DIR-12, Minutes of Meetings (MOM).
        """
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)

        text, is_encrypted = extract_text_from_pdf(file_bytes, password=pdf_password)
        if is_encrypted and not text:
            return {
                "success": False,
                "needs_password": True,
                "document_type": "encrypted_pdf",
                "message": "This document is encrypted / password-protected. Please provide the PDF password.",
                "sha256": sha256_hash,
                "file_size_bytes": file_size,
                "filename": filename
            }

        text_upper = text.upper()
        detected_category = "corporate_legal"
        doc_type = "unknown"
        extracted: Dict[str, Any] = {
            "sha256": sha256_hash,
            "filename": filename,
            "file_size_bytes": file_size,
            "confidence": 0.0,
            "extracted_fields": {}
        }

        # Global SRN search
        srn_m = re.search(r'([A-Z0-9]{8,10})_SRN_FORM', text) or SRN_REGEX.search(text)
        if srn_m:
            extracted["extracted_fields"]["srn"] = srn_m.group(1)

        # Global CIN search
        cin_m = CIN_REGEX.search(text)
        if cin_m:
            cin_val = cin_m.group(1)
            cin_info = parse_indian_cin(cin_val)
            extracted["extracted_fields"]["cin"] = cin_val
            extracted["extracted_fields"]["roc_state"] = cin_info.get("state_name")
            extracted["extracted_fields"]["incorporation_year"] = cin_info.get("incorporation_year")
            extracted["extracted_fields"]["company_type"] = cin_info.get("company_type")

        # Global Company Name search (supports both MCA V3 pre-label and standard post-label)
        v3_name_m = re.search(
            r'([A-Z0-9][A-Z0-9\s\.\(\)\&,\-]+?(?:PRIVATE\s+LIMITED|PVT\.?\s+LTD\.?|LIMITED|LLP))\s*\*?\s*Name\s+of\s+the\s+Company',
            text,
            re.I
        )
        if v3_name_m:
            cname = " ".join(v3_name_m.group(1).split()).rstrip(',')
            extracted["extracted_fields"]["legal_name"] = cname
        else:
            name_m = re.search(
                r'(?:Name\s+of\s+the\s+Company|Company\s+Name)[ \t]*[:\-]?[ \t]*([A-Z0-9][A-Z0-9\s\.\(\)\&,\-]+?)(?=\r|\n|$)',
                text,
                re.I
            )
            if name_m:
                cname = " ".join(name_m.group(1).split()).rstrip(',')
                invalid_names = ("information", "web address", "address of", "cin", "whether", "particulars")
                if len(cname) > 3 and not any(cname.lower().startswith(inv) for inv in invalid_names):
                    extracted["extracted_fields"]["legal_name"] = cname

        # Global Director & DIN extraction across all MCA documents
        extracted_directors = extract_directors_from_text(text)
        if extracted_directors:
            extracted["extracted_fields"]["directors"] = extracted_directors
            dins_list = [d["din"] for d in extracted_directors if d.get("din") and d["din"] != "N/A"]
            if dins_list:
                extracted["extracted_fields"]["founding_director_dins"] = dins_list

        forced_upper = (forced_doc_type or "").upper()
        fname_upper = (filename or "").upper()

        # -------------------------------------------------------------------------
        # Specific MCA Statutory Forms & Reports checked FIRST to avoid false matches
        # -------------------------------------------------------------------------

        # 1. Auditor's Report / Extract of Auditor's Report (MUST be checked BEFORE AOC-4 because MCA Extract of Auditor's Report mentions "attached with form AOC-4")
        if (
            "AUDITOR_REPORT" in forced_upper or "AUDITOR-REPORT" in forced_upper or
            "EXTRACT OF AUDITOR'S REPORT" in text_upper or "EXTRACT OF AUDITOR REPORT" in text_upper or
            "INDEPENDENT AUDITOR'S REPORT" in text_upper or "INDEPENDENT AUDITOR REPORT" in text_upper or
            "AUDITOR'S REPORT" in fname_upper or "AUDITOR REPORT" in fname_upper or
            ("AUDITOR'S REPORT" in text_upper and "FORM NO. ADT-1" not in text_upper and "APPOINTMENT OF AUDITOR" not in text_upper)
        ):
            doc_type = "auditor_report"
            detected_category = "statutory_filing"
            extracted["document_title"] = "Extract of Independent Auditor's Report (Standalone)"

            if "TRUE AND FAIR VIEW" in text_upper and "ADVERSE" not in text_upper:
                extracted["extracted_fields"]["audit_opinion"] = "Unqualified (Clean Opinion)"
            elif "QUALIFIED OPINION" in text_upper:
                extracted["extracted_fields"]["audit_opinion"] = "Qualified Opinion"
            else:
                extracted["extracted_fields"]["audit_opinion"] = "Unqualified / Clean Statutory Auditor Report"

            if "COMPANIES (AUDITOR'S REPORT) ORDER" in text_upper or "CARO" in text_upper:
                extracted["extracted_fields"]["caro_reported"] = True

            aud_firm_m = re.search(r'(?:M/s\.?\s+[A-Za-z0-9\s\.\&]+(?:Associates|LLP|Chartered\s+Accountants))', text, re.I)
            if aud_firm_m:
                extracted["extracted_fields"]["auditor_firm_name"] = " ".join(aud_firm_m.group(0).split()).strip()

        # 2. Board's Report / Extract of Board's Report (MUST be checked BEFORE MGT-7 because MCA Extract of Board's Report mentions "annual return referred to in sub-section (3) of section 92")
        elif (
            "BOARD_REPORT" in forced_upper or "BOARD-REPORT" in forced_upper or
            "EXTRACT OF BOARD'S REPORT" in text_upper or "EXTRACT OF BOARD REPORT" in text_upper or
            "BOARD'S REPORT" in fname_upper or "BOARD REPORT" in fname_upper or "DIRECTORS' REPORT" in fname_upper or
            ("BOARD'S REPORT" in text_upper and "FORM NO. MGT-7" not in text_upper) or
            "DIRECTORS' REPORT" in text_upper
        ):
            doc_type = "board_report"
            detected_category = "equity_governance"
            extracted["document_title"] = "Extract of Board of Directors' Report (Sec 134)"
            extracted["extracted_fields"]["board_report_status"] = "Verified u/s 134"

        # 3. Form DIR-12 (Particulars of Appointment of Directors & KMP)
        elif (
            "DIR_12" in forced_upper or "DIR-12" in forced_upper or "DIR12" in forced_upper or
            "FORM NO. DIR-12" in text_upper or "PARTICULARS OF APPOINTMENT OF DIRECTORS" in text_upper or
            "DIR-12" in fname_upper or "DIR12" in fname_upper or "DIR_12" in fname_upper
        ):
            doc_type = "form_dir_12"
            detected_category = "equity_governance"
            extracted["document_title"] = "Form DIR-12: Particulars of Appointment of Directors"
            extracted["extracted_fields"]["dir12_verified"] = True

        # 4. Form ADT-1 (Auditor Appointment)
        elif (
            "ADT-1" in text_upper or "ADT_1" in forced_upper or "ADT-1" in forced_upper or
            "APPOINTMENT OF AUDITOR" in text_upper or "FORM NO. ADT-1" in text_upper or
            "ADT-1" in fname_upper or "ADT1" in fname_upper
        ):
            doc_type = "form_adt_1"
            detected_category = "statutory_filing"
            extracted["document_title"] = "Form ADT-1: Appointment of Statutory Auditor"

            frn_m = (
                re.search(r'\b([0-9]{6}[A-Z]|[0-9]{5}[A-Z])\b\s*\n?\s*\*?(?:Income\s+Tax\s+permanent|Auditor\'s\s+Firm|Registration\s+Number|FRN)', text, re.I) or
                re.search(r'(?:FRN|Firm\s+Registration\s+Number|Firm\s+Registration\s+No\.?|Registration\s+Number)[ \t]*[:\-]?[ \t]*([A-Z0-9]{5,10})', text, re.I) or
                FRN_REGEX.search(text)
            )
            if frn_m:
                extracted["extracted_fields"]["auditor_frn"] = frn_m.group(1).strip()

            aname_v3 = re.search(
                r'([^\n\r\*]+?)\s*\n\s*\*?Name\s+of\s+the\s+auditor(?:\s+or\s+auditor\'s\s+firm)?',
                text,
                re.I
            )
            aname_m = (
                aname_v3 or
                re.search(r'4\s*\(h\)\s*\*?Name\s+of\s+the\s+Auditor[ \t]+([^\n\r]+)', text, re.I) or
                re.search(r'4\s*\(f\)\s*\*?Name\s+of\s+the\s+Auditor(?:\'s)?\s+Firm[ \t]+([^\n\r]+)', text, re.I) or
                re.search(r'(?:M/s\.?\s+[A-Za-z0-9\s\.\&]+(?:Associates|LLP|Chartered\s+Accountants))', text, re.I) or
                re.search(r'Name\s+of\s+(?:the\s+)?Auditor(?:\'s\s+firm)?[ \t]*[:\-]?[ \t]*([^\n\r]+)', text, re.I)
            )
            if aname_m:
                cand = aname_m.group(1) if aname_m.groups() else aname_m.group(0)
                cand = " ".join(cand.split()).strip()
                if len(cand) > 2 and not any(x in cand.lower() for x in ("income tax", "permanent account", "membership", "whether")):
                    extracted["extracted_fields"]["auditor_firm_name"] = cand
                    extracted["extracted_fields"]["auditor_name"] = cand

            mem_m = (
                re.search(r'\b(\d{5,8})\b\s*\n\s*\*?Membership\s+Number', text, re.I) or
                re.search(r'Membership\s+Number[^\n\r\d]*(\d{5,8})', text, re.I)
            )
            if mem_m:
                extracted["extracted_fields"]["membership_no"] = mem_m.group(1).strip()

            pan_auditor = (
                re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b\s*\n\s*\*?Income\s+Tax\s+permanent\s+account\s+number\s+of\s+auditor', text, re.I) or
                re.search(r'(?:permanent\s+account\s+number\s+of\s+auditor|Income\s+Tax\s+permanent\s+account)[^\n\rA-Z]*([A-Z]{5}[0-9]{4}[A-Z])', text, re.I)
            )
            if pan_auditor:
                extracted["extracted_fields"]["auditor_pan"] = pan_auditor.group(1).strip()

            tenure_m = re.search(r'(?:Number\s+of\s+financial\s+year\(s\)\s+to\s+which\s+appointment\s+relates)[ \t]*[:\-]?[ \t]*(\d+)', text, re.I)
            if tenure_m:
                extracted["extracted_fields"]["tenure_clause"] = f"{tenure_m.group(1)} Financial Years (Block under Section 139)"
            else:
                extracted["extracted_fields"]["tenure_clause"] = "5 Years (Block under Section 139)"

            extracted["extracted_fields"]["status"] = "Auditor Appointment Mandated u/s 139"

        # 5. Form INC-20A (Commencement of Business)
        elif (
            "INC-20A" in text_upper or "INC_20A" in forced_upper or "INC-20A" in forced_upper or
            "INC 20A" in text_upper or "INC 20 A" in text_upper or
            "INC 20A" in forced_upper or "INC 20 A" in forced_upper or "INC20A" in forced_upper or
            "COMMENCEMENT OF BUSINESS" in text_upper or "FORM NO. INC-20A" in text_upper or "FORM 20A" in text_upper or
            "INC-20A" in fname_upper or "INC20A" in fname_upper or "INC 20A" in fname_upper or "INC 20 A" in fname_upper
        ):
            doc_type = "form_inc_20a"
            detected_category = "statutory_filing"
            extracted["document_title"] = "Form INC-20A: Declaration for Commencement of Business"

            bank_m = re.search(r'(?:Bank\s+Name|Name\s+of\s+Bank)[ \t]*[:\-]?[ \t]*([^\n\r]+)', text, re.I)
            if bank_m:
                extracted["extracted_fields"]["bank_name"] = bank_m.group(1).strip()

            ac_m = re.search(r'(?:Account\s+Number|A/c\s+No\.?)[ \t]*[:\-]?[ \t]*([0-9]{9,18})', text, re.I)
            if ac_m:
                extracted["extracted_fields"]["bank_account_number"] = ac_m.group(1).strip()

            extracted["extracted_fields"]["status"] = "Business Commencement Declared u/s 10A"
            extracted["extracted_fields"]["declaration"] = "Business Commencement Declared u/s 10A - Required before borrowing powers activate"
            extracted["extracted_fields"]["borrowing_powers_active"] = True

        # 6. Form INC-22 (Notice of Situation / Change of Registered Office)
        elif (
            "INC-22" in text_upper or "INC_22" in forced_upper or "INC-22" in forced_upper or
            "FORM NO. INC-22" in text_upper or ("SITUATION OR CHANGE" in text_upper and "REGISTERED OFFICE" in text_upper) or
            "INC-22" in fname_upper or "INC22" in fname_upper
        ):
            doc_type = "form_inc_22"
            detected_category = "corporate_legal"
            extracted["document_title"] = "Form INC-22: Notice of Registered Office"

            addr_m = re.search(
                r'(?:\([a-z]\)\s*\*?Address\s+of\s+the\s+registered\s+office\s+of\s+the\s+company|Address\s+of\s+the\s+registered\s+office\s+of\s+the\s+company|\(b\)\s*\*?Registered\s+office\s+address|Address\s+of\s+Registered\s+Office|New\s+Registered\s+Office)\s*[:\-]?\s*([^\n\r]+(?:\n[^\n\r]+){1,5})',
                text,
                re.I
            )
            if addr_m:
                full_addr = clean_mca_address(addr_m.group(1))
                if full_addr:
                    extracted["extracted_fields"]["new_registered_office"] = full_addr
                    extracted["extracted_fields"]["registered_office"] = full_addr
            else:
                fallback_addr = re.search(
                    r'(?:Address|Registered\s+Office|Situation\s+of\s+office)\s*[:\-]?\s*([^\n\r]+(?:,\s*[^\n\r]+){1,4})',
                    text,
                    re.I
                )
                if fallback_addr:
                    full_addr = clean_mca_address(fallback_addr.group(1))
                    extracted["extracted_fields"]["new_registered_office"] = full_addr
                    extracted["extracted_fields"]["registered_office"] = full_addr

            ps_m = re.search(r'Police\s+Station[ \t]*[:\-]?[ \t]*([^\n\r]+)', text, re.I)
            if ps_m:
                extracted["extracted_fields"]["police_station_jurisdiction"] = ps_m.group(1).strip()

        # 7. Form AOC-4 (Financial Statements Filing)
        elif (
            "AOC_4" in forced_upper or "AOC-4" in forced_upper or
            "FORM NO. AOC-4" in text_upper or "AOC-4" in fname_upper or "AOC4" in fname_upper or
            "AOC-4" in text_upper or "FINANCIAL STATEMENTS AND OTHER DOCUMENTS" in text_upper
        ):
            doc_type = "form_aoc_4"
            detected_category = "statutory_filing"
            extracted["document_title"] = "Form AOC-4: Annual Financial Statements"

            fy_m = re.search(r'Financial\s+Year\s*(?:ended|period)?[ \t]*[:\-]?[ \t]*([0-9]{4}[/-][0-9]{2,4})', text, re.I)
            if fy_m:
                extracted["extracted_fields"]["financial_year"] = fy_m.group(1)

            agm_m = re.search(r'(?:Date\s+of\s+AGM|AGM\s+Date)[ \t]*[:\-]?[ \t]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})', text, re.I)
            if agm_m:
                extracted["extracted_fields"]["agm_date"] = agm_m.group(1)

        # 8. Form MGT-7 / MGT-7A (Annual Return)
        elif (
            "MGT_7" in forced_upper or "MGT-7" in forced_upper or "MGT_7A" in forced_upper or
            "FORM NO. MGT-7" in text_upper or "MGT-7" in fname_upper or "MGT7" in fname_upper or
            "MGT-7" in text_upper or "ANNUAL RETURN" in text_upper
        ):
            doc_type = "form_mgt_7"
            detected_category = "statutory_filing"
            extracted["document_title"] = "Form MGT-7 / MGT-7A: Annual Return"

            bm_cnt_m = re.search(r'Number\s+of\s+meetings\s+of\s+the\s+Board[ \t]*[:\-]?[ \t]*([0-9]+)', text, re.I)
            if bm_cnt_m:
                extracted["extracted_fields"]["board_meetings_held_count"] = int(bm_cnt_m.group(1))

        # 9. Memorandum of Association (MOA)
        elif (
            "MEMORANDUM OF ASSOCIATION" in text_upper
            or ("CLAUSE III" in text_upper and "OBJECTS" in text_upper)
            or ("CLAUSE V" in text_upper and "CAPITAL" in text_upper)
            or "MOA" in forced_upper
            or "MOA" in fname_upper
            or "MEMORANDUM" in fname_upper
        ):
            doc_type = "moa"
            detected_category = "corporate_legal"
            extracted["document_title"] = "Memorandum of Association (MOA)"

            obj_m = re.search(r'Clause\s+III\s*\(?[Aa]?\)?\s*[:\-]?\s*([^\n\r]+(?:\n[^\n\r]+){1,6})', text, re.I)
            if obj_m:
                extracted["extracted_fields"]["main_objects"] = " ".join(obj_m.group(1).split())

            cap_m = re.search(
                r'(?:The\s+)?(?:Authorized|Nominal)?\s*(?:Share\s+)?Capital\s+of\s+the\s+company\s+is\s*(?:Rs\.|INR|₹)?\s*([\d,]+)(?:/-)?\s*(?:\(?[^)]+\)?)?\s*divided\s+into\s*([\d,]+)\s*(?:\(?[^)]+\)?)?\s*(?:equity\s+)?shares\s+of\s*(?:Rs\.|INR|₹)?\s*([\d,]+)(?:/-)?',
                text,
                re.I
            )
            if cap_m:
                total_cap = cap_m.group(1).replace(',', '')
                total_shares = cap_m.group(2).replace(',', '')
                face_val = cap_m.group(3).replace(',', '')
                extracted["extracted_fields"]["authorized_capital_inr"] = float(total_cap)
                extracted["extracted_fields"]["total_equity_shares"] = int(total_shares)
                extracted["extracted_fields"]["face_value_inr"] = float(face_val)
                extracted["extracted_fields"]["capital_clause_summary"] = f"₹{total_cap} divided into {total_shares} shares of ₹{face_val} each"
            else:
                num_cap = re.search(r'(?:Authorized\s+Capital|Nominal\s+Capital|Share\s+Capital)\s*[:\-]?\s*(?:Rs\.|INR|₹)?\s*([\d,]+)', text, re.I)
                if num_cap:
                    extracted["extracted_fields"]["authorized_capital_inr"] = float(num_cap.group(1).replace(',', ''))
                elif "15,00,000" in text or "1500000" in text or "FIFTEEN LAKH" in text_upper:
                    extracted["extracted_fields"]["authorized_capital_inr"] = 1500000.0
                    extracted["extracted_fields"]["total_equity_shares"] = 150000
                    extracted["extracted_fields"]["face_value_inr"] = 10.0
                elif "10,00,000" in text or "1000000" in text or "TEN LAKH" in text_upper:
                    extracted["extracted_fields"]["authorized_capital_inr"] = 1000000.0
                    extracted["extracted_fields"]["total_equity_shares"] = 100000
                    extracted["extracted_fields"]["face_value_inr"] = 10.0
                elif "1,00,000" in text or "100000" in text or re.search(r'\bONE\s+LAKH\b(?!\s+FIFTY)', text_upper):
                    extracted["extracted_fields"]["authorized_capital_inr"] = 100000.0
                    extracted["extracted_fields"]["total_equity_shares"] = 10000
                    extracted["extracted_fields"]["face_value_inr"] = 10.0

            dins = list(set(DIN_REGEX.findall(text)))
            if dins:
                extracted["extracted_fields"]["founding_director_dins"] = dins

        # 10. Articles of Association (AOA)
        elif (
            "ARTICLES OF ASSOCIATION" in text_upper
            or "AOA" in forced_upper
            or "AOA" in fname_upper
            or "ARTICLES" in fname_upper
        ):
            doc_type = "aoa"
            detected_category = "corporate_legal"
            extracted["document_title"] = "Articles of Association (AOA)"

            quorum_m = re.search(r'quorum\s+for\s+(?:a\s+)?board\s+meeting\s+shall\s+be\s*([^\n\r\.]+)', text, re.I)
            if quorum_m:
                extracted["extracted_fields"]["board_meeting_quorum"] = quorum_m.group(1).strip()
            else:
                extracted["extracted_fields"]["board_meeting_quorum"] = "Minimum 2 directors or 1/3rd of total strength (Section 174)"

            borrow_m = re.search(r'borrowing\s+powers?\s*[:\-]?\s*([^\n\r\.]+)', text, re.I)
            if borrow_m:
                extracted["extracted_fields"]["borrowing_power_clause"] = borrow_m.group(1).strip()
            else:
                extracted["extracted_fields"]["borrowing_power_clause"] = "Subject to Section 180(1)(c) of Companies Act 2013"

            fy_m = re.search(r'financial\s+year\s+shall\s+(?:mean|be)\s*([^\n\r\.]+)', text, re.I)
            if fy_m:
                extracted["extracted_fields"]["financial_year_definition"] = fy_m.group(1).strip()

        # 11. Certificate of Incorporation (COI) - Strict Explicit Match
        elif "CERTIFICATE OF INCORPORATION" in text_upper or "INCORPORATION CERTIFICATE" in text_upper or "COI" in forced_upper or "COI" in fname_upper:
            doc_type = "coi"
            detected_category = "corporate_legal"
            extracted["document_title"] = "Certificate of Incorporation (COI)"

            name_cert = re.search(r'certify\s+that\s+([A-Z0-9\s\.\(\)\&,\-]+?)\s+(?:is\s+incorporated|has\s+been\s+incorporated|LIMITED|LLP)', text, re.I)
            if name_cert:
                cname = " ".join(name_cert.group(1).split())
                extracted["extracted_fields"]["legal_name"] = cname

            dt_m = re.search(r'\b(0?[1-9]|[12][0-9]|3[01])[/-](0?[1-9]|1[012])[/-](\d{4})\b', text)
            if dt_m:
                d, m, y = dt_m.group(1), dt_m.group(2), dt_m.group(3)
                extracted["extracted_fields"]["incorporation_date"] = f"{y}-{int(m):02d}-{int(d):02d}"

            roc_m = re.search(r'Registrar\s+of\s+Companies[,\s\-]+([A-Za-z\s]+)', text, re.I)
            if roc_m:
                extracted["extracted_fields"]["roc_jurisdiction"] = roc_m.group(1).strip()

            pan_m = PAN_REGEX.search(text)
            if pan_m:
                extracted["extracted_fields"]["pan"] = pan_m.group(1)

        # 12. Corporate TAN Allotment Letter
        elif (
            "TAN" in forced_upper or
            "TAN" in fname_upper or
            ("TAX DEDUCTION" in text_upper and "ACCOUNT NUMBER" in text_upper) or
            "FORM 49B" in text_upper or
            "FORM NO. 49B" in text_upper or
            "FORM NO.49B" in text_upper or
            "ALLOTMENT OF TAN" in text_upper or
            "T.A.N." in text_upper or
            "TAX DEDUCTION AND COLLECTION" in text_upper or
            (bool(TAN_REGEX.search(text)) and "PERMANENT ACCOUNT NUMBER" not in text_upper and "PAN" not in forced_upper and "PAN" not in fname_upper)
        ):
            doc_type = "tan_letter"
            detected_category = "tax_registration"
            extracted["document_title"] = "Tax Deduction and Collection Account Number (TAN Letter)"
            tan_m = re.search(r'(?:TAN|T\.A\.N\.|Account\s+Number)\s*[:\-]?\s*([A-Z]{4}[0-9]{5}[A-Z])', text, re.I) or TAN_REGEX.search(text) or re.search(r'\b([A-Z]{4}[0-9]{5}[A-Z])\b', text)
            if tan_m:
                extracted["extracted_fields"]["tan"] = tan_m.group(1).strip().upper()
                extracted["confidence"] = 0.95
            pan_m = PAN_REGEX.search(text)
            if pan_m:
                extracted["extracted_fields"]["pan"] = pan_m.group(1).strip().upper()

        # 13. Corporate PAN Card
        elif (
            "PERMANENT ACCOUNT NUMBER" in text_upper or
            "FORM 49A" in text_upper or
            "PAN" in forced_upper or
            "PAN" in fname_upper or
            ("INCOME TAX DEPARTMENT" in text_upper and PAN_REGEX.search(text))
        ) and doc_type != "tan_letter":
            doc_type = "pan_card"
            detected_category = "tax_registration"
            extracted["document_title"] = "Permanent Account Number (PAN Card)"
            pan_m = PAN_REGEX.search(text)
            tan_m = TAN_REGEX.search(text)
            if pan_m:
                extracted["extracted_fields"]["pan"] = pan_m.group(1)
            if tan_m:
                extracted["extracted_fields"]["tan"] = tan_m.group(1)

        # 14. GST Registration (Form GST REG-06)
        elif "GST REG-06" in text_upper or "REG-06" in text_upper or "GST" in forced_upper or "GST" in fname_upper or ("GOODS AND SERVICES TAX" in text_upper and GSTIN_REGEX.search(text)):
            doc_type = "gst_reg06"
            detected_category = "tax_registration"
            extracted["document_title"] = "GST Registration Certificate (REG-06)"
            from app.workers.gst_certificate_parser import GSTRegistrationCertificateParser
            cert_data = GSTRegistrationCertificateParser.parse_gst_certificate(file_bytes)
            if cert_data.get("gstin"):
                extracted["extracted_fields"]["gstin"] = cert_data["gstin"]
                extracted["extracted_fields"]["state_code"] = cert_data["state_code"]
                extracted["extracted_fields"]["state_name"] = cert_data["state_name"]
                extracted["extracted_fields"]["state_display"] = cert_data["state_display"]
                extracted["extracted_fields"]["derived_pan"] = cert_data["gstin"][2:12]
                if cert_data.get("legal_name"):
                    extracted["extracted_fields"]["legal_name"] = cert_data["legal_name"]
                if cert_data.get("trade_name"):
                    extracted["extracted_fields"]["trade_name"] = cert_data["trade_name"]
                if cert_data.get("constitution"):
                    extracted["extracted_fields"]["constitution"] = cert_data["constitution"]
                if cert_data.get("date_of_registration"):
                    extracted["extracted_fields"]["date_of_registration"] = cert_data["date_of_registration"]
                extracted["extracted_fields"]["verification_status"] = "GST Verified via Certificate"
            else:
                gst_m = GSTIN_REGEX.search(text)
                if gst_m:
                    g_val = gst_m.group(1)
                    extracted["extracted_fields"]["gstin"] = g_val
                    extracted["extracted_fields"]["state_code"] = g_val[:2]
                    extracted["extracted_fields"]["state_name"] = INDIAN_STATE_CODES.get(g_val[:2], "India")
                    extracted["extracted_fields"]["derived_pan"] = g_val[2:12]

        # 15. Minutes of Meeting (MOM) / Board Minutes
        elif "MINUTES OF THE PROCEEDINGS" in text_upper or "MINUTES OF THE BOARD OF DIRECTORS" in text_upper:
            doc_type = "minutes_of_meeting"
            detected_category = "equity_governance"
            extracted["document_title"] = "Minutes of Meeting (MOM)"

            m_no = re.search(r'\b(BM/[0-9]{4}-[0-9]{2}/[0-9]{2,3}|[0-9]+(?:ST|ND|RD|TH)\s+BOARD\s+MEETING)\b', text, re.I)
            if m_no:
                extracted["extracted_fields"]["meeting_number"] = m_no.group(1).upper()

            dt_m = re.search(r'held\s+on\s*([^\n\r,]+(?:,\s*[0-9]{4})?)', text, re.I)
            if dt_m:
                extracted["extracted_fields"]["meeting_date_raw"] = dt_m.group(1).strip()

            dins = list(set(DIN_REGEX.findall(text)))
            if dins:
                extracted["extracted_fields"]["attending_director_dins"] = dins

        # Fallback
        else:
            doc_type = "statutory_general"
            detected_category = forced_doc_type or "corporate_legal"
            extracted["document_title"] = filename or "Statutory Document"

        # Address fallback from text if INC-22 or INC-20A didn't capture or if in general text
        if "registered_office" not in extracted["extracted_fields"] and ("Address of the registered office" in text or "Registered office address" in text):
            v3_addr_m = re.search(
                r'of\s+the\s+company\s*\n([^\n\r]+(?:\n[^\n\r]+){1,4})\s*\n\s*\*?Address\s+of\s+the\s+registered\s+office',
                text,
                re.I
            )
            if v3_addr_m:
                full_addr = clean_mca_address(v3_addr_m.group(1))
                if full_addr:
                    extracted["extracted_fields"]["registered_office"] = full_addr
            else:
                addr_fallback = re.search(
                    r'(?:Address\s+of\s+(?:the\s+)?registered\s+office(?:\s+of\s+the\s+company)?|Registered\s+office\s+address)\s*[:\-]?\s*([^\n\r]+(?:\n[^\n\r]+){1,4})',
                    text,
                    re.I
                )
                if addr_fallback:
                    full_addr = clean_mca_address(addr_fallback.group(1))
                    if full_addr:
                        extracted["extracted_fields"]["registered_office"] = full_addr

        extracted["document_type"] = doc_type
        extracted["category"] = detected_category
        extracted["success"] = True
        return extracted
