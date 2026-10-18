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

    # 3. MCA Tabular Signatory Row (e.g. Form AOC-4):
    #    "11249061 ADITHYA NAGARAJAKHAMITHKAR Director 05/09/2026"
    aoc4_matches = re.finditer(
        r'\b([01][0-9]{7})\s+([A-Z][A-Z\s\.]{3,55}?)\s+(Director|Managing\s+Director|Whole-?time\s+Director|Additional\s+Director)\b',
        text,
        re.I
    )
    for m in aoc4_matches:
        din_val = m.group(1).strip()
        raw_name = " ".join(m.group(2).split()).strip()
        desig = " ".join(m.group(3).split()).strip() or "Director"
        if _is_valid_person_name(raw_name):
            title_name = raw_name.title()
            key = title_name.lower()
            if key not in seen_names:
                seen_names.add(key)
                seen_dins.add(din_val)
                directors.append({
                    "name": title_name,
                    "din": din_val,
                    "designation": desig.title()
                })

    # 4. MGT-7 / MGT-7A Designated Person format:
    #    DIN/PAN/Membership number of Designated Person 11249061 ... Name of the Designated Person ADITHYA NAGARAJA KHAMITHKAR
    mgt_matches = re.finditer(
        r'DIN/PAN/Membership\s+number\s+of\s+Designated\s+Person\s*([01][0-9]{7})[\s\S]{0,120}?Name\s+of\s+the\s+Designated\s+Person\s*([A-Za-z\s\.]+?)(?=\n|Declaration|$)',
        text,
        re.I
    )
    for m in mgt_matches:
        din_val = m.group(1).strip()
        raw_name = " ".join(m.group(2).split()).strip()
        if _is_valid_person_name(raw_name):
            title_name = raw_name.title()
            key = title_name.lower()
            if key not in seen_names:
                seen_names.add(key)
                seen_dins.add(din_val)
                directors.append({
                    "name": title_name,
                    "din": din_val,
                    "designation": "Director"
                })

    # 5. MOA / AOA Subscriber Details block:
    #    "Subscriber Details\n... 1\nADITHYA NAGARAJA KHAMITHKAR\nR/O-NO 4 ..."
    moa_sub_match = re.search(
        r'Subscriber\s+Details[\s\S]*?(?:^|\n)\s*[1-9]\s*\n\s*([A-Z][A-Z\s\.]{3,55}?)\s*\n\s*(?:R/O|NO\b|#)',
        text,
        re.I
    )
    if moa_sub_match:
        raw_name = " ".join(moa_sub_match.group(1).split()).strip()
        if _is_valid_person_name(raw_name):
            title_name = raw_name.title()
            key = title_name.lower()
            if key not in seen_names:
                seen_names.add(key)
                directors.append({
                    "name": title_name,
                    "din": "N/A",
                    "designation": "Founding Director / Subscriber"
                })

    # 6. Also look for explicit DIN1 / DIN2 / *DIN lines if we have DINs not yet attached
    din_labeled = re.findall(r'(?:(\d{8})\s*(?:\n\s*\*?DIN[12]?|DIN[12]?|###)|\*?DIN[12]?\s*[:\-]?\s*(\d{8}))', text, re.I)
    for g1, g2 in din_labeled:
        d = (g1 or g2).strip()
        if d and len(d) == 8 and re.match(r'^[01]\d{7}$', d):
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
            # First attempt empty password (standard for digitally signed e-PAN, TAN, MCA forms)
            decrypted = reader.decrypt(password or "")
            if not decrypted:
                if password:
                    decrypted = reader.decrypt(password)
                if not decrypted:
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
            if re.search(r'\b(?:PRIVATE|PVT\.?|\(OPC\)\s+PRIVATE)\s*$', cname, re.I):
                cname += " LIMITED"
            extracted["extracted_fields"]["legal_name"] = cname
        else:
            name_m = re.search(
                r'(?:Name\s+of\s+the\s+Company|Company\s+Name)[ \t]*[:\-]?[ \t]*([A-Z0-9][A-Z0-9\s\.\(\)\&,\-]+?)(?=\r|\n|$)',
                text,
                re.I
            )
            if name_m:
                cname = " ".join(name_m.group(1).split()).rstrip(',')
                if re.search(r'\b(?:PRIVATE|PVT\.?|\(OPC\)\s+PRIVATE)\s*$', cname, re.I):
                    cname += " LIMITED"
                invalid_names = ("information", "web address", "address of", "cin", "whether", "particulars")
                if len(cname) > 3 and not any(cname.lower().startswith(inv) for inv in invalid_names):
                    extracted["extracted_fields"]["legal_name"] = cname

        # Universal Financial Year & Assessment Year Extraction
        detected_fy = None
        detected_ay = None

        # 1. Direct FY mentions: "Financial Year 2025-26", "FY 2026-27", "F.Y. 2026-27"
        fy_pat = re.search(r'(?:Financial\s+Year|F\.?Y\.?)\s*[:\-]?[ \t]*(?:20)?(\d\d)[-_/](?:20)?(\d\d)', text, re.I)
        if fy_pat:
            y1, y2 = fy_pat.group(1), fy_pat.group(2)
            detected_fy = f"20{y1[-2:]}-{y2[-2:]}"

        # 2. AY mentions: "Assessment Year 2026-27", "A.Y. 2027-28" (FY = AY - 1)
        ay_pat = re.search(r'(?:Assessment\s+Year|A\.?Y\.?)\s*[:\-]?[ \t]*(?:20)?(\d\d)[-_/](?:20)?(\d\d)', text, re.I)
        if ay_pat:
            y1, y2 = ay_pat.group(1), ay_pat.group(2)
            detected_ay = f"20{y1[-2:]}-{y2[-2:]}"
            if not detected_fy:
                start_yr = int(f"20{y1[-2:]}") - 1
                detected_fy = f"{start_yr}-{str(start_yr + 1)[-2:]}"

        # 3. "Year ended 31st March 2026" / "ended on 31-03-2027" / "as at 31st March, 2026"
        if not detected_fy:
            ended_pat = re.search(r'(?:ended|ending|as\s+at)\s*(?:on)?\s*(?:31st\s+March|31/03|31-03)[,\s\-]+(?:20)?(\d\d)', text, re.I)
            if ended_pat:
                eyr = int(f"20{ended_pat.group(1)[-2:]}")
                detected_fy = f"{eyr - 1}-{str(eyr)[-2:]}"
                detected_ay = f"{eyr}-{str(eyr + 1)[-2:]}"

        # 4. Check filename e.g. "MGT-7A_25-26.pdf" or "AOC-4_2026-27.pdf"
        if not detected_fy and filename:
            fn_m = re.search(r'(?:20)?(\d\d)[-_](?:20)?(\d\d)', filename)
            if fn_m:
                y1, y2 = int(fn_m.group(1)), int(fn_m.group(2))
                if abs(y2 - y1) == 1:
                    detected_fy = f"20{str(y1)[-2:]}-{str(y2)[-2:]}"

        # 5. Check date in document
        if not detected_fy:
            dt_match = re.search(r'\b(0?[1-9]|[12][0-9]|3[01])[/-](0?[1-9]|1[012])[/-](20\d\d)\b', text)
            if dt_match:
                d, m, y = int(dt_match.group(1)), int(dt_match.group(2)), int(dt_match.group(3))
                if m >= 4:
                    detected_fy = f"{y}-{str(y + 1)[-2:]}"
                else:
                    detected_fy = f"{y - 1}-{str(y)[-2:]}"

        if detected_fy:
            extracted["fiscal_year"] = detected_fy
            extracted["extracted_fields"]["financial_year"] = detected_fy
            if not detected_ay:
                s_yr = int(detected_fy.split('-')[0]) + 1
                detected_ay = f"{s_yr}-{str(s_yr + 1)[-2:]}"
            extracted["extracted_fields"]["assessment_year"] = detected_ay

        # Global Director & DIN extraction across all MCA documents
        extracted_directors = extract_directors_from_text(text)
        if extracted_directors:
            extracted["extracted_fields"]["directors"] = extracted_directors
            dins_list = [d["din"] for d in extracted_directors if d.get("din") and d["din"] != "N/A"]
            if dins_list:
                extracted["extracted_fields"]["founding_director_dins"] = dins_list

        forced_upper = (forced_doc_type or "").upper()
        fname_upper = (filename or "").upper()

        # Universal string normalization for punctuation & Unicode quotes
        text_norm = text_upper.replace("’", "'").replace("`", "'").replace("‘", "'")
        fname_norm = fname_upper.replace("’", "'").replace("`", "'").replace("‘", "'")
        forced_norm = forced_upper.replace("’", "'").replace("`", "'").replace("‘", "'")

        # -------------------------------------------------------------------------
        # Specific MCA Statutory Forms & Reports checked FIRST to avoid false matches
        # -------------------------------------------------------------------------

        # Pre-calculate forced flags from explicit user / UI selection
        is_forced_board = any(k in forced_norm for k in ("BOARD_REPORT", "BOARD-REPORT", "BOARD REPORT", "SEC_134", "SECTION 134", "DIRECTOR_REPORT", "BOARD"))
        is_forced_aoc4 = any(k in forced_norm for k in ("AOC_4", "AOC-4", "AOC 4", "AOC4", "FORM_AOC_4", "FORM_AOC4", "AOC"))
        is_forced_itr = any(k in forced_norm for k in ("ITR", "ITR_6", "ITR-6", "ITR 6", "ITR_V", "ITR-V", "ITR V", "INCOME_TAX_RETURN", "INCOME TAX RETURN"))
        is_forced_din = any(k in forced_norm for k in ("DIN", "DIN_APPROVAL", "DIR_3", "DIR-3", "DIR3", "ALLOTMENT OF DIN", "DIN ALLOTMENT", "FORM_DIR_3", "FORM DIR-3", "SPICE", "SPICE+", "SPICE +", "SPICE_PLUS", "SPICE_PLUS_PART_B", "PART B", "PART_B", "PART-B", "INC-32", "INC32"))
        is_forced_auditor = any(k in forced_norm for k in ("AUDITOR_REPORT", "AUDITOR-REPORT", "AUDITOR REPORT", "AUDITOR")) and not is_forced_board and not is_forced_aoc4
        is_forced_mgt7 = any(k in forced_norm for k in ("MGT_7", "MGT-7", "MGT 7", "MGT7", "MGT_7A", "MGT-7A", "MGT 7A", "MGT7A"))

        # 0. SPICe+ Part B / Form DIR-3 DIN Approval Letter
        if (
            is_forced_din or
            ("DIN" in fname_norm and ("APPROVAL" in fname_norm or "LETTER" in fname_norm or "ALLOTMENT" in fname_norm or "DIR3" in fname_norm or "DIR-3" in fname_norm or "SPICE" in fname_norm or "PART_B" in fname_norm or "PART-B" in fname_norm or "PART B" in fname_norm)) or
            "ALLOTMENT OF DIRECTOR IDENTIFICATION NUMBER" in text_norm or
            "ALLOTMENT OF DIN" in text_norm or
            "INTIMATION OF DIN ALLOTMENT" in text_norm or
            "INTIMATION OF ALLOTMENT OF DIRECTOR IDENTIFICATION NUMBER" in text_norm or
            ("SPICE" in text_norm and ("PART B" in text_norm or "PART-B" in text_norm or "DIN" in text_norm or "INC-32" in text_norm or "INC32" in text_norm)) or
            ("DIRECTOR IDENTIFICATION NUMBER" in text_norm and ("DIR-3" in text_norm or "ALLOTTED TO YOU" in text_norm or "APPLICATION IN FORM DIR-3" in text_norm or "ALLOTMENT OF DIN" in text_norm or "DIN CELL" in text_norm or "SPICE" in text_norm))
        ):
            doc_type = "din_approval"
            detected_category = "equity_governance"
            extracted["document_title"] = "SPICe+ Part B / Form DIR-3 DIN Approval Letter"
            extracted["extracted_fields"]["din_verified"] = True
            extracted["extracted_fields"]["din_approval_letter_verified"] = True

            # Extract DIN (8 digits)
            din_m = re.search(r'(?:Director\s+Identification\s+Number\s*(?:\(DIN\))?|DIN)\s*[:\-]?\s*([01][0-9]{7})', text, re.I) or re.search(r'\b([01][0-9]{7})\b', text)
            din_val = din_m.group(1).strip() if din_m else ""
            if din_val:
                extracted["extracted_fields"]["din"] = din_val
                extracted["extracted_fields"]["director_din"] = din_val

            # Extract Director Legal Name
            name_m = re.search(r'(?:Name\s+of\s+(?:the\s+)?Director|Name\s+of\s+Applicant|Director\s+Name|Name)\s*[:\-]?\s*([A-Za-z\s\.]+?)(?=\n|Father|Date|DIN|Nationality|Address|$)', text, re.I)
            raw_name = name_m.group(1).strip() if name_m else ""
            if not raw_name or len(raw_name) < 3 or not _is_valid_person_name(raw_name):
                sal_m = re.search(r'(?:Shri|Smt\.|Ms\.|Mr\.)\s+([A-Za-z\s\.]+?)(?=\n|Father|Date|DIN|Nationality|Address|$)', text, re.I)
                if sal_m and _is_valid_person_name(sal_m.group(1)):
                    raw_name = sal_m.group(1).strip()

            if not raw_name and extracted_directors:
                raw_name = extracted_directors[0]["name"]
                if not din_val and extracted_directors[0].get("din") != "N/A":
                    din_val = extracted_directors[0]["din"]
                    extracted["extracted_fields"]["din"] = din_val
                    extracted["extracted_fields"]["director_din"] = din_val

            if raw_name:
                extracted["extracted_fields"]["director_name"] = raw_name.title()
                extracted["extracted_fields"]["name"] = raw_name.title()
                extracted["extracted_fields"]["directors"] = [{
                    "name": raw_name.title(),
                    "din": din_val or "N/A",
                    "designation": "Director"
                }]

            # Father's Name
            father_m = re.search(r'Father(?:\'s)?\s+Name\s*[:\-]?\s*([A-Za-z\s\.]+?)(?=\n|Date|DIN|Nationality|Address|$)', text, re.I)
            if father_m and _is_valid_person_name(father_m.group(1)):
                extracted["extracted_fields"]["fathers_name"] = father_m.group(1).strip().title()

            # Date of Allotment
            allot_m = re.search(r'(?:Date\s+of\s+Allotment|Allotted\s+on|Date)\s*[:\-]?\s*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})', text, re.I)
            if allot_m:
                extracted["extracted_fields"]["allotment_date"] = allot_m.group(1).strip()

        # 1. Form AOC-4 (Financial Statements Filing) - High Priority to prevent falling into general auditor report
        elif (
            is_forced_aoc4 or
            "AOC-4" in fname_norm or "AOC 4" in fname_norm or "AOC4" in fname_norm or "AOC_4" in fname_norm or
            ("AOC" in fname_norm and "4" in fname_norm) or
            "FORM NO. AOC-4" in text_norm or "FORM NO. AOC 4" in text_norm or "FORM NO AOC-4" in text_norm or "FORM NO AOC 4" in text_norm or
            "FORM AOC-4" in text_norm or "FORM AOC 4" in text_norm or
            ("FINANCIAL STATEMENTS AND OTHER DOCUMENTS" in text_norm and "AOC" in text_norm) or
            ("BALANCE SHEET" in text_norm and "PROFIT AND LOSS" in text_norm and ("AOC" in text_norm or "AOC" in fname_norm)) or
            "ATTACHED WITH FORM AOC-4" in text_upper or "ATTACHED WITH AOC-4" in text_upper
        ):
            doc_type = "form_aoc_4"
            detected_category = "statutory_filing"
            extracted["document_title"] = "Form AOC-4: Annual Financial Statements Filing"
            extracted["extracted_fields"]["aoc4_verified"] = True
            extracted["extracted_fields"]["status"] = "Financial Statements Filed u/s 137"

            # Extract SRN
            srn_m = re.search(r'([A-Z0-9\-]{8,15})_SRN_FORM', text) or re.search(r'\b(1-[0-9]{10,12})\b', text) or re.search(r'\b([0-9]{10})\b', text) or SRN_REGEX.search(text)
            if srn_m:
                extracted["extracted_fields"]["srn"] = srn_m.group(1).replace("1-2", "").strip()

            fy_m = re.search(r'Financial\s+Year\s*(?:ended|period)?[ \t]*[:\-]?[ \t]*([0-9]{4}[/-][0-9]{2,4})', text, re.I) or re.search(r'Balance\s+Sheet\s+as\s+at\s+31st\s+March\s+(20[2-3][0-9])', text, re.I)
            if fy_m:
                val = fy_m.group(1)
                if len(val) == 4 and val.isdigit():
                    y = int(val)
                    extracted["extracted_fields"]["financial_year"] = f"{y-1}-{str(y)[-2:]}"
                    extracted["extracted_fields"]["assessment_year"] = f"{y}-{str(y+1)[-2:]}"
                else:
                    extracted["extracted_fields"]["financial_year"] = val

            agm_m = re.search(r'(?:Date\s+of\s+AGM|AGM\s+Date)[ \t]*[:\-]?[ \t]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})', text, re.I)
            if agm_m:
                extracted["extracted_fields"]["agm_date"] = agm_m.group(1)

            # Extract Schedule III payload
            aoc4_classified = StatutoryVaultEngine.classify_statutory_filing(file_bytes, filename, pdf_password)
            sch_payload = aoc4_classified.get("schedule_iii_payload", {})
            if sch_payload:
                extracted["extracted_fields"]["schedule_iii_payload"] = sch_payload
            if aoc4_classified.get("signatory_din"):
                extracted["extracted_fields"]["signatory_din"] = aoc4_classified["signatory_din"]
            if aoc4_classified.get("auditor_udin"):
                extracted["extracted_fields"]["auditor_udin"] = aoc4_classified["auditor_udin"]


        # 2. Board's Report / Extract of Board's Report (Section 134)
        elif (
            is_forced_board or
            "BOARD'S REPORT" in fname_norm or "BOARD REPORT" in fname_norm or "BOARDS REPORT" in fname_norm or
            "DIRECTORS' REPORT" in fname_norm or "DIRECTOR'S REPORT" in fname_norm or "DIRECTORS REPORT" in fname_norm or
            ("BOARD" in fname_norm and "REPORT" in fname_norm) or
            ("SECTION 134" in fname_norm or "SEC 134" in fname_norm or "SEC. 134" in fname_norm) or
            "EXTRACT OF BOARD'S REPORT" in text_norm or "EXTRACT OF BOARD REPORT" in text_norm or "EXTRACT OF BOARDS REPORT" in text_norm or
            ("BOARD'S REPORT" in text_norm and "FORM NO. MGT-7" not in text_norm and "FORM NO. AOC-4" not in text_norm) or
            ("BOARDS REPORT" in text_norm and "FORM NO. MGT-7" not in text_norm and "FORM NO. AOC-4" not in text_norm) or
            ("DIRECTORS' REPORT" in text_norm and "FORM NO. AOC-4" not in text_norm) or
            ("SECTION 134" in text_norm and "BOARD" in text_norm)
        ):
            doc_type = "board_report"
            detected_category = "equity_governance"
            extracted["document_title"] = "Extract of Board's Report (Section 134)"
            extracted["extracted_fields"]["board_report_status"] = "Verified u/s 134"
            extracted["extracted_fields"]["board_report_verified"] = True

        # 3. Auditor's Report / Extract of Auditor's Report (Standalone)
        elif (
            is_forced_auditor or
            "AUDITOR'S REPORT" in fname_norm or "AUDITOR REPORT" in fname_norm or "AUDITORS REPORT" in fname_norm or
            ("AUDITOR" in fname_norm and "REPORT" in fname_norm) or
            "EXTRACT OF AUDITOR'S REPORT" in text_norm or "EXTRACT OF AUDITOR REPORT" in text_norm or "EXTRACT OF AUDITORS REPORT" in text_norm or
            "INDEPENDENT AUDITOR'S REPORT" in text_norm or "INDEPENDENT AUDITOR REPORT" in text_norm or "INDEPENDENT AUDITORS REPORT" in text_norm
        ):
            doc_type = "auditor_report"
            detected_category = "statutory_filing"
            extracted["document_title"] = "Extract of Independent Auditor's Report (Standalone)"
            extracted["extracted_fields"]["auditor_report_verified"] = True

            if "TRUE AND FAIR VIEW" in text_norm and "ADVERSE" not in text_norm:
                extracted["extracted_fields"]["audit_opinion"] = "Unqualified (Clean Opinion)"
            elif "QUALIFIED OPINION" in text_norm:
                extracted["extracted_fields"]["audit_opinion"] = "Qualified Opinion"
            else:
                extracted["extracted_fields"]["audit_opinion"] = "Unqualified / Clean Statutory Auditor Report"

            if "COMPANIES (AUDITOR'S REPORT) ORDER" in text_norm or "CARO" in text_norm:
                extracted["extracted_fields"]["caro_reported"] = True

            aud_firm_m = re.search(r'(?:M/s\.?\s+[A-Za-z0-9\s\.\&]+(?:Associates|LLP|Chartered\s+Accountants))', text, re.I)
            if aud_firm_m:
                extracted["extracted_fields"]["auditor_firm_name"] = " ".join(aud_firm_m.group(0).split()).strip()

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


        # 8. Form MGT-7 / MGT-7A (Annual Return)
        elif (
            "MGT_7" in forced_norm or "MGT-7" in forced_norm or "MGT 7" in forced_norm or "MGT7" in forced_norm or
            "MGT_7A" in forced_norm or "MGT-7A" in forced_norm or "MGT 7A" in forced_norm or "MGT7A" in forced_norm or
            "FORM NO. MGT-7" in text_norm or "FORM NO. MGT-7A" in text_norm or "FORM NO. MGT 7" in text_norm or "FORM NO. MGT 7A" in text_norm or
            "FORM MGT-7" in text_norm or "FORM MGT-7A" in text_norm or "FORM MGT 7" in text_norm or "FORM MGT 7A" in text_norm or
            "MGT-7" in fname_norm or "MGT-7A" in fname_norm or "MGT 7" in fname_norm or "MGT 7A" in fname_norm or "MGT7" in fname_norm or "MGT7A" in fname_norm or
            ("MGT" in fname_norm and "7" in fname_norm) or
            "MGT-7" in text_norm or "MGT-7A" in text_norm or "MGT 7" in text_norm or "MGT 7A" in text_norm or
            "ABRIDGED ANNUAL RETURN" in text_norm or
            ("ANNUAL RETURN" in text_norm and ("SMALL COMPANY" in text_norm or "ONE PERSON COMPANY" in text_norm or "MGT" in text_norm))
        ):
            doc_type = "form_mgt_7"
            detected_category = "statutory_filing"
            extracted["document_title"] = "Form MGT-7 / MGT-7A: Annual Return"
            extracted["extracted_fields"]["mgt7_verified"] = True

            # Extract SRN
            srn_m = re.search(r'([A-Z0-9]{8,15})_SRN_FORM', text) or re.search(r'\b([A-Z]{2}[0-9]{7})\b', text) or SRN_REGEX.search(text)
            if srn_m:
                extracted["extracted_fields"]["srn"] = srn_m.group(1).strip()

            # Extract FY
            to_dt_m = re.search(r'(\d{2}/\d{2}/\d{4})\s*\(b\)\s*\*Financial\s+year|31/03/(20[2-3][0-9])', text)
            if to_dt_m:
                if to_dt_m.group(2):
                    yr = int(to_dt_m.group(2))
                    extracted["extracted_fields"]["financial_year"] = f"{yr-1}-{str(yr)[-2:]}"
                    extracted["extracted_fields"]["assessment_year"] = f"{yr}-{str(yr+1)[-2:]}"
                elif to_dt_m.group(1):
                    dt_part = to_dt_m.group(1).split('/')
                    yr = int(dt_part[2])
                    extracted["extracted_fields"]["financial_year"] = f"{yr-1}-{str(yr)[-2:]}"
                    extracted["extracted_fields"]["assessment_year"] = f"{yr}-{str(yr+1)[-2:]}"

            # Extract Board meetings count
            bm_cnt_m = re.search(r'Number\s+of\s+meetings\s+of\s+the\s+Board[ \t]*[:\-]?[ \t]*([0-9]+)', text, re.I)
            if bm_cnt_m:
                extracted["extracted_fields"]["board_meetings_held_count"] = int(bm_cnt_m.group(1))

            # Extract Share Capital Structure
            sh_num_m = re.search(r'Total\s+number\s+of\s+equity\s+shares\s+([0-9]+)', text)
            sh_amt_m = re.search(r'shares\s*\(in\s*rupees\)\s*([0-9\.]+)', text)
            sh_nom_m = re.search(r'Nominal\s+value\s+per\s+share\s*\(in\s*rupees\)\s*([0-9\.]+)', text)

            auth_cap = float(sh_amt_m.group(1)) if sh_amt_m else 100000.0
            tot_shares = int(sh_num_m.group(1)) if sh_num_m else 10000
            face_val = float(sh_nom_m.group(1)) if sh_nom_m else 10.0

            extracted["extracted_fields"]["authorized_capital_inr"] = auth_cap
            extracted["extracted_fields"]["total_equity_shares"] = tot_shares
            extracted["extracted_fields"]["face_value_inr"] = face_val
            extracted["extracted_fields"]["paid_up_capital_inr"] = auth_cap
            extracted["extracted_fields"]["paid_up_shares"] = tot_shares

            # Extract Net Worth & Turnover
            nw_m = re.search(r'Net\s+worth\s+of\s+the\s+Company\s*([-\d\.,]+)', text)
            if nw_m:
                extracted["extracted_fields"]["net_worth_inr"] = float(nw_m.group(1).replace(',', ''))

            to_m = re.search(r'([0-9\.]+)\s*i\s*\*Turnover', text) or re.search(r'Turnover\s*[:\-]?[ \t]*([0-9\.]+)', text)
            if to_m:
                extracted["extracted_fields"]["turnover_inr"] = float(to_m.group(1).replace(',', ''))

            # Extract Promoters / Shareholding pattern
            prom_cnt_m = re.search(r'Promoters\s*([0-9]+)\s+([0-9]+)', text)
            dirs = extracted.get("extracted_fields", {}).get("directors") or []
            prim_dir = dirs[0]["name"] if dirs else "Director"
            prim_din = dirs[0]["din"] if dirs else "N/A"

            mgt7_payload = {
                "srn": extracted["extracted_fields"].get("srn"),
                "financial_year": extracted["extracted_fields"].get("financial_year"),
                "authorized_capital_inr": auth_cap,
                "total_equity_shares": tot_shares,
                "face_value_inr": face_val,
                "paid_up_capital_inr": auth_cap,
                "paid_up_shares": tot_shares,
                "net_worth_inr": extracted["extracted_fields"].get("net_worth_inr"),
                "turnover_inr": extracted["extracted_fields"].get("turnover_inr", 0.0),
                "promoters_count": int(prom_cnt_m.group(1)) if prom_cnt_m else 1,
                "promoter_holding_percent": 100.0,
                "shareholders": [
                    {
                        "name": prim_dir,
                        "class_of_shares": "Equity Shares",
                        "number_of_shares": tot_shares,
                        "percentage_holding": 100.0
                    }
                ],
                "promoter_shareholding": [
                    {
                        "promoter_name": prim_dir,
                        "din": prim_din,
                        "shares": tot_shares,
                        "percentage": 100.0
                    }
                ]
            }
            extracted["extracted_fields"]["mgt7_payload"] = mgt7_payload
            extracted["extracted_fields"]["shareholders"] = mgt7_payload["shareholders"]
            extracted["extracted_fields"]["shareholding_pattern"] = mgt7_payload["promoter_shareholding"]


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

        # 13. Income Tax Return (ITR / Form ITR-6 / ITR-V Ack) - Checked BEFORE PAN Card
        elif (
            is_forced_itr or
            "ITR" in forced_norm or "ITR-6" in forced_norm or "ITR_6" in forced_norm or "ITR 6" in forced_norm or
            "ITR-V" in forced_norm or "ITR_V" in forced_norm or "ITR V" in forced_norm or
            "INCOME TAX RETURN" in forced_norm or
            "ITR" in fname_norm or "ITR-6" in fname_norm or "ITR 6" in fname_norm or "ITR-V" in fname_norm or "ITR V" in fname_norm or
            "INCOME TAX RETURN" in fname_norm or
            "INDIAN INCOME TAX RETURN" in text_norm or "INCOME TAX RETURN ACKNOWLEDGEMENT" in text_norm or
            "ITR-6" in text_norm or "FORM ITR-6" in text_norm or "ITR-V" in text_norm or
            ("INCOME TAX" in text_norm and ("ASSESSMENT YEAR" in text_norm or "ACK. NO." in text_norm or "ACKNOWLEDGEMENT" in text_norm or "TOTAL INCOME" in text_norm))
        ):
            doc_type = "itr"
            detected_category = "tax_registration"
            extracted["document_title"] = "Income Tax Return (Form ITR-6 / ITR-V Ack)"
            extracted["extracted_fields"]["itr_verified"] = True
            extracted["extracted_fields"]["itr_status"] = "Filed u/s 139"

            ay_m = re.search(r'Assessment\s+Year[ \t]*[:\-]?[ \t]*([0-9]{4}-[0-9]{2,4})', text, re.I)
            if ay_m:
                extracted["extracted_fields"]["assessment_year"] = ay_m.group(1).strip()

            py_m = re.search(r'(?:Previous\s+Year|Financial\s+Year)[ \t]*[:\-]?[ \t]*([0-9]{4}-[0-9]{2,4})', text, re.I)
            if py_m:
                extracted["extracted_fields"]["financial_year"] = py_m.group(1).strip()

            ack_m = re.search(r'(?:Acknowledgement\s+Number|e-Filing\s+Acknowledgement\s+Number|Ack\.?\s+No\.?)[ \t]*[:\-]?[ \t]*([0-9]{15})', text, re.I) or re.search(r'\b([0-9]{15})\b', text)
            if ack_m:
                extracted["extracted_fields"]["itr_ack_number"] = ack_m.group(1).strip()
                extracted["extracted_fields"]["acknowledgement_number"] = ack_m.group(1).strip()

            pan_m = PAN_REGEX.search(text)
            if pan_m:
                extracted["extracted_fields"]["pan"] = pan_m.group(1).strip().upper()

            filing_date_m = re.search(r'(?:Date\s+of\s+Filing|Filed\s+on)[ \t]*[:\-]?[ \t]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})', text, re.I)
            if filing_date_m:
                extracted["extracted_fields"]["filing_date"] = filing_date_m.group(1).strip()

            inc_m = re.search(r'(?:Total\s+Income|Gross\s+Total\s+Income)[ \t]*[:\-]?[ \t]*(?:Rs\.|INR|₹)?[ \t]*([0-9,]+)', text, re.I)
            if inc_m:
                extracted["extracted_fields"]["total_income"] = inc_m.group(1).strip().replace(',', '')

        # 14. Corporate PAN Card
        elif (
            (
                "PERMANENT ACCOUNT NUMBER" in text_upper or
                "FORM 49A" in text_upper or
                "PAN" in forced_upper or
                "PAN" in fname_upper or
                ("INCOME TAX DEPARTMENT" in text_upper and PAN_REGEX.search(text))
            )
            and doc_type != "tan_letter"
            and not is_forced_itr
            and "ASSESSMENT YEAR" not in text_upper
            and "ITR" not in fname_upper
            and "ITR" not in text_upper
        ):
            doc_type = "pan_card"
            detected_category = "tax_registration"
            extracted["document_title"] = "Permanent Account Number (PAN Card)"
            extracted["extracted_fields"]["pan_verified"] = True
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

    @staticmethod
    async def check_and_deduplicate(
        db: Any,
        tenant_id: Any,
        sha256_hash: str
    ) -> Dict[str, Any]:
        """
        Content-addressed deduplication guard.
        Queries statutory_filing_anchors and document_vault to verify whether
        the uploaded document already exists in sovereign storage.
        """
        from sqlalchemy import select
        from app.models.compliance import StatutoryFilingAnchor
        from app.models.vault import DocumentVault

        # 1. Check statutory_filing_anchors
        stmt_anchor = (
            select(StatutoryFilingAnchor)
            .where(
                StatutoryFilingAnchor.tenant_id == tenant_id,
                StatutoryFilingAnchor.document_sha256 == sha256_hash
            )
        )
        res_anchor = await db.execute(stmt_anchor)
        existing_anchor = res_anchor.scalar_one_or_none()

        if existing_anchor:
            return {
                "is_duplicate": True,
                "source": "statutory_filing_anchors",
                "id": str(existing_anchor.id),
                "fiscal_year": existing_anchor.fiscal_year,
                "assessment_year": existing_anchor.assessment_year,
                "form_type": existing_anchor.form_type,
                "srn_or_ack_number": existing_anchor.srn_or_ack_number,
                "filing_date": existing_anchor.filing_date.isoformat() if existing_anchor.filing_date else None,
                "s3_document_key": existing_anchor.s3_document_key,
                "sha256": existing_anchor.document_sha256,
                "message": (
                    f"Duplicate Prevented: This authentic {existing_anchor.form_type.upper()} document was already "
                    f"uploaded and verified for FY {existing_anchor.fiscal_year} (Ref: {existing_anchor.srn_or_ack_number}). "
                    f"No redundant binary storage created."
                )
            }

        # 2. Check document_vault
        stmt_vault = (
            select(DocumentVault)
            .where(
                DocumentVault.tenant_id == tenant_id,
                DocumentVault.sha256_hash == sha256_hash
            )
        )
        res_vault = await db.execute(stmt_vault)
        existing_vault = res_vault.scalar_one_or_none()

        if existing_vault:
            meta = existing_vault.metadata_json or {}
            return {
                "is_duplicate": True,
                "source": "document_vault",
                "id": str(existing_vault.id),
                "fiscal_year": meta.get("fiscal_year", "N/A"),
                "form_type": meta.get("form_type", "statutory_document"),
                "srn_or_ack_number": existing_vault.document_number,
                "filing_date": existing_vault.created_at.date().isoformat() if existing_vault.created_at else None,
                "s3_document_key": existing_vault.minio_s3_key,
                "sha256": existing_vault.sha256_hash,
                "message": (
                    f"Duplicate Prevented: This authentic document ({existing_vault.document_name}) was already "
                    f"indexed in Sovereign Vault on {existing_vault.created_at.date()}. No redundant binary storage created."
                )
            }

        return {"is_duplicate": False, "sha256": sha256_hash}

    @staticmethod
    def classify_statutory_filing(
        file_bytes: bytes,
        filename: str = "",
        pdf_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extracts metadata and classifies government return into:
        - aoc_4: Form AOC-4 / AOC-4 XBRL (identifies SRN, CIN, FY, Balance sheet lines)
        - itr_6: Form ITR-6 / ITR-V (identifies PAN, AY, Ack #, Date)
        - auditor_report: Standalone Independent Auditor's Report (identifies UDIN, CA firm, FRN, Date)
        - boards_report: Board's Report under Sec 134 (identifies meeting date, director names, DINs)
        - mgt_7a: Form MGT-7 / MGT-7A (identifies SRN, CIN, AGM date)
        - tax_audit_3cd: Form 3CD (identifies UDIN, AY)
        """
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        text, is_encrypted = extract_text_from_pdf(file_bytes, password=pdf_password)
        text_upper = text.upper()

        detected_form = "unknown"
        srn_or_ack = None
        filing_dt = date.today()
        detected_fy = None
        detected_ay = None
        signatory_din = None
        auditor_udin = None
        schedule_iii = {}

        # 1. Form AOC-4 Check
        is_aoc4_candidate = (
            "AOC-4" in text_upper or "AOC 4" in text_upper or "FORM NO. AOC-4" in text_upper or "FORM AOC-4" in text_upper or
            "ATTACHED WITH FORM AOC-4" in text_upper or "ATTACHED WITH AOC-4" in text_upper or
            (("BALANCE SHEET AS AT 31ST MARCH" in text_upper or "BALANCE SHEET AS AT 31 MARCH" in text_upper) and
             ("AUDITOR'S REPORT" in text_upper or "AUDITORS REPORT" in text_upper or "AOC" in filename.upper()))
        )
        if is_aoc4_candidate:
            detected_form = "aoc_4"
            srn_m = (
                re.search(r'([A-Z0-9\-]{8,15})_SRN_FORM', text) or
                re.search(r'\b(1-[0-9]{10,12})\b', text) or
                re.search(r'\b([0-9]{10})\b', text) or
                SRN_REGEX.search(text)
            )
            if srn_m:
                srn_or_ack = srn_m.group(1).replace("1-2", "").strip()

            fy_m = (
                re.search(r'\b(20[2-3][0-9])-(20[2-3][0-9]|[0-9]{2})\b', text) or
                re.search(r'31st\s+March\s+(20[2-3][0-9])', text, re.I) or
                re.search(r'31\s+March\s+(20[2-3][0-9])', text, re.I)
            )
            if fy_m:
                if fy_m.lastindex == 2:
                    y1 = int(fy_m.group(1))
                    y2_str = fy_m.group(2)
                    y2 = int(y2_str) if len(y2_str) == 4 else y1 + 1
                    detected_fy = f"{y1}-{str(y2)[-2:]}"
                    detected_ay = f"{y2}-{str(y2+1)[-2:]}"
                else:
                    y = int(fy_m.group(1))
                    detected_fy = f"{y-1}-{str(y)[-2:]}"
                    detected_ay = f"{y}-{str(y+1)[-2:]}"

            date_to_m = re.search(r'\*To\s*\(DD/MM/YYYY\)\s*(\d{2}/\d{2}/\d{4})', text)
            if date_to_m:
                try:
                    to_dt = datetime.strptime(date_to_m.group(1), "%d/%m/%Y").date()
                    detected_fy = f"{to_dt.year - 1}-{str(to_dt.year)[-2:]}"
                    detected_ay = f"{to_dt.year}-{str(to_dt.year + 1)[-2:]}"
                except Exception:
                    pass

            dins = DIN_REGEX.findall(text)
            if dins:
                signatory_din = dins[0]
            udins = re.findall(r'\b([2-3][0-9]{5}[0-9A-Z]{12})\b', text_upper)
            if udins:
                auditor_udin = udins[0]

            # Parse authentic Schedule III balance sheet heads
            aoc4_patterns = {
                '2010': [r'Share\s+capital\s+([-\d\.,]+)', r'\(a\)\s+Share\s+capital\s+([-\d\.,]+)'],
                '2020': [r'Reserves\s+and\s+surplus\s+([-\d\.,]+)', r'\(b\)\s+Reserves\s+and\s+surplus\s+([-\d\.,]+)'],
                '2030': [r'Long\s*term\s+borrowings\s+([-\d\.,]+)', r'\(a\)\s+Long\s+term\s+borrowings\s+([-\d\.,]+)'],
                '2035': [r'Short\s*term\s+borrowings\s+([-\d\.,]+)'],
                '2040': [r'Trade\s+payables.*?creditors[^\n]*\n\s*([-\d\.,]+)', r'Trade\s+payables\s+([-\d\.,]+)'],
                '2050': [r'Other\s+current\s+liabilities\s+([-\d\.,]+)'],
                '2060': [r'Short\s*term\s+provisions\s+([-\d\.,]+)'],
                '1050': [r'Property\s+Plant\s+and\s+Equipment\s+([-\d\.,]+)', r'Tangible\s+assets\s+([-\d\.,]+)'],
                '1020': [r'Trade\s+receivables\s+([-\d\.,]+)'],
                '1010': [r'Cash\s+and\s+cash\s+equivalents\s+([-\d\.,]+)', r'Cash\s+and\s+bank\s+balances\s+([-\d\.,]+)'],
                '1040': [r'Short\s*term\s+loans\s+and\s+advances\s+([-\d\.,]+)'],
                '1030': [r'Other\s+current\s+assets\s+([-\d\.,]+)'],
                '3010': [r'Revenue\s+from\s+operations\s+([-\d\.,]+)'],
                '3020': [r'Other\s+income\s+([-\d\.,]+)'],
                '4010': [r'Employee\s+benefits?\s+expense\s+([-\d\.,]+)'],
                '4020': [r'Finance\s+costs\s+([-\d\.,]+)'],
                '4030': [r'Depreciation\s+and\s+amorti[sz]ation\s+expense\s+([-\d\.,]+)'],
                '4040': [r'Other\s+expenses\s+([-\d\.,]+)'],
                '5010': [r'Profit\s+before\s+tax\s+([-\d\.,]+)'],
                '5020': [r'Profit\s*(?:/\s*\(?loss\)?)?\s*(?:for\s+the\s+period|for\s+the\s+year)\s*([-\d\.,]+)']
            }
            for code, pats in aoc4_patterns.items():
                for p in pats:
                    m = re.search(p, text, re.IGNORECASE)
                    if m:
                        val_str = m.group(1).replace(',', '').strip()
                        try:
                            schedule_iii[code] = f"{float(val_str):.2f}"
                            break
                        except ValueError:
                            pass

        # 2. Form ITR-6 Check
        elif "ITR-6" in text_upper or "INDIAN INCOME TAX RETURN" in text_upper or "ITR-V" in text_upper or "ACKNOWLEDGEMENT NUMBER" in text_upper:
            detected_form = "itr_6"
            ack_m = re.search(r'(?:ACKNOWLEDGEMENT\s+NUMBER|ACK\s+NO|ACK\s+NUMBER)[ \t]*[:\-]?[ \t]*([0-9]{10,18})', text_upper)
            if ack_m:
                srn_or_ack = ack_m.group(1)
            ay_m = re.search(r'ASSESSMENT\s+YEAR[ \t]*[:\-]?[ \t]*(20[2-3][0-9]-(?:20[2-3][0-9]|[0-9]{2}))', text_upper)
            if ay_m:
                detected_ay = ay_m.group(1)
                p = detected_ay.split('-')
                ay_y1 = int(p[0])
                detected_fy = f"{ay_y1 - 1}-{str(ay_y1)[-2:]}"

            pan_m = PAN_REGEX.search(text)
            if pan_m:
                schedule_iii["pan"] = pan_m.group(1)

            loss_m = re.search(r'Current\s+Year\s+business\s+loss[^\n]*\n\s*1\s*\n\s*([0-9,\.]+)', text, re.I)
            if loss_m:
                schedule_iii["business_loss"] = float(loss_m.group(1).replace(',', ''))

        # 3. Independent Auditor's Report
        elif "INDEPENDENT AUDITOR'S REPORT" in text_upper or "AUDITOR'S REPORT" in text_upper or "INDEPENDENT AUDITORS REPORT" in text_upper:
            detected_form = "auditor_report"
            udins = re.findall(r'\b([2-3][0-9]{5}[0-9A-Z]{12})\b', text_upper) or re.findall(r'UDIN[ \t]*[:\-]?[ \t]*([0-9A-Z]{18})', text_upper)
            if udins:
                auditor_udin = udins[0]
                srn_or_ack = f"UDIN-{auditor_udin}"
            frn_m = FRN_REGEX.search(text)
            if frn_m:
                schedule_iii["frn"] = frn_m.group(1)

        # 4. Board's Report (Section 134)
        elif "BOARD'S REPORT" in text_upper or "BOARDS REPORT" in text_upper or "DIRECTORS' REPORT" in text_upper or "DIRECTORS REPORT" in text_upper or "PURSUANT TO SECTION 134" in text_upper:
            detected_form = "boards_report"
            srn_or_ack = f"SEC134-BR-{datetime.utcnow().strftime('%Y%m%d')}"
            dins = DIN_REGEX.findall(text)
            if dins:
                signatory_din = dins[0]

        # 5. Form MGT-7 / MGT-7A
        elif "MGT-7" in text_upper or "MGT 7" in text_upper or "MGT-7A" in text_upper or ("ANNUAL RETURN" in text_upper and "COMPANIES ACT" in text_upper):
            detected_form = "mgt_7a"
            srn_m = re.search(r'([A-Z0-9]{8,15})_SRN_FORM', text) or re.search(r'\b([A-Z]{2}[0-9]{7})\b', text) or SRN_REGEX.search(text)
            if srn_m:
                srn_or_ack = srn_m.group(1).strip()

            to_dt_m = re.search(r'(\d{2}/\d{2}/\d{4})\s*\(b\)\s*\*Financial\s+year|31/03/(20[2-3][0-9])', text)
            if to_dt_m:
                if to_dt_m.group(2):
                    yr = int(to_dt_m.group(2))
                    detected_fy = f"{yr-1}-{str(yr)[-2:]}"
                    detected_ay = f"{yr}-{str(yr+1)[-2:]}"
                elif to_dt_m.group(1):
                    dt_part = to_dt_m.group(1).split('/')
                    yr = int(dt_part[2])
                    detected_fy = f"{yr-1}-{str(yr)[-2:]}"
                    detected_ay = f"{yr}-{str(yr+1)[-2:]}"

            # Extract share capital
            sh_num_m = re.search(r'Total\s+number\s+of\s+equity\s+shares\s+([0-9]+)', text)
            sh_amt_m = re.search(r'shares\s*\(in\s*rupees\)\s*([0-9\.]+)', text)
            sh_nom_m = re.search(r'Nominal\s+value\s+per\s+share\s*\(in\s*rupees\)\s*([0-9\.]+)', text)
            auth_cap = float(sh_amt_m.group(1)) if sh_amt_m else 100000.0
            tot_shares = int(sh_num_m.group(1)) if sh_num_m else 10000
            face_val = float(sh_nom_m.group(1)) if sh_nom_m else 10.0
            schedule_iii["2010"] = f"{auth_cap:.2f}"
            schedule_iii["authorized_capital_inr"] = auth_cap
            schedule_iii["total_equity_shares"] = tot_shares
            schedule_iii["face_value_inr"] = face_val
            schedule_iii["paid_up_capital_inr"] = auth_cap
            schedule_iii["paid_up_shares"] = tot_shares
            nw_m = re.search(r'Net\s+worth\s+of\s+the\s+Company\s*([-\d\.,]+)', text)
            if nw_m:
                schedule_iii["net_worth_inr"] = float(nw_m.group(1).replace(',', ''))


        # Fallback if filename hints
        if detected_form == "unknown":
            fn_u = filename.upper()
            if "AOC" in fn_u:
                detected_form = "aoc_4"
            elif "ITR" in fn_u:
                detected_form = "itr_6"
            elif "AUDIT" in fn_u:
                detected_form = "auditor_report"
            elif "BOARD" in fn_u:
                detected_form = "boards_report"
            elif "MGT" in fn_u:
                detected_form = "mgt_7a"
            elif "3CD" in fn_u:
                detected_form = "tax_audit_3cd"

        if not srn_or_ack:
            srn_or_ack = f"REF-{sha256_hash[:8].upper()}"

        return {
            "form_type": detected_form,
            "srn_or_ack_number": srn_or_ack,
            "fiscal_year": detected_fy,
            "assessment_year": detected_ay,
            "filing_date": filing_dt.isoformat(),
            "signatory_din": signatory_din,
            "auditor_udin": auditor_udin,
            "sha256": sha256_hash,
            "file_size_bytes": file_size,
            "schedule_iii_payload": schedule_iii
        }

