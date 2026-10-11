from datetime import date, timedelta
from decimal import Decimal
from typing import List, Tuple, Dict, Any
import random
from app.services.bank_tokenizer import IndianPaymentTokenizer
from app.services.bank_parser import IndianBankPDFParser, parse_indian_amount
from app.services.reconciliation_engine import ReconciliationEngine, calculate_name_similarity

def test_tokenizer_upi():
    narration = "UPI/409823124567/PAYMENT TO SWIGGY/swiggy@icici/HDFC"
    res = IndianPaymentTokenizer.tokenize_narration(narration)
    assert res["payment_channel"] == "UPI"
    assert res["reference_number"] == "409823124567"
    assert "SWIGGY" in (res["counterparty_name"] or "")

def test_tokenizer_neft():
    narration = "NEFT CR-HDFC0001234-ACME CORP-N12345678901"
    res = IndianPaymentTokenizer.tokenize_narration(narration)
    assert res["payment_channel"] == "NEFT"
    assert "N12345678901" in (res["reference_number"] or "")
    assert "ACME CORP" in (res["counterparty_name"] or "")

def test_tokenizer_imps():
    narration = "IMPS/P2A/409823124567/RAZORPAY SOFTWARE/HDFC"
    res = IndianPaymentTokenizer.tokenize_narration(narration)
    assert res["payment_channel"] == "IMPS"
    assert res["reference_number"] == "409823124567"
    assert "RAZORPAY" in (res["counterparty_name"] or "")

def test_tokenizer_cheque():
    narration = "CHQ DEP / 001234 / HDFC CLEARING"
    res = IndianPaymentTokenizer.tokenize_narration(narration)
    assert res["payment_channel"] == "CHEQUE"
    assert res["reference_number"] == "001234"

def test_fuzzy_name_matching():
    # Minor differences in company names
    score = calculate_name_similarity("Acme Labs Pvt Ltd", "Acme Labs Private Limited")
    assert score >= 80.0

    score2 = calculate_name_similarity("Zomato Media Private Limited", "ZOMATO")
    assert score2 >= 40.0

def generate_sample_hdfc_statement_200_transactions() -> Tuple[List[str], Decimal, Decimal, Decimal, Decimal]:
    """
    Generates a realistic 200-transaction HDFC Bank statement text dump.
    Returns: (raw_lines, opening_balance, closing_balance, total_withdrawals, total_deposits)
    """
    lines = [
        "HDFC BANK LIMITED",
        "INDUMATI COMPLEX, 100 FEET ROAD, INDIRANAGAR, BENGALURU - 560038",
        "Statement of Account No: 50200012345678",
        "Period: 01/01/2026 to 28/02/2026",
        "--------------------------------------------------------------------------------",
        "Date       Narration                                  Chq/Ref No    Withdrawal     Deposit     Closing Balance",
        "--------------------------------------------------------------------------------",
    ]

    running_balance = Decimal("500000.00") # Starting opening balance: 5 Lakhs
    opening_balance = running_balance
    total_withdrawals = Decimal("0.00")
    total_deposits = Decimal("0.00")

    counterparties = [
        ("INFOSYS BPO LIMITED", "NEFT"),
        ("SWIGGY DINING", "UPI"),
        ("AMAZON WEB SERVICES INDIA", "NEFT"),
        ("GOOGLE CLOUD INDIA PVT LTD", "IMPS"),
        ("RAZORPAY SOFTWARE PRIVATE LIMITED", "UPI"),
        ("WEWORK INDIA MANAGEMENT", "NEFT"),
        ("AIRTEL BROADBAND SERVICES", "UPI"),
        ("DEV CONTRACTOR STIPEND", "IMPS"),
        ("HDFC BANK CONSOLIDATED CHARGES", "CHARGES"),
        ("CLIENT ACME CORP US WIRE", "RTGS"),
    ]

    start_date = date(2026, 1, 1)

    for i in range(200):
        current_date = start_date + timedelta(days=(i // 4))
        date_str = current_date.strftime("%d/%m/%y")
        cp, channel = counterparties[i % len(counterparties)]

        ref_id = f"{409800000000 + i}"
        if channel == "UPI":
            narration = f"UPI/{ref_id}/{cp}/pay@{channel.lower()}"
        elif channel == "NEFT":
            narration = f"NEFT CR-HDFC0001234-{cp}-N{ref_id}"
        elif channel == "IMPS":
            narration = f"IMPS/P2A/{ref_id}/{cp}/HDFC"
        elif channel == "RTGS":
            narration = f"RTGS CR-HDFC0000001-{cp}-R{ref_id}"
        elif channel == "CHARGES":
            narration = f"CHRG: CONSOLIDATED QUARTERLY SERVICE CHARGES"
            ref_id = ""
        else:
            narration = f"CLR CHQ {100000+i} {cp}"
            ref_id = f"{100000+i}"

        # Alternating deposits and withdrawals
        is_deposit = (i % 3 == 0)
        amount = Decimal(f"{((i * 137) % 25000) + 150}.00")

        if is_deposit:
            withdrawal = Decimal("0.00")
            deposit = amount
            running_balance += deposit
            total_deposits += deposit
            withdrawal_str = "0.00"
            deposit_str = f"{deposit:,.2f}"
        else:
            withdrawal = amount
            deposit = Decimal("0.00")
            running_balance -= withdrawal
            total_withdrawals += withdrawal
            withdrawal_str = f"{withdrawal:,.2f}"
            deposit_str = "0.00"

        balance_str = f"{running_balance:,.2f}"

        # Standard HDFC row
        row = f"{date_str}  {narration}  {ref_id}  {withdrawal_str}  {deposit_str}  {balance_str}"
        lines.append(row)

        # Inject periodic multi-line wraps for realistic statement simulation
        if i % 15 == 0:
            lines.append(f"            REFUND VOUCHER SEQUENCE ID #{i*999}")

    return lines, opening_balance, running_balance, total_withdrawals, total_deposits

def test_hdfc_statement_200_transactions_verification_gate():
    """
    Phase 2 Verification Gate:
    Upload a sample HDFC statement containing 200 mixed transactions;
    parser must correctly extract >= 98% of transactions into bank_statement_lines
    with ZERO total balance discrepancy.
    """
    raw_lines, exp_open, exp_close, exp_withdrawals, exp_deposits = generate_sample_hdfc_statement_200_transactions()

    parsed = IndianBankPDFParser.parse_text_lines(raw_lines, "HDFC")

    # 1. Extraction rate check: Must extract >= 98% (>= 196 / 200)
    total_extracted = parsed["total_transactions"]
    extraction_rate = (total_extracted / 200) * 100.0
    assert extraction_rate >= 98.0, f"Extraction rate {extraction_rate}% is below the required 98% gate! ({total_extracted}/200)"

    # 2. Mathematical zero balance discrepancy check
    calc_close = parsed["closing_balance"]
    assert calc_close == exp_close, f"Balance discrepancy! Expected closing balance {exp_close}, but parser calculated {calc_close}."

    assert parsed["total_withdrawals"] == exp_withdrawals, f"Withdrawals mismatch: {parsed['total_withdrawals']} != {exp_withdrawals}"
    assert parsed["total_deposits"] == exp_deposits, f"Deposits mismatch: {parsed['total_deposits']} != {exp_deposits}"

def test_3tier_reconciliation_logic():
    """
    Verifies Tier 1 (Deterministic), Tier 2 (Window Heuristic), and Tier 3 (Suspense) matching.
    """
    open_invoices = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "invoice_number": "INV-2026-001",
            "issue_date": date(2026, 1, 10),
            "grand_total": Decimal("150000.00"),
            "contact_name": "Infosys BPO Limited",
            "notes": "INV-2026-001"
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "invoice_number": "INV-2026-002",
            "issue_date": date(2026, 1, 15),
            "grand_total": Decimal("75000.00"),
            "contact_name": "Zomato Media Private Limited",
            "notes": "INV-2026-002"
        }
    ]

    # 1. Tier 1 exact match (contains INV-2026-001 and amount 150000.00)
    line_t1 = {
        "transaction_date": date(2026, 1, 12),
        "description": "NEFT CR-HDFC0001234-INFOSYS-INV-2026-001",
        "reference_number": "INV-2026-001",
        "counterparty_name": "INFOSYS",
        "deposit_amount": Decimal("150000.00")
    }
    match1 = ReconciliationEngine.match_tier1(line_t1, open_invoices)
    assert match1 is not None
    inv1, score1 = match1
    assert inv1["invoice_number"] == "INV-2026-001"
    assert score1 == 100.00

    # 2. Tier 2 heuristic match (Date Jan 17, within window of Jan 15, name 'Zomato Media', amount 75000.00)
    line_t2 = {
        "transaction_date": date(2026, 1, 17),
        "description": "UPI/998877665544/ZOMATO MEDIA/vpa@icici",
        "reference_number": "998877665544",
        "counterparty_name": "ZOMATO MEDIA",
        "deposit_amount": Decimal("75000.00")
    }
    match2 = ReconciliationEngine.match_tier2(line_t2, open_invoices)
    assert match2 is not None
    inv2, score2 = match2
    assert inv2["invoice_number"] == "INV-2026-002"
    assert score2 >= 70.00

    # 3. Tier 3 Unmatched record (Random vendor, not in invoices)
    line_t3 = {
        "transaction_date": date(2026, 1, 20),
        "description": "UPI/112233445566/UNKNOWN CLIENT/pay@upi",
        "reference_number": "112233445566",
        "counterparty_name": "UNKNOWN CLIENT",
        "deposit_amount": Decimal("3300.00")
    }
    assert ReconciliationEngine.match_tier1(line_t3, open_invoices) is None
    assert ReconciliationEngine.match_tier2(line_t3, open_invoices) is None
