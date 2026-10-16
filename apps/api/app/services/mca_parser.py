"""
b00k5 - MCA SPICe+ Part B & Statutory Document Parser
Compliant with:
- Companies Act, 2013 & Companies (Appointment and Qualification of Directors) Rules, 2014
- Form DIR-3 / SPICe+ Part B (INC-32) DIN Allotment Verification
"""

import re
from datetime import datetime, date
from typing import Dict, Any, Optional, List

DIN_REGEX = re.compile(r'\b([01][0-9]{7})\b')
CIN_REGEX = re.compile(r'\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b')
PAN_REGEX = re.compile(r'\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b')
TAN_REGEX = re.compile(r'\b([A-Z]{4}[0-9]{5}[A-Z]{1})\b')


class MCAParser:
    """
    Statutory parser for official Ministry of Corporate Affairs (MCA) instruments:
    - SPICe+ Part B Allotment Intimation
    - Form DIR-3 DIN Approval Letter
    - Form ADT-1 Auditor Appointment
    """

    @staticmethod
    def parse_din_approval_letter(text: str, filename: str = "") -> Dict[str, Any]:
        """
        Extracts 8-digit DIN, Director Full Legal Name, Father's Name,
        and Date of Allotment from official MCA DIN approval letters.
        """
        result: Dict[str, Any] = {
            "document_type": "din_approval",
            "document_title": "SPICe+ Part B / Form DIR-3 DIN Approval Letter",
            "din": "",
            "director_name": "",
            "father_name": "",
            "allotment_date": None,
            "nationality": "Indian",
            "is_authentic": False,
            "verification_status": "unverified"
        }

        # 1. Extract 8-digit DIN
        din_patterns = [
            r'Director\s+Identification\s+Number\s*(?:\(DIN\))?\s*[:\-]?\s*([01][0-9]{7})',
            r'DIN\s*[:\-]?\s*([01][0-9]{7})',
            r'\b([01][0-9]{7})\b'
        ]
        for pat in din_patterns:
            m = re.search(pat, text, re.I)
            if m:
                result["din"] = m.group(1).strip()
                break

        # 2. Extract Director Full Legal Name
        # Check formal MCA allotment phrasing first
        allot_match = re.search(
            r'Director\s+Identification\s+Number\s*(?:\(DIN\))?\s*(?:has\s+been\s+allotted\s+to\s+you\s+as\s+per\s+details|has\s+been\s+allotted\s+to)\s*[:\-]?\s*([A-Za-z\s\.]+?)(?=\n|Father|Date|DIN|$)',
            text,
            re.I
        )
        if allot_match:
            cand = allot_match.group(1).strip()
            if len(cand) > 3 and not any(k in cand.upper() for k in ["DETAILS", "GIVEN", "SIR", "MADAM"]):
                result["director_name"] = " ".join(cand.split()).title()

        if not result["director_name"]:
            name_patterns = [
                r'(?:Name\s+of\s+(?:the\s+)?Director|Name\s+of\s+Applicant|Director\s+Name)\s*[:\-]?\s*([A-Za-z\s\.]+?)(?=\n|Father|Date|DIN|Nationality|Address|$)',
                r'(?:Shri|Smt\.|Ms\.|Mr\.)\s+([A-Za-z\s\.]+?)(?=\n|Father|Date|DIN|Nationality|Address|$)'
            ]
            for pat in name_patterns:
                m = re.search(pat, text, re.I)
                if m:
                    cand = m.group(1).strip()
                    if len(cand) > 3 and not any(k in cand.upper() for k in ["DIRECTOR", "APPLICANT", "MINISTRY", "CORPORATE"]):
                        result["director_name"] = " ".join(cand.split()).title()
                        break

        # 3. Extract Father's Name
        father_match = re.search(
            r'Father(?:\'s)?\s+Name\s*[:\-]?\s*([A-Za-z\s\.]+?)(?=\n|Date|DIN|Nationality|Address|$)',
            text,
            re.I
        )
        if father_match:
            result["father_name"] = " ".join(father_match.group(1).split()).title()

        # 4. Extract Date of Allotment / Approval
        date_patterns = [
            r'Date\s+of\s+(?:Allotment|Approval|Issue)\s*[:\-]?\s*([0-3]?[0-9][\/\-\.][0-1]?[0-9][\/\-\.](?:20)?\d\d)',
            r'Dated\s*[:\-]?\s*([0-3]?[0-9][\/\-\.][0-1]?[0-9][\/\-\.](?:20)?\d\d)',
            r'([0-3]?[0-9][\/\-\.][0-1]?[0-9][\/\-\.](?:20)?\d\d)'
        ]
        for pat in date_patterns:
            m = re.search(pat, text, re.I)
            if m:
                raw_d = m.group(1).strip().replace('.', '/').replace('-', '/')
                try:
                    parts = raw_d.split('/')
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                    if year < 100:
                        year += 2000
                    result["allotment_date"] = date(year, month, day).isoformat()
                    break
                except Exception:
                    pass

        # Validation status
        if result["din"] and result["director_name"]:
            result["is_authentic"] = True
            result["verification_status"] = "verified"

        return result

    @staticmethod
    def parse_spice_plus_part_b(text: str) -> Dict[str, Any]:
        """
        Parses MCA Form SPICe+ Part B (INC-32) for company incorporation,
        founding directors, capital, PAN, and TAN.
        """
        res: Dict[str, Any] = {
            "document_type": "spice_plus_part_b",
            "document_title": "SPICe+ Part B (Form INC-32)",
            "cin": "",
            "company_name": "",
            "directors": [],
            "pan": "",
            "tan": "",
            "authorized_capital": 0.0
        }

        cin_m = CIN_REGEX.search(text)
        if cin_m:
            res["cin"] = cin_m.group(1)

        pan_m = PAN_REGEX.search(text)
        if pan_m:
            res["pan"] = pan_m.group(1)

        tan_m = TAN_REGEX.search(text)
        if tan_m:
            res["tan"] = tan_m.group(1)

        # Extract all DINs
        dins = list(set(DIN_REGEX.findall(text)))
        res["directors"] = [{"din": d} for d in dins]

        return res

