import re
from typing import List, Optional

OCR_MERCHANT_BLACKLIST: List[str] = [
    "SIGNATURE VALID",
    "DIGITALLY SIGNED",
    "SIGNATURE NOT VERIFIED",
    "DOCUMENT CERTIFIED",
    "TAX INVOICE",
    "ORIGINAL FOR RECIPIENT",
    "DUPLICATE FOR TRANSPORTER",
    "INVOICE",
    "BILL OF SUPPLY",
    "SIGNATURE",
    "SIGNED BY",
    "AUTHENTICATED",
    "TAX INVOICE/BILL OF SUPPLY",
    "ORIGINAL",
    "DUPLICATE",
    "TRIPLICATE"
]

def is_blacklisted_merchant(merchant_name: str) -> bool:
    """Checks whether the extracted merchant candidate matches signature noise or tax invoice headers."""
    if not merchant_name:
        return True
    cleaned = merchant_name.strip().upper()
    for bad in OCR_MERCHANT_BLACKLIST:
        if bad in cleaned or cleaned == bad:
            return True
    return False

def extract_counterparty_from_invoice_text(text: str) -> Optional[str]:
    """
    Extracts the genuine selling entity from marketplace bills (Amazon, Flipkart, etc.),
    bypassing digital signature blocks and tax invoice titles.
    """
    # 1. Search for explicit Sold By / Seller block
    sold_by_patterns = [
        r'(?:Sold\s*By|Seller\s*Details|Seller\s*Name|Billed\s*By)\s*[:\-]?\s*([^\n\r]+)',
        r'(?:Appario\s*Retail\s*Private\s*Limited|Cloudtail\s*India\s*Private\s*Limited|Amazon\s*Seller\s*Services\s*Private\s*Limited)',
        r'(?:Sold\s*by\s*:\s*)([A-Za-z0-9\s\.\&,\-]+?)(?=\n|PAN|GSTIN|CIN|State|$)'
    ]
    for pat in sold_by_patterns:
        m = re.search(pat, text, re.I)
        if m:
            cand = m.group(1).strip() if m.groups() else m.group(0).strip()
            if not is_blacklisted_merchant(cand) and len(cand) > 3:
                return cand

    # 2. Marketplace sellers & Cloud providers keywords
    text_upper = text.upper()
    if "AMAZON WEB SERVICES" in text_upper or "AWS " in text_upper or " AWS" in text_upper or "ELASTIC COMPUTE" in text_upper:
        return "Amazon Web Services India Pvt Ltd"
    if "APPARIO" in text_upper:
        return "Appario Retail Private Limited"
    if "CLOUDTAIL" in text_upper:
        return "Cloudtail India Private Limited"
    if "AMAZON SELLER" in text_upper or "AMAZON.IN" in text_upper or "AMAZON" in text_upper:
        return "Amazon Seller Services Private Limited"

    return None

