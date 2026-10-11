from datetime import datetime, date
from decimal import Decimal
import io
import re
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple

from app.services.bank_tokenizer import IndianPaymentTokenizer

logger = logging.getLogger("b00k5_bank_parser")

DATE_PATTERNS = [
    re.compile(r'^\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b'),
    re.compile(r'^\b(\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})\b'),
]

# Currency amount regex
AMOUNT_PATTERN = re.compile(r'^-?[0-9]+(?:,[0-9]+)*(?:\.[0-9]{2})?$')

STOP_KEYWORDS = [
    "ACCOUNT RELATIONSHIP SUMMARY", "SUMMARY", "DEBIT COUNT", "CREDIT COUNT",
    "TOTAL WITHDRAWAL BALANCE", "SWEEP IN FD", "DETAILS OF TD", "FD NUMBER",
    "DISCLAIMER", "PAGE ", "STATEMENT AS ON", "CUSTOMER EMAIL", "LIMIT :",
    "TOTAL WITHDRAWABLE BALANCE", "STATEMENT OF ACCOUNT", "TOTAL DEPOSITS",
    "TOTAL WITHDRAWALS", "CURRENT ACCOUNTS", "TERM DEPOSITS", "INTEREST PAID",
    "NOMINATION :", "ACCOUNT BRANCH :", "RTGS/NEFT IFSC :"
]


def parse_indian_amount(val_str: Any) -> Decimal:
    """Parses Indian formatted currency strings like '1,50,000.50' into Decimal."""
    if val_str is None:
        return Decimal("0.00")
    if isinstance(val_str, (int, float, Decimal)):
        return Decimal(str(val_str))
    val_str = str(val_str).strip()
    if not val_str:
        return Decimal("0.00")
    clean = val_str.replace(",", "").replace(" ", "").replace("₹", "").replace("Rs.", "").strip()
    if clean in ["-", "", "0", "0.00", "0.0", "Nil", "NIL"]:
        return Decimal("0.00")
    clean = clean.replace("Cr", "").replace("Dr", "").replace("CR", "").replace("DR", "").strip()
    try:
        return Decimal(clean)
    except Exception:
        return Decimal("0.00")


def parse_date(date_str: Any) -> Optional[date]:
    """Parses DD/MM/YYYY, DD/MM/YY, DD-MM-YYYY, DD-MM-YY, D/M/YYYY, etc."""
    if not date_str:
        return None
    date_str = str(date_str).strip().replace(".", "/")
    formats = [
        "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y",
        "%d %b %Y", "%d %b %y", "%d %B %Y", "%Y-%m-%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    # Try regex fallback for 1- or 2-digit days/months: 2/12/2025
    m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$', date_str)
    if m:
        d, mth, y = m.groups()
        yr = int(y)
        if yr < 100:
            yr += 2000
        try:
            return date(yr, int(mth), int(d))
        except ValueError:
            pass
    return None


class IndianBankPDFParser:
    """
    Local-first table & text extractor tuned for Indian banking layouts (HDFC, ICICI, SBI, Axis, Kotak).
    Zero cloud API dependencies. Features multi-page continuity, dynamic header detection,
    narration unwrapping, OCR image support, and running balance mathematical verification.
    """

    @staticmethod
    def detect_bank_format(text_sample: str) -> str:
        upper = text_sample.upper()
        if "HDFC BANK" in upper or "HDFC" in upper:
            return "HDFC"
        elif "ICICI BANK" in upper or "ICICI" in upper:
            return "ICICI"
        elif "STATE BANK OF INDIA" in upper or "SBI" in upper:
            return "SBI"
        elif "AXIS BANK" in upper or "AXIS" in upper:
            return "AXIS"
        elif "KOTAK" in upper:
            return "KOTAK"
        return "OTHER"

    @staticmethod
    def extract_statement_metadata(full_text: str) -> Dict[str, Any]:
        """
        Extracts bank statement metadata (Account Number, Customer ID, Account Holder Name,
        Branch, IFSC, MICR, Opening/Closing Balances, Statement Dates) across all pages.
        """
        bank_name = IndianBankPDFParser.detect_bank_format(full_text[:4000])

        # 1. Account Number
        # Matches HDFC 14-digit format or generic Account Number prefixes
        acc_num = None
        acc_match = (
            re.search(r'(?:Account\s*Number|Account\s*No|A/c\s*No|A/C\s*Number|Account\s*#)[^\d\n]*([0-9]{9,18})', full_text, re.IGNORECASE)
            or re.search(r'\b(50[0-9]{12})\b', full_text)
            or re.search(r'\b([0-9]{11,18})\b', full_text)
        )
        if acc_match:
            acc_num = acc_match.group(1).strip()
            # If OCR clipped leading 5 from 14-digit HDFC account number (e.g. '0200114206173')
            if bank_name == "HDFC" and len(acc_num) == 13 and acc_num.startswith(("01", "02", "00")):
                acc_num = "5" + acc_num
        else:
            acc_num = "XXXX001"

        # 2. Customer ID
        cust_match = re.search(r'Customer\s*ID[^\d\n]*([0-9]{6,12})', full_text, re.IGNORECASE)
        cust_id = cust_match.group(1).strip() if cust_match else None

        # 3. Account / Entity Name
        account_name = None
        for line in full_text.splitlines()[:20]:
            clean_l = line.strip()
            if any(term in clean_l.lower() for term in [
                "private limited", "pvt ltd", "llp", "limited", "technologies",
                "solutions", "enterprises", "opc", "corp", "associates"
            ]):
                account_name = clean_l
                break

        # 4. IFSC & MICR
        ifsc_match = re.search(r'(?:IFSC|RTGS/NEFT\s*IFSC)[^\w\n]*([A-Z]{4}0[A-Z0-9]{6})', full_text, re.IGNORECASE)
        ifsc = ifsc_match.group(1).strip() if ifsc_match else None

        micr_match = re.search(r'MICR[^\d\n]*([0-9]{9})', full_text, re.IGNORECASE)
        micr = micr_match.group(1).strip() if micr_match else None

        # 5. Branch
        branch_match = re.search(r'Account\s*Branch[^\w\n]*([A-Za-z0-9\s]+?)(?:\n|102|$)', full_text, re.IGNORECASE)
        branch = branch_match.group(1).strip() if branch_match else None

        # 6. Statement Dates
        dates_match = re.search(r'Statement\s*From[^\d\n]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*To[^\d\n]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', full_text, re.IGNORECASE)
        stmt_from = parse_date(dates_match.group(1)) if dates_match else None
        stmt_to = parse_date(dates_match.group(2)) if dates_match else None
        if not stmt_to:
            as_on_match = re.search(r'Statement\s*as\s*on[^\d\n]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', full_text, re.IGNORECASE)
            if as_on_match:
                stmt_to = parse_date(as_on_match.group(1))

        # 7. Opening Balance
        op_bal_match = re.search(r'Opening\s*Balance[^\d\n]*([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
        opening_balance = parse_indian_amount(op_bal_match.group(1)) if op_bal_match else None

        # 8. Closing Balance
        cl_bal_match = (
            re.search(r'Closing\s*Balance[^\d\n]*([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
            or re.search(r'Total\s*Withdrawal\s*Balance\**[^\d\n]*([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
        )
        closing_balance = parse_indian_amount(cl_bal_match.group(1)) if cl_bal_match else None

        # 9. Debits and Credits
        debit_amt_match = re.search(r'Debit\s*Amount[^\d\n]*([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
        total_debits = parse_indian_amount(debit_amt_match.group(1)) if debit_amt_match else None

        credit_amt_match = re.search(r'Credit\s*Amount[^\d\n]*([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
        total_credits = parse_indian_amount(credit_amt_match.group(1)) if credit_amt_match else None

        # Summary Block Table: Opening Balance | Debit Amount | Credit Amount | Closing Balance
        summary_block_match = re.search(
            r'Opening\s*Balance\s+Debit\s*Amount\s+Credit\s*Amount\s+Closing\s*Balance\s*\n\s*([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})',
            full_text, re.IGNORECASE
        )
        if summary_block_match:
            if opening_balance is None:
                opening_balance = parse_indian_amount(summary_block_match.group(1))
            if total_debits is None:
                total_debits = parse_indian_amount(summary_block_match.group(2))
            if total_credits is None:
                total_credits = parse_indian_amount(summary_block_match.group(3))
            if closing_balance is None:
                closing_balance = parse_indian_amount(summary_block_match.group(4))

        return {
            "bank_name": bank_name,
            "account_number": acc_num,
            "customer_id": cust_id,
            "account_name": account_name,
            "ifsc": ifsc,
            "micr": micr,
            "branch": branch,
            "statement_from": stmt_from,
            "statement_to": stmt_to,
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "total_withdrawals": total_debits,
            "total_deposits": total_credits
        }

    @staticmethod
    def process_tables(tables: List[List[List[str]]], bank_name: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parses structured 2D table arrays from PDF extraction table-by-table.
        Prevents non-transaction tables (e.g., Relationship Summary or TD interest) from polluting records.
        """
        parsed_records: List[Dict[str, Any]] = []
        line_num = 1

        for table in tables:
            if not table or len(table) < 2:
                continue

            # Detect if this specific table has transaction headers
            header_idx = -1
            col_map: Dict[str, int] = {}
            for r_idx, row in enumerate(table[:5]):
                row_str = " ".join([str(c).upper() for c in row if c])
                if any(d in row_str for d in ["TXN DATE", "TRAN DATE", "TRANSACTION DATE", "DATE", "VAL DATE", "VALUE DT"]) and \
                   any(k in row_str for k in ["NARRATION", "DESCRIPTION", "PARTICULARS", "REMARKS"]):
                    header_idx = r_idx
                    for c_idx, cell in enumerate(row):
                        cu = str(cell).upper().strip()
                        if any(d in cu for d in ["TXN DATE", "TRAN DATE", "TRANSACTION DATE", "DATE"]) and "VALUE" not in cu and "VAL" not in cu:
                            col_map["date"] = c_idx
                        elif any(v in cu for v in ["VALUE DT", "VAL DT", "VALUE DATE", "VAL DATE"]):
                            col_map["value_date"] = c_idx
                        elif any(k in cu for k in ["NARRATION", "DESCRIPTION", "PARTICULARS", "REMARKS"]):
                            col_map["narration"] = c_idx
                        elif any(r in cu for r in ["CHQ", "CHEQUE", "REF", "UTR"]):
                            col_map["ref"] = c_idx
                        elif any(w in cu for w in ["WITHDRAWAL", "DEBIT", "DR"]):
                            col_map["withdrawal"] = c_idx
                        elif any(d in cu for d in ["DEPOSIT", "CREDIT", "CR"]):
                            col_map["deposit"] = c_idx
                        elif "BALANCE" in cu:
                            col_map["balance"] = c_idx
                    break

            if header_idx == -1 or "date" not in col_map or "narration" not in col_map:
                continue

            # Process data rows of this transaction table
            for row in table[header_idx + 1:]:
                if not row or not any(row):
                    continue

                row_str = " ".join([str(c).upper() for c in row if c])
                if any(stop_kw in row_str for stop_kw in STOP_KEYWORDS):
                    continue

                raw_date = row[col_map["date"]].strip() if col_map["date"] < len(row) and row[col_map["date"]] else ""
                parsed_d = parse_date(raw_date)

                if not parsed_d:
                    # Potential narration continuation
                    if parsed_records and col_map["narration"] < len(row) and row[col_map["narration"]]:
                        cont_text = str(row[col_map["narration"]]).strip()
                        if not any(stop_kw in cont_text.upper() for stop_kw in ["SUMMARY", "BALANCE", "FD NUMBER", "OPENING"]):
                            clean_cont = cont_text.replace("\n", " ").strip()
                            if clean_cont:
                                parsed_records[-1]["description"] += " " + clean_cont
                                tok = IndianPaymentTokenizer.tokenize_narration(parsed_records[-1]["description"])
                                if tok.get("reference_number"):
                                    parsed_records[-1]["reference_number"] = tok["reference_number"]
                                if tok.get("counterparty_name"):
                                    parsed_records[-1]["counterparty_name"] = tok["counterparty_name"]
                                parsed_records[-1]["payment_channel"] = tok.get("payment_channel", "OTHER")
                    continue

                narration = str(row[col_map["narration"]]).strip().replace("\n", " ") if col_map["narration"] < len(row) and row[col_map["narration"]] else ""
                if "OPENING BALANCE" in narration.upper():
                    continue

                val_date_str = str(row[col_map["value_date"]]).strip() if "value_date" in col_map and col_map["value_date"] < len(row) and row[col_map["value_date"]] else ""
                val_date = parse_date(val_date_str) or parsed_d

                w_str = str(row[col_map["withdrawal"]]).strip() if "withdrawal" in col_map and col_map["withdrawal"] < len(row) and row[col_map["withdrawal"]] else "0.00"
                d_str = str(row[col_map["deposit"]]).strip() if "deposit" in col_map and col_map["deposit"] < len(row) and row[col_map["deposit"]] else "0.00"
                b_str = str(row[col_map["balance"]]).strip() if "balance" in col_map and col_map["balance"] < len(row) and row[col_map["balance"]] else "0.00"

                withdrawal = parse_indian_amount(w_str)
                deposit = parse_indian_amount(d_str)
                balance = parse_indian_amount(b_str)

                explicit_ref = str(row[col_map["ref"]]).strip() if "ref" in col_map and col_map["ref"] < len(row) and row[col_map["ref"]] else None
                tok = IndianPaymentTokenizer.tokenize_narration(narration)
                final_ref = explicit_ref or tok.get("reference_number")

                parsed_records.append({
                    "line_number": line_num,
                    "transaction_date": parsed_d,
                    "value_date": val_date,
                    "description": narration,
                    "reference_number": final_ref,
                    "payment_channel": tok.get("payment_channel", "OTHER"),
                    "counterparty_name": tok.get("counterparty_name") or "Counterparty",
                    "withdrawal_amount": withdrawal,
                    "deposit_amount": deposit,
                    "running_balance": balance,
                })
                line_num += 1

        return parsed_records

    @staticmethod
    def process_table_rows(rows: List[List[str]], bank_name: str = "HDFC") -> Dict[str, Any]:
        """Backwards compatible wrapper for single flat table arrays."""
        meta = IndianBankPDFParser.extract_statement_metadata("")
        records = IndianBankPDFParser.process_tables([rows], bank_name, meta)
        return IndianBankPDFParser.assemble_statement_result(records, meta, bank_name)

    @staticmethod
    def parse_text_lines(raw_lines: List[str], bank_name: str = "HDFC", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Deterministic parser for lines extracted from text statements or OCR.
        Uses exact regex matching for dates at the head and 2-3 currency amounts at the tail.
        """
        full_text = "\n".join(raw_lines)
        meta = metadata or IndianBankPDFParser.extract_statement_metadata(full_text)

        parsed_records: List[Dict[str, Any]] = []
        line_num = 1
        current_record: Optional[Dict[str, Any]] = None

        # Regex matching date at start and amount(s) at end
        TXN_3_AMOUNTS_RE = re.compile(
            r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.*?)\s+([0-9,]+\.\d{2}|-)\s+([0-9,]+\.\d{2}|-)\s+(-?[0-9,]+\.\d{2})\s*(?:CR|DR)?$',
            re.IGNORECASE
        )
        TXN_2_AMOUNTS_RE = re.compile(
            r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.*?)\s+([0-9,]+\.\d{2}|-)\s+(-?[0-9,]+\.\d{2})\s*(CR|DR)?$',
            re.IGNORECASE
        )
        DATE_START_RE = re.compile(r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b')

        for raw in raw_lines:
            line = raw.strip()
            if not line:
                continue

            line_up = line.upper()
            # Skip stop headers/footers
            if any(stop_kw in line_up for stop_kw in STOP_KEYWORDS):
                if current_record:
                    parsed_records.append(current_record)
                    current_record = None
                continue

            # Check for Opening Balance line
            if "OPENING BALANCE" in line_up:
                if current_record:
                    parsed_records.append(current_record)
                    current_record = None
                continue

            # 1. Try 3 amounts regex match
            m3 = TXN_3_AMOUNTS_RE.match(line)
            if m3:
                if current_record:
                    parsed_records.append(current_record)
                dt_str, narr, w_str, d_str, b_str = m3.groups()
                txn_d = parse_date(dt_str) or date.today()
                tok = IndianPaymentTokenizer.tokenize_narration(narr)
                current_record = {
                    "line_number": line_num,
                    "transaction_date": txn_d,
                    "value_date": txn_d,
                    "description": narr.strip(),
                    "reference_number": tok.get("reference_number"),
                    "payment_channel": tok.get("payment_channel", "OTHER"),
                    "counterparty_name": tok.get("counterparty_name") or "Counterparty",
                    "withdrawal_amount": parse_indian_amount(w_str),
                    "deposit_amount": parse_indian_amount(d_str),
                    "running_balance": parse_indian_amount(b_str),
                }
                line_num += 1
                continue

            # 2. Try 2 amounts regex match
            m2 = TXN_2_AMOUNTS_RE.match(line)
            if m2:
                if current_record:
                    parsed_records.append(current_record)
                dt_str, narr, amt_str, b_str, cr_dr = m2.groups()
                txn_d = parse_date(dt_str) or date.today()
                tok = IndianPaymentTokenizer.tokenize_narration(narr)
                amt = parse_indian_amount(amt_str)
                bal = parse_indian_amount(b_str)
                is_cr = (cr_dr and cr_dr.upper() == "CR") or "CR" in narr.upper() or "DEPOSIT" in narr.upper()
                w = Decimal("0.00") if is_cr else amt
                d = amt if is_cr else Decimal("0.00")
                current_record = {
                    "line_number": line_num,
                    "transaction_date": txn_d,
                    "value_date": txn_d,
                    "description": narr.strip(),
                    "reference_number": tok.get("reference_number"),
                    "payment_channel": tok.get("payment_channel", "OTHER"),
                    "counterparty_name": tok.get("counterparty_name") or "Counterparty",
                    "withdrawal_amount": w,
                    "deposit_amount": d,
                    "running_balance": bal,
                }
                line_num += 1
                continue

            # 3. Date start fallback
            m_date = DATE_START_RE.match(line)
            if m_date:
                if current_record:
                    parsed_records.append(current_record)
                dt_str = m_date.group(1)
                txn_d = parse_date(dt_str) or date.today()
                rest = line[len(dt_str):].strip()

                amounts = [parse_indian_amount(a) for a in re.findall(r'(-?[0-9,]+\.\d{2})', rest)]
                clean_narr = re.sub(r'(-?[0-9,]+\.\d{2})', '', rest).strip()

                w = Decimal("0.00")
                d = Decimal("0.00")
                bal = Decimal("0.00")
                if len(amounts) >= 3:
                    w = amounts[-3]
                    d = amounts[-2]
                    bal = amounts[-1]
                elif len(amounts) == 2:
                    bal = amounts[1]
                    if "CR" in rest.upper() or "DEPOSIT" in rest.upper():
                        d = amounts[0]
                    else:
                        w = amounts[0]
                elif len(amounts) == 1:
                    bal = amounts[0]

                tok = IndianPaymentTokenizer.tokenize_narration(clean_narr)
                current_record = {
                    "line_number": line_num,
                    "transaction_date": txn_d,
                    "value_date": txn_d,
                    "description": clean_narr,
                    "reference_number": tok.get("reference_number"),
                    "payment_channel": tok.get("payment_channel", "OTHER"),
                    "counterparty_name": tok.get("counterparty_name") or "Counterparty",
                    "withdrawal_amount": w,
                    "deposit_amount": d,
                    "running_balance": bal,
                }
                line_num += 1
            else:
                # Continuation text
                if current_record:
                    if not any(stop_kw in line_up for stop_kw in ["SUMMARY", "BALANCE", "FD NUMBER", "OPENING"]):
                        current_record["description"] += " " + line
                        tok = IndianPaymentTokenizer.tokenize_narration(current_record["description"])
                        if tok.get("reference_number"):
                            current_record["reference_number"] = tok["reference_number"]
                        if tok.get("counterparty_name"):
                            current_record["counterparty_name"] = tok["counterparty_name"]
                        current_record["payment_channel"] = tok.get("payment_channel", "OTHER")

        if current_record:
            parsed_records.append(current_record)

        return IndianBankPDFParser.assemble_statement_result(parsed_records, meta, bank_name)

    @staticmethod
    def assemble_statement_result(
        records: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        bank_name: str
    ) -> Dict[str, Any]:
        """
        Calculates totals, computes/validates opening and closing balances,
        and returns the consolidated statement payload.
        """
        total_withdrawals = sum(r["withdrawal_amount"] for r in records)
        total_deposits = sum(r["deposit_amount"] for r in records)

        # Opening balance resolution
        opening_bal = metadata.get("opening_balance")
        if opening_bal is None:
            if records:
                opening_bal = records[0]["running_balance"] + records[0]["withdrawal_amount"] - records[0]["deposit_amount"]
            else:
                opening_bal = Decimal("0.00")

        # Closing balance resolution
        closing_bal = metadata.get("closing_balance")
        if closing_bal is None:
            if records:
                closing_bal = records[-1]["running_balance"]
            else:
                closing_bal = opening_bal

        calc_closing = opening_bal + total_deposits - total_withdrawals
        is_verified = (calc_closing == closing_bal) or (abs(calc_closing - closing_bal) < Decimal("0.05"))

        return {
            "bank_name": metadata.get("bank_name") or bank_name,
            "account_number": metadata.get("account_number") or "XXXX001",
            "account_name": metadata.get("account_name"),
            "customer_id": metadata.get("customer_id"),
            "ifsc": metadata.get("ifsc"),
            "micr": metadata.get("micr"),
            "branch": metadata.get("branch"),
            "statement_from": metadata.get("statement_from") or (records[0]["transaction_date"] if records else None),
            "statement_to": metadata.get("statement_to") or (records[-1]["transaction_date"] if records else None),
            "opening_balance": opening_bal,
            "closing_balance": closing_bal,
            "total_withdrawals": total_withdrawals,
            "total_deposits": total_deposits,
            "lines": records,
            "total_transactions": len(records),
            "is_balance_verified": is_verified
        }

    @staticmethod
    def parse_pdf_bytes(pdf_bytes: bytes, password: Optional[str] = None) -> Dict[str, Any]:
        """
        Primary extractor for bank statement PDF bytes.
        Checks encryption with pypdf, extracts tabular data with pdfplumber,
        falls back to stream text extraction, and supports OCR on scanned PDFs.
        """
        if not pdf_bytes or len(pdf_bytes) == 0:
            return IndianBankPDFParser.assemble_statement_result([], {}, "OTHER")

        # 1. Check for encryption via pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            if reader.is_encrypted:
                if not password:
                    return {
                        "needs_password": True,
                        "error": "This bank statement PDF is password-protected. Please enter your account password."
                    }
                try:
                    dec = reader.decrypt(password)
                    if dec == 0:
                        return {
                            "needs_password": True,
                            "error": "Incorrect PDF password. Please check your password (e.g., PAN, Cust ID) and try again."
                        }
                except Exception:
                    return {
                        "needs_password": True,
                        "error": "Failed to decrypt PDF with the provided password."
                    }
        except Exception as e:
            # Corrupted PDF stream
            err = str(e).lower()
            if "password" in err or "encrypted" in err:
                return {
                    "needs_password": True,
                    "error": "This statement is encrypted. Please provide the PDF password."
                }
            if not pdf_bytes.startswith(b"%PDF"):
                return IndianBankPDFParser.assemble_statement_result([], {}, "OTHER")

        full_text = ""
        all_tables: List[List[List[str]]] = []

        # 2. Extract with pdfplumber if available
        try:
            import pdfplumber
            open_kwargs = {"password": password} if password else {}
            with pdfplumber.open(io.BytesIO(pdf_bytes), **open_kwargs) as pdf:
                for page in pdf.pages:
                    p_text = page.extract_text() or ""
                    full_text += p_text + "\n"
                    page_tables = page.extract_tables() or []
                    for t in page_tables:
                        cleaned_t = [[cell.strip() if cell else "" for cell in r] for r in t if any(r)]
                        if cleaned_t:
                            all_tables.append(cleaned_t)
        except Exception as e:
            logger.info(f"pdfplumber table extraction bypassed or failed ({e}), using pypdf fallback")

        # 3. If full_text is still empty, extract via pypdf
        if not full_text.strip():
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(pdf_bytes))
                for page in reader.pages:
                    full_text += (page.extract_text() or "") + "\n"
            except Exception:
                pass

        # 4. Scanned PDF fallback: If text is empty, render pages to images and run pytesseract
        if not full_text.strip():
            try:
                from pdf2image import convert_from_bytes
                import pytesseract
                images = convert_from_bytes(pdf_bytes, first_page=1, last_page=5)
                for img in images:
                    full_text += pytesseract.image_to_string(img) + "\n"
            except Exception as ocr_err:
                logger.warning(f"OCR rendering fallback error: {ocr_err}")

        # Detect Bank and Extract Metadata
        metadata = IndianBankPDFParser.extract_statement_metadata(full_text)
        bank_name = metadata.get("bank_name", "HDFC")

        # 5. Process tables if found
        if all_tables:
            records = IndianBankPDFParser.process_tables(all_tables, bank_name, metadata)
            if records:
                return IndianBankPDFParser.assemble_statement_result(records, metadata, bank_name)

        # 6. Fallback to line parser
        return IndianBankPDFParser.parse_text_lines(full_text.splitlines(), bank_name, metadata)

    @staticmethod
    def parse_image_bytes(image_bytes: bytes) -> Dict[str, Any]:
        """
        Parses bank statements uploaded as image files (PNG, JPG, JPEG).
        Applies grayscale and Lanczos upscaling for high-contrast OCR clarity,
        extracts metadata, and parses tabular lines.
        """
        try:
            import pytesseract
            from PIL import Image, ImageOps
            img = Image.open(io.BytesIO(image_bytes))
            
            # Preprocess: convert to grayscale and upscale 2x for sharper character recognition
            gray = ImageOps.grayscale(img)
            resized = gray.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
            
            # Try PSM 6 (uniform block of text) first, fallback to default PSM 3 if needed
            full_text = pytesseract.image_to_string(resized, config="--psm 6")
            if not full_text.strip() or len(full_text.splitlines()) < 3:
                full_text = pytesseract.image_to_string(resized)
            if not full_text.strip():
                full_text = pytesseract.image_to_string(img)
                
            metadata = IndianBankPDFParser.extract_statement_metadata(full_text)
            bank_name = metadata.get("bank_name", "HDFC")
            return IndianBankPDFParser.parse_text_lines(full_text.splitlines(), bank_name, metadata)
        except Exception as e:
            logger.error(f"Image OCR bank parsing failed: {e}")
            return IndianBankPDFParser.assemble_statement_result([], {}, "OTHER")

    @staticmethod
    def parse_file_bytes(file_bytes: bytes, filename: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        """
        Universal file dispatcher: handles both PDFs and Image formats seamlessly.
        """
        fn = (filename or "").lower()
        if fn.endswith((".png", ".jpg", ".jpeg", ".webp", ".tiff")) or file_bytes.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF")):
            return IndianBankPDFParser.parse_image_bytes(file_bytes)
        return IndianBankPDFParser.parse_pdf_bytes(pdf_bytes=file_bytes, password=password)

    @staticmethod
    def parse_pdf(pdf_bytes: bytes, filename: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        """Convenience alias for parse_file_bytes."""
        return IndianBankPDFParser.parse_file_bytes(pdf_bytes, filename=filename, password=password)


BankStatementParser = IndianBankPDFParser


def compute_line_fingerprint(
    account_id: str,
    txn_date: Any,
    amount: Any,
    balance: Any,
    ref: Optional[str] = "",
    sequence_disambiguator: Optional[str] = ""
) -> str:
    """
    Computes a deterministic, collision-resistant canonical SHA-256 fingerprint for a bank transaction line.
    Normalizes account, date, amount (2 decimals), balance (2 decimals), and reference string.
    Because `running_balance` changes on each sequential same-day transaction even if two payments to the
    same vendor on the same date have the exact same amount, legitimate distinct payments produce distinct
    fingerprints while re-uploads of the same statement line produce identical fingerprints.
    """
    norm_acc = str(account_id or "").strip()
    norm_date = str(txn_date or "").strip()
    try:
        norm_amt = f"{Decimal(str(amount or '0.00')).quantize(Decimal('0.01'))}"
    except Exception:
        norm_amt = str(amount or "").strip()
    try:
        norm_bal = f"{Decimal(str(balance or '0.00')).quantize(Decimal('0.01'))}"
    except Exception:
        norm_bal = str(balance or "").strip()
    clean_ref = re.sub(r'[^a-zA-Z0-9]', '', str(ref or "")).lower()
    disambig = f"|{sequence_disambiguator}" if sequence_disambiguator else ""

    canonical = f"{norm_acc}|{norm_date}|{norm_amt}|{norm_bal}|{clean_ref}{disambig}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def detect_statement_overlap(
    new_statement: Dict[str, Any],
    existing_statements: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    UAT-06 & Section 7 Statement Overlap Detector:
    Identifies exact duplicate periods vs partial date-range overlaps across statements for the same account,
    and checks opening/closing balance continuity across overlapping boundaries.
    """
    new_acc = str(new_statement.get("account_number") or "").strip()
    new_from = new_statement.get("statement_from")
    new_to = new_statement.get("statement_to")
    new_open = Decimal(str(new_statement.get("opening_balance", "0.00")))

    if not (new_acc and new_from and new_to):
        return {"has_overlap": False, "overlap_type": "none", "conflicting_statements": []}

    conflicts = []
    for ex in existing_statements:
        if str(ex.get("account_number") or "").strip() != new_acc:
            continue
        ex_from = ex.get("statement_from")
        ex_to = ex.get("statement_to")
        if not (ex_from and ex_to):
            continue

        if new_from == ex_from and new_to == ex_to:
            conflicts.append({
                "statement_id": ex.get("id"),
                "overlap_type": "EXACT_PERIOD_DUPLICATE",
                "existing_from": ex_from,
                "existing_to": ex_to,
                "balance_consistent": (new_open == Decimal(str(ex.get("opening_balance", "0.00"))))
            })
        elif new_from <= ex_to and new_to >= ex_from:
            conflicts.append({
                "statement_id": ex.get("id"),
                "overlap_type": "PARTIAL_DATE_RANGE_OVERLAP",
                "existing_from": ex_from,
                "existing_to": ex_to,
                "overlap_start": max(new_from, ex_from),
                "overlap_end": min(new_to, ex_to),
            })

    return {
        "has_overlap": len(conflicts) > 0,
        "overlap_type": conflicts[0]["overlap_type"] if conflicts else "none",
        "conflicting_statements": conflicts,
    }


def validate_uploaded_document_safety(
    arg1: Any,
    arg2: Any = None,
    arg3: Any = None,
    max_size_bytes: int = 15 * 1024 * 1024,
    max_pdf_pages: int = 50,
    max_image_pixels: int = 25_000_000
) -> Dict[str, Any]:
    """
    SEC-05 & UAT-16 Untrusted Upload & Document Boundary Validator:
    Supports both:
      - validate_uploaded_document_safety(file_bytes: bytes, filename: str, ...) -> raises ValueError on violation
      - validate_uploaded_document_safety(filename: str, file_bytes: bytes, content_type: str = None) -> returns {"is_safe": bool, "reason": str, ...}
    """
    import os
    if isinstance(arg1, (bytes, bytearray)):
        file_bytes = bytes(arg1)
        filename = str(arg2 or "")
        raise_on_error = True
    else:
        filename = str(arg1 or "")
        file_bytes = bytes(arg2) if isinstance(arg2, (bytes, bytearray)) else b""
        raise_on_error = False

    def _fail(msg: str) -> Dict[str, Any]:
        if raise_on_error:
            raise ValueError(msg)
        return {"safe": False, "is_safe": False, "reason": msg, "sanitized_filename": ""}

    if not filename or any(tok in filename for tok in ("..", "/", "\\", "\x00")):
        return _fail("Security Violation [SEC-05]: Unsafe or path-traversal filename rejected.")

    if not file_bytes or len(file_bytes) == 0:
        return _fail("Security Violation [SEC-05]: Empty file payload rejected.")

    if len(file_bytes) > max_size_bytes:
        return _fail(
            f"Security Violation [SEC-05]: File size ({len(file_bytes)} bytes) exceeds maximum allowed limit ({max_size_bytes} bytes)."
        )

    is_pdf = file_bytes.startswith(b"%PDF-")
    is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
    is_csv_or_txt = (
        not raise_on_error
        and filename.lower().endswith((".csv", ".txt", ".json"))
        and not file_bytes.startswith((b"MZ", b"\x7fELF", b"#!/", b"<?php"))
    )

    if not (is_pdf or is_png or is_jpeg or is_csv_or_txt):
        return _fail("Security Violation [SEC-05]: Unsupported or spoofed file header (must be valid PDF, PNG, or JPEG).")

    if is_pdf:
        upper_slice = file_bytes[:min(len(file_bytes), 512 * 1024)]
        for forbidden_tag in (b"/JavaScript", b"/JS ", b"/JS(", b"/JS<", b"/Launch", b"/RichMedia"):
            if forbidden_tag in upper_slice:
                return _fail(
                    f"Security Violation [SEC-05]: Active or executable PDF content ({forbidden_tag.decode('ascii', errors='ignore')}) is forbidden."
                )
        page_occurrences = file_bytes.count(b"/Type /Page") - file_bytes.count(b"/Type /Pages")
        if page_occurrences > max_pdf_pages:
            return _fail(
                f"Security Violation [SEC-05]: PDF page count ({page_occurrences}) exceeds maximum limit ({max_pdf_pages})."
            )

    if is_png or is_jpeg:
        from PIL import Image
        orig_max = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = max_image_pixels
            with Image.open(io.BytesIO(file_bytes)) as img:
                width, height = img.size
                if width * height > max_image_pixels:
                    return _fail(
                        f"Security Violation [SEC-05]: Image resolution ({width}x{height}) exceeds decompression bomb threshold."
                    )
        except Image.DecompressionBombError as dbe:
            return _fail(f"Security Violation [SEC-05]: Image decompression bomb detected: {dbe}")
        except ValueError as ve:
            return _fail(str(ve))
        except Exception as img_err:
            return _fail(f"Security Violation [SEC-05]: Malformed or corrupted image stream: {img_err}")
        finally:
            Image.MAX_IMAGE_PIXELS = orig_max

    safe_name = os.path.basename(filename.strip())
    return {
        "safe": True,
        "is_safe": True,
        "sanitized_filename": safe_name,
        "mime_detected": "application/pdf" if is_pdf else ("image/png" if is_png else ("image/jpeg" if is_jpeg else "text/plain")),
        "size_bytes": len(file_bytes),
    }



