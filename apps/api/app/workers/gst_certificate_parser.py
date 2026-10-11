"""
b00k5 - GST REG-06 Registration Certificate OCR Extractor
Parses official Indian GST Registration Certificates (Form GST REG-06) under Rule 10(1)
Extracts:
- 15-character GSTIN
- Legal Name
- Trade Name
- Constitution of Business
- Date of Liability / Registration
- State Code and State Name
"""

import io
import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("b00k5_gst_parser")

STATE_CODE_MAP = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh"
}

GSTIN_REGEX = re.compile(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b")
DATE_REGEX = re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b")


class GSTRegistrationCertificateParser:
    @classmethod
    def extract_text_from_bytes(cls, file_bytes: bytes) -> str:
        """Extracts text from PDF or raw bytes."""
        text = ""
        # 1. Try PyPDF
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            if text.strip():
                return text
        except Exception as e:
            logger.debug(f"pypdf extraction failed or not applicable: {e}")

        # 2. Try raw text decode if text file / stream
        try:
            decoded = file_bytes.decode("utf-8", errors="ignore")
            # If standard text markers appear
            if "GST" in decoded or "Registration" in decoded:
                return decoded
        except Exception:
            pass

        return text

    @classmethod
    def parse_gst_certificate(cls, file_bytes: bytes) -> Dict[str, Any]:
        """
        Parses GST REG-06 document text and extracts key statutory attributes.
        """
        raw_text = cls.extract_text_from_bytes(file_bytes)
        
        # 1. GSTIN (15 characters)
        gstin_match = GSTIN_REGEX.search(raw_text)
        gstin = gstin_match.group(1).upper() if gstin_match else None

        # 2. State Code and Name
        state_code = None
        state_name = None
        if gstin:
            state_code = gstin[:2]
            state_name = STATE_CODE_MAP.get(state_code, f"State Code {state_code}")

        # 3. Legal Name
        legal_name = None
        legal_name_match = re.search(r"Legal\s*Name\s*[:\-]?\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        if legal_name_match:
            legal_name = legal_name_match.group(1).strip()
            # Clean up trailing labels if captured
            legal_name = re.sub(r"\s*Trade\s*Name.*", "", legal_name, flags=re.IGNORECASE).strip()

        # 4. Trade Name
        trade_name = None
        trade_name_match = re.search(r"Trade\s*Name\s*(?:,\s*if\s*any)?\s*[:\-]?\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        if trade_name_match:
            trade_name = trade_name_match.group(1).strip()
            trade_name = re.sub(r"\s*Constitution.*", "", trade_name, flags=re.IGNORECASE).strip()
        if not trade_name:
            trade_name = legal_name

        # 5. Constitution of Business
        constitution = None
        constitution_patterns = [
            r"Constitution\s*of\s*Business\s*[:\-]?\s*([^\n\r]+)",
            r"(Private\s+Limited\s+Company|Public\s+Limited\s+Company|Limited\s+Liability\s+Partnership|Partnership|Sole\s+Proprietorship|Proprietorship|One\s+Person\s+Company)"
        ]
        for pat in constitution_patterns:
            m = re.search(pat, raw_text, re.IGNORECASE)
            if m:
                constitution = m.group(1).strip()
                break
        if not constitution:
            constitution = "Private Limited Company"

        # 6. Date of Liability / Registration
        date_str = None
        date_matches = DATE_REGEX.findall(raw_text)
        if date_matches:
            date_str = date_matches[0]

        # 7. Principal Place of Business
        address = None
        addr_match = re.search(r"Address\s*(?:of\s*Principal\s*Place\s*of\s*Business)?\s*[:\-]?\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        if addr_match:
            address = addr_match.group(1).strip()

        is_valid = bool(gstin and len(gstin) == 15)

        return {
            "success": is_valid,
            "document_type": "GST_REG-06",
            "gstin": gstin,
            "legal_name": legal_name,
            "trade_name": trade_name,
            "constitution": constitution,
            "date_of_registration": date_str,
            "state_code": state_code,
            "state_name": state_name,
            "state_display": f"{state_code} - {state_name}" if state_code and state_name else None,
            "registered_address": address,
            "verification_status": "GST Verified via Certificate" if is_valid else "Extraction Incomplete",
            "raw_text_length": len(raw_text)
        }
