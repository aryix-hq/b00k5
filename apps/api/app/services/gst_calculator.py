from decimal import Decimal
from typing import Dict, Any, Tuple, Optional
import re

COMMON_HSN_SAC = {
    # IT, Software & SaaS
    "998313": {"description": "Information technology consulting and support services", "default_rate": Decimal("18.00")},
    "998314": {"description": "Information technology design and development services", "default_rate": Decimal("18.00")},
    "998315": {"description": "Hosting and information technology infrastructure provisioning services", "default_rate": Decimal("18.00")},
    "998316": {"description": "IT infrastructure and network management services", "default_rate": Decimal("18.00")},
    "998319": {"description": "Other information technology services n.e.c.", "default_rate": Decimal("18.00")},
    # Professional Services
    "998221": {"description": "Legal advisory and representation services", "default_rate": Decimal("18.00")},
    "998222": {"description": "Legal documentation and certification services", "default_rate": Decimal("18.00")},
    "998231": {"description": "Accounting, auditing and bookkeeping services", "default_rate": Decimal("18.00")},
    "998232": {"description": "Tax consultancy and preparation services", "default_rate": Decimal("18.00")},
    # Goods
    "847130": {"description": "Laptops, notebooks and portable computers", "default_rate": Decimal("18.00")},
    "851762": {"description": "Routers, switches and communication apparatus", "default_rate": Decimal("18.00")},
}

# Indian State Codes Mapping (GST 2-digit prefixes)
INDIAN_STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan",
    "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand",
    "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh"
}

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def validate_gstin_checksum(gstin: str) -> bool:
    """
    Validates an Indian 15-digit GSTIN using the official Modulus 36 check digit algorithm.
    Format: 2 digits (State) + 10 chars (PAN) + 1 char (Entity code) + 'Z' + 1 check digit.
    """
    if not gstin or len(gstin) != 15:
        return False
    gstin = gstin.upper()
    if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', gstin):
        return False

    factor = 1
    total = 0
    for i in range(14):
        c = gstin[i]
        code_point = GSTIN_CHARS.index(c)
        digit = code_point * factor
        factor = 1 if factor == 2 else 2
        digit = (digit // 36) + (digit % 36)
        total += digit

    remainder = total % 36
    check_code = (36 - remainder) % 36
    calculated_check_char = GSTIN_CHARS[check_code]
    return gstin[14] == calculated_check_char

def calculate_tax_breakdown(
    operating_state: str,
    place_of_supply: str,
    taxable_value: Decimal,
    gst_rate_percent: Decimal
) -> Dict[str, Any]:
    """
    Calculates the exact CGST, SGST, or IGST based on whether the transaction is intra-state or inter-state.
    """
    is_interstate = (operating_state.strip() != place_of_supply.strip())

    if is_interstate:
        # Full GST is IGST
        cgst_rate = Decimal("0.00")
        sgst_rate = Decimal("0.00")
        igst_rate = gst_rate_percent
        cgst_amt = Decimal("0.00")
        sgst_amt = Decimal("0.00")
        igst_amt = round(taxable_value * (igst_rate / Decimal("100.00")), 2)
    else:
        # Split equally into CGST & SGST
        cgst_rate = gst_rate_percent / Decimal("2.00")
        sgst_rate = gst_rate_percent / Decimal("2.00")
        igst_rate = Decimal("0.00")
        cgst_amt = round(taxable_value * (cgst_rate / Decimal("100.00")), 2)
        sgst_amt = round(taxable_value * (sgst_rate / Decimal("100.00")), 2)
        igst_amt = Decimal("0.00")

    total_tax = cgst_amt + sgst_amt + igst_amt
    total_amount = taxable_value + total_tax

    return {
        "is_interstate": is_interstate,
        "taxable_value": taxable_value,
        "cgst_rate": cgst_rate,
        "sgst_rate": sgst_rate,
        "igst_rate": igst_rate,
        "cgst_amount": cgst_amt,
        "sgst_amount": sgst_amt,
        "igst_amount": igst_amt,
        "total_tax": total_tax,
        "total_amount": total_amount
    }
