"""
Official GSTN (Goods and Services Tax Network) Unique Quantity Codes (UQC)
Catalog, Chapter 99 Service Invariants, and Validation Utilities.
"""

from typing import Dict, Tuple

# Official 44+ GSTN UQC standard dictionary (3-letter codes mapped to descriptions)
GSTN_UQC_CATALOG: Dict[str, str] = {
    "BAG": "BAGS",
    "BAL": "BALE",
    "BDL": "BUNDLES",
    "BKL": "BUCKLES",
    "BOU": "BILLION OF UNITS",
    "BOX": "BOX",
    "BTL": "BOTTLES",
    "BUN": "BUNCHES",
    "CAN": "CANS",
    "CBM": "CUBIC METERS",
    "CCM": "CUBIC CENTIMETERS",
    "CMS": "CENTIMETERS",
    "CTN": "CARTONS",
    "DOZ": "DOZENS",
    "DRM": "DRUMS",
    "GGK": "GREAT GROSS",
    "GMS": "GRAMMES",
    "GRS": "GROSS",
    "GYD": "GROSS YARDS",
    "KGS": "KILOGRAMS",
    "KLR": "KILOLITRE",
    "KME": "KILOMETRE",
    "MLT": "MILLILITRE",
    "MTR": "METERS",
    "MTS": "METRIC TON",
    "NOS": "NUMBERS",
    "PAC": "PACKS",
    "PCS": "PIECES",
    "PRS": "PAIRS",
    "QTL": "QUINTAL",
    "ROL": "ROLLS",
    "SET": "SETS",
    "SQF": "SQUARE FEET",
    "SQM": "SQUARE METERS",
    "SQY": "SQUARE YARDS",
    "TBS": "TABLETS",
    "TGM": "TEN GROSS",
    "THD": "THOUSANDS",
    "TON": "TONNES",
    "TUB": "TUBES",
    "UGS": "US GALLONS",
    "UNT": "UNITS",
    "YDS": "YARDS",
    "OTH": "OTHERS",
    "NA": "NOT APPLICABLE (SERVICES)",
}


def is_service_hsn(hsn_sac: str) -> bool:
    """
    Returns True if HSN/SAC belongs to Chapter 99 (Services).
    All services under Chapter 99 MUST report UQC as 'NA' per GSTN rules.
    """
    clean = str(hsn_sac or "").strip()
    return clean.startswith("99")


def resolve_uqc(hsn_sac: str, raw_uqc: str = None) -> str:
    """
    Enforces GSTN UQC rules:
    - If Chapter 99 (Services): strictly returns 'NA'.
    - If Goods: returns upper-cased valid UQC or defaults to 'NOS'. 'NA' is not allowed for goods.
    """
    if is_service_hsn(hsn_sac):
        return "NA"

    clean_uqc = str(raw_uqc or "NOS").strip().upper()
    if clean_uqc == "NA" or clean_uqc not in GSTN_UQC_CATALOG:
        return "NOS"
    return clean_uqc


def validate_uqc(hsn_sac: str, uqc: str) -> Tuple[bool, str]:
    """
    Validates UQC compatibility with HSN/SAC code:
    Returns (is_valid, error_message).
    """
    clean_hsn = str(hsn_sac or "").strip()
    clean_uqc = str(uqc or "").strip().upper()

    if is_service_hsn(clean_hsn):
        if clean_uqc != "NA":
            return False, f"Services under Chapter 99 ({clean_hsn}) must strictly report UQC as 'NA'."
        return True, ""

    if clean_uqc == "NA":
        return False, f"Goods under HSN ({clean_hsn}) cannot have UQC as 'NA'. Select an official unit (e.g. NOS, BOX, KGS)."

    if clean_uqc not in GSTN_UQC_CATALOG:
        return False, f"Invalid UQC '{clean_uqc}'. Must be one of standard GSTN unit codes."

    return True, ""

