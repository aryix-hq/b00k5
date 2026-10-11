import re
from typing import Dict, Any

CIN_REGEX = re.compile(r'^([LU])([0-9]{5})([A-Z]{2})([0-9]{4})([A-Z]{3})([0-9]{6})$')

STATE_ALPHA_TO_NUM = {
    "KA": "29", "MH": "27", "DL": "07", "TN": "33", "TS": "36",
    "TG": "36", "GJ": "24", "UP": "09", "HR": "06", "WB": "19",
    "RJ": "08", "KL": "32", "AP": "37", "MP": "23", "PB": "03"
}

from app.services.gst_calculator import INDIAN_STATE_CODES

def parse_indian_cin(cin: str) -> Dict[str, Any]:
    """
    Parses a 21-digit Indian Corporate Identification Number (CIN)
    e.g. U72900KA2026PTC123456
    """
    cin_clean = cin.strip().upper()
    match = CIN_REGEX.match(cin_clean)
    if not match:
        raise ValueError("Invalid CIN format. Must be 21 characters (e.g., U72900KA2026PTC123456).")

    listing_status = "Unlisted" if match.group(1) == "U" else "Listed"
    industry_code = match.group(2)
    state_alpha = match.group(3)
    inc_year = int(match.group(4))
    company_type = match.group(5) # PTC = Private Limited, PLC = Public Limited, FTC = Foreign Company
    reg_number = match.group(6)

    numeric_state = STATE_ALPHA_TO_NUM.get(state_alpha, "29")
    state_name = INDIAN_STATE_CODES.get(numeric_state, "Unknown State")

    type_map = {
        "PTC": "Private Limited Company",
        "PLC": "Public Limited Company",
        "FTC": "Subsidiary of Foreign Company",
        "GOI": "Government of India Company",
        "SGC": "State Government Company"
    }

    return {
        "cin": cin_clean,
        "is_valid": True,
        "listing_status": listing_status,
        "industry_code": industry_code,
        "state_alpha": state_alpha,
        "numeric_state_code": numeric_state,
        "state_name": state_name,
        "incorporation_year": inc_year,
        "company_type": type_map.get(company_type, company_type),
        "registration_number": reg_number
    }
