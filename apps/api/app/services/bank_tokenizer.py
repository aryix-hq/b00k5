import re
from typing import Dict, Any, Optional

class IndianPaymentTokenizer:
    """
    Regex tokenization engine for Indian banking transaction narrations:
    Isolates standard payment schemes (UPI, NEFT, RTGS, IMPS, Cheques) and counterparties.
    """

    # 12-digit UPI RRN retrieval reference number
    UPI_REGEX = re.compile(r'UPI[/_-](?:CR/|DR/)?([0-9]{12})', re.IGNORECASE)
    # NEFT standard formats (N-prefix or UTR)
    NEFT_REGEX = re.compile(r'NEFT\s*(?:CR|DR)?[/_-]([A-Z0-9]{11,22})', re.IGNORECASE)
    # RTGS standard formats (R-prefix or UTR)
    RTGS_REGEX = re.compile(r'RTGS\s*(?:CR|DR)?[/_-]([A-Z0-9]{11,22})', re.IGNORECASE)
    # IMPS 12-digit reference
    IMPS_REGEX = re.compile(r'IMPS[/_-](?:P2A/|P2P/)?([0-9]{12})', re.IGNORECASE)
    # Cheque numbers (6 digits)
    CHQ_REGEX = re.compile(r'(?:CHQ|CHEQUE|CLR|CLG)[ \-\/:]*([0-9]{6})', re.IGNORECASE)

    @staticmethod
    def tokenize_narration(narration: str) -> Dict[str, Any]:
        text = narration.strip()
        channel = "OTHER"
        ref_number: Optional[str] = None
        counterparty: Optional[str] = None

        # Check UPI
        upi_match = IndianPaymentTokenizer.UPI_REGEX.search(text)
        if upi_match or "UPI/" in text.upper() or "UPI-" in text.upper() or "UPI" in text.upper():
            channel = "UPI"
            if upi_match:
                ref_number = upi_match.group(1)
            else:
                # Look for 12-digit ref number anywhere in UPI text
                r_match = re.search(r'(?:Ref|RRN|UPI)[:\s\/-]*([0-9]{12})', text, re.IGNORECASE) or re.search(r'\b([0-9]{12})\b', text)
                if r_match:
                    ref_number = r_match.group(1)

            # Counterparty heuristic:
            parts = re.split(r'[/_-]', text)
            if len(parts) >= 2:
                # If parts[1] is name (e.g. 'UPI-TUV SUD South Asia P-...')
                if not parts[1].isdigit() and parts[1].upper() not in ["CR", "DR", "P2A", "P2P"] and len(parts[1]) > 2:
                    counterparty = parts[1].strip()
                elif len(parts) >= 3 and not parts[2].isdigit() and parts[2].upper() not in ["CR", "DR", "P2A", "P2P"]:
                    counterparty = parts[2].strip()
                elif len(parts) >= 4 and not parts[3].isdigit():
                    counterparty = parts[3].strip()

        # Check NEFT
        elif "NEFT" in text.upper():
            channel = "NEFT"
            # Standard Indian NEFT UTR: N followed by digits/alphanumeric (>=10 chars)
            utr_match = re.search(r'\b(N[0-9A-Z]{9,21})\b', text, re.IGNORECASE)
            if utr_match:
                ref_number = utr_match.group(1).upper()
            else:
                neft_match = IndianPaymentTokenizer.NEFT_REGEX.search(text)
                if neft_match:
                    ref_number = neft_match.group(1).upper()

            parts = [p.strip() for p in re.split(r'[/_-]', text) if p.strip()]
            for p in parts:
                p_up = p.upper()
                if p_up in ["NEFT", "CR", "DR", "NEFT CR", "NEFT DR"]:
                    continue
                if ref_number and p_up == ref_number:
                    continue
                if re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', p_up):
                    continue
                if len(p) >= 3 and not p.isdigit():
                    counterparty = p
                    break

        # Check RTGS
        elif "RTGS" in text.upper():
            channel = "RTGS"
            utr_match = re.search(r'\b(R[0-9A-Z]{9,21})\b', text, re.IGNORECASE)
            if utr_match:
                ref_number = utr_match.group(1).upper()
            else:
                rtgs_match = IndianPaymentTokenizer.RTGS_REGEX.search(text)
                if rtgs_match:
                    ref_number = rtgs_match.group(1).upper()

            parts = [p.strip() for p in re.split(r'[/_-]', text) if p.strip()]
            for p in parts:
                p_up = p.upper()
                if p_up in ["RTGS", "CR", "DR", "RTGS CR", "RTGS DR"]:
                    continue
                if ref_number and p_up == ref_number:
                    continue
                if re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', p_up):
                    continue
                if len(p) >= 3 and not p.isdigit():
                    counterparty = p
                    break

        # Check IMPS
        elif "IMPS" in text.upper():
            channel = "IMPS"
            imps_match = IndianPaymentTokenizer.IMPS_REGEX.search(text)
            if imps_match:
                ref_number = imps_match.group(1)
            parts = [p.strip() for p in re.split(r'[/_-]', text) if p.strip()]
            for p in parts:
                p_up = p.upper()
                if p_up in ["IMPS", "P2A", "P2P", "CR", "DR"]:
                    continue
                if ref_number and p_up == ref_number:
                    continue
                if p.isdigit():
                    continue
                if len(p) >= 3:
                    counterparty = p
                    break

        # Check Cheque
        elif any(k in text.upper() for k in ["CHQ", "CHEQUE", "CLEARING"]):
            channel = "CHEQUE"
            chq_match = re.search(r'\b([0-9]{6})\b', text)
            if chq_match:
                ref_number = chq_match.group(1)
            parts = [p.strip() for p in re.split(r'[/_-]', text) if p.strip()]
            for p in parts:
                p_up = p.upper()
                if any(x in p_up for x in ["CHQ", "CHEQUE", "CLEARING", "DEP", "WDL"]):
                    continue
                if ref_number and p_up == ref_number:
                    continue
                if p.isdigit():
                    continue
                if len(p) >= 3:
                    counterparty = p
                    break

        # Bank Charges heuristic
        elif any(k in text.upper() for k in ["CHRG", "CHARGE", "ANNUAL FEE", "INTEREST"]):
            channel = "CHARGES"
            counterparty = "Bank Service Charges"

        # General cleanup of counterparty
        if counterparty:
            # Remove VPA handles like @okhdfcbank or @icici
            counterparty = re.sub(r'@[a-zA-Z0-9]+', '', counterparty).strip()
            # Clean non-alphanumeric noise
            counterparty = re.sub(r'[^a-zA-Z0-9\s\.\&\-]', '', counterparty).strip()
            if len(counterparty) < 2:
                counterparty = None

        return {
            "payment_channel": channel,
            "reference_number": ref_number,
            "counterparty_name": counterparty,
            "raw_narration": text
        }
