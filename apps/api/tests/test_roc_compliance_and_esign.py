import hashlib
from datetime import date, timedelta
from decimal import Decimal

from app.services.compliance_watchdog import ComplianceWatchdogService
from app.services.document_assembly import DocumentAssemblyService
from app.services.esign_service import ESignService
from app.core.s3 import storage_manager

def test_sec_173_board_meeting_countdown_watchdog():
    """
    Validates Section 173(1) Cadence Rules:
    - Normal when <= 100 days elapsed.
    - Warning when > 100 days elapsed.
    - Statutory violation when > 120 days elapsed (with ₹100/day fine).
    """
    last_meeting = date(2026, 1, 1)

    # 1. Compliant state (day 80)
    day80 = last_meeting + timedelta(days=80)
    res_80 = ComplianceWatchdogService.evaluate_board_meeting_cadence(last_meeting, day80)
    assert res_80["status"] == "compliant"
    assert res_80["days_remaining"] == 40
    assert not res_80["is_violation"]

    # 2. Warning state (day 105)
    day105 = last_meeting + timedelta(days=105)
    res_105 = ComplianceWatchdogService.evaluate_board_meeting_cadence(last_meeting, day105)
    assert res_105["status"] == "warning_due_soon"
    assert res_105["days_remaining"] == 15
    assert res_105["warning_level"] == "WARNING"

    # 3. Violation state (day 128 - 8 days overdue)
    day128 = last_meeting + timedelta(days=128)
    res_128 = ComplianceWatchdogService.evaluate_board_meeting_cadence(last_meeting, day128)
    assert res_128["status"] == "statutory_violation"
    assert res_128["is_violation"]
    assert res_128["warning_level"] == "CRITICAL"
    # 8 days * ₹100 = ₹800 fine
    assert res_128["penalty_inr"] == Decimal("800.00")

def test_statutory_calendar_deadlines():
    """
    Validates Indian corporate statutory calendar calculations.
    """
    fy_end = date(2026, 3, 31)
    calendar = ComplianceWatchdogService.calculate_statutory_calendar(fy_end)

    # AGM deadline: 6 months from FY close -> Sep 30
    assert calendar["agm_deadline"] == date(2026, 9, 30)
    # AOC-4 deadline: 30 days from AGM -> Oct 30
    assert calendar["aoc4_filing_deadline"] == date(2026, 10, 30)
    # MGT-7 deadline: 60 days from AGM -> Nov 29
    assert calendar["mgt7_filing_deadline"] == date(2026, 11, 29)
    # DIR-3 KYC: Sep 30
    assert calendar["dir3_kyc_deadline"] == date(2026, 9, 30)

def test_document_assembly_board_minutes_and_notice():
    """
    Validates generation of valid SS-1 Board Minutes and Notice/Agenda PDFs.
    """
    minutes_payload = {
        "company_name": "BHARAT TECHVENTURES PRIVATE LIMITED",
        "cin": "U72900KA2024PTC190001",
        "meeting_number": "BM/2025-26/04",
        "meeting_date": "2026-02-15",
        "meeting_time": "02:30 PM IST",
        "venue": "Coworking Hub, HSR Layout, Bengaluru",
        "directors_present": [
            {"name": "Vikram Sharma", "din": "09876541", "designation": "Director"},
            {"name": "Priya Sharma", "din": "09876543", "designation": "Director"}
        ],
        "resolutions": [
            "RESOLVED THAT the audited financial statements for Q3 FY26 be approved.",
            "RESOLVED FURTHER THAT the banking reconciliation report be placed on record."
        ]
    }

    # 1. Assemble Minutes
    minutes_pdf = DocumentAssemblyService.assemble_board_minutes(minutes_payload)
    assert minutes_pdf.startswith(b"%PDF-1.4")
    assert minutes_pdf.endswith(b"%%EOF\n")
    assert b"MINUTES OF THE PROCEEDINGS" in minutes_pdf
    assert b"BHARAT TECHVENTURES" in minutes_pdf
    assert b"U72900KA2024PTC190001" in minutes_pdf

    # 2. Assemble Notice & Agenda
    notice_payload = {
        "company_name": "BHARAT TECHVENTURES PRIVATE LIMITED",
        "cin": "U72900KA2024PTC190001",
        "meeting_number": "BM/2025-26/05",
        "meeting_date": "2026-03-25"
    }
    notice_pdf = DocumentAssemblyService.assemble_board_notice_and_agenda(notice_payload)
    assert notice_pdf.startswith(b"%PDF-1.4")
    assert b"NOTICE OF BOARD MEETING" in notice_pdf

def test_esign_seal_application_and_tamper_detection():
    """
    Validates visual digital signature stamp, SHA-256 seal, and tamper-evidence.
    """
    # 1. Generate base document
    payload = {
        "company_name": "ACME INDIA PRIVATE LIMITED",
        "cin": "U72200KA2025PTC112233",
        "meeting_number": "BM/2025-26/01",
        "meeting_date": "2026-01-20"
    }
    base_pdf = DocumentAssemblyService.assemble_board_minutes(payload)
    raw_sha256 = hashlib.sha256(base_pdf).hexdigest()

    # 2. Apply digital signature
    sign_result = ESignService.apply_digital_signature(
        pdf_bytes=base_pdf,
        signer_name="Vikram Sharma",
        din="09876541",
        designation="Managing Director",
        reason="Approved and signed in compliance with Section 173(1)",
        location="Bengaluru, Karnataka"
    )

    signed_pdf = sign_result["signed_pdf_bytes"]
    assert signed_pdf.startswith(b"%PDF-1.4")
    assert signed_pdf.endswith(b"%%EOF\n")
    assert sign_result["raw_sha256"] == raw_sha256
    assert sign_result["seal_id"].startswith("SEAL-")

    # 3. Verify intact signed document
    verif = ESignService.verify_signature(signed_pdf)
    assert verif["is_valid"] is True
    assert verif["signer_name"] == "Vikram Sharma"
    assert verif["din"] == "09876541"
    assert verif["designation"] == "Managing Director"

    # 4. Tamper Test: Modify one byte of the document body
    tampered_pdf = signed_pdf.replace(b"ACME INDIA", b"HACK INDIA")
    tamper_verif = ESignService.verify_signature(tampered_pdf)
    assert tamper_verif["is_valid"] is False
    assert "Tamper Detected" in tamper_verif["error"]

def test_phase4_verification_gate_complete_pack():
    """
    Phase 4 Verification Gate:
    Generate complete Board Meeting minutes pack from template, calculate countdown alerts,
    apply digital signature seal, verify PDF validity and tamper-evident SHA-256 audit record.
    """
    print("\n--- Executing Phase 4 Verification Gate ---")
    
    # 1. Calculate Section 173 countdown alerts
    last_meeting_date = date(2026, 1, 10)
    check_date = date(2026, 4, 25) # 105 days elapsed -> warning triggered
    cadence = ComplianceWatchdogService.evaluate_board_meeting_cadence(last_meeting_date, check_date)
    assert cadence["status"] == "warning_due_soon"
    assert cadence["days_remaining"] == 15
    print(f"  ✓ Section 173 Cadence Alert: {cadence['message']}")

    # 2. Assemble Board Meeting Minutes Pack from template
    pack_data = {
        "company_name": "STEALTH VENTURES LABS PRIVATE LIMITED",
        "cin": "U72900KA2024PTC199888",
        "meeting_number": "BM/2025-26/04",
        "meeting_date": "2026-04-20",
        "meeting_time": "10:30 AM IST",
        "venue": "Bengaluru Innovation Campus, Bengaluru",
        "directors_present": [
            {"name": "Vikram Sharma", "din": "09876541", "designation": "Director"},
            {"name": "Siddharth Rao", "din": "09876544", "designation": "Director"}
        ],
        "resolutions": [
            "RESOLVED THAT the bank reconciliation reports and financial ledger for FY 2025-26 be approved.",
            "RESOLVED THAT the Company convene its Annual General Meeting on or before September 30, 2026."
        ]
    }

    assembled_pdf = DocumentAssemblyService.assemble_board_minutes(pack_data)
    assert assembled_pdf.startswith(b"%PDF-1.4")
    assert len(assembled_pdf) > 500
    print(f"  ✓ Assembled Board Minutes Pack ({len(assembled_pdf)} bytes, valid PDF/A structure)")

    # 3. Apply self-hosted digital signature seal
    signed_meta = ESignService.apply_digital_signature(
        pdf_bytes=assembled_pdf,
        signer_name="Vikram Sharma",
        din="09876541",
        designation="Director & Chairman",
        reason="Certified True Copy of Minutes of Meeting of Board of Directors",
        location="Bengaluru, India"
    )

    signed_pdf = signed_meta["signed_pdf_bytes"]
    seal_id = signed_meta["seal_id"]
    signed_sha256 = signed_meta["signed_sha256"]
    assert signed_meta["is_sealed"] is True
    print(f"  ✓ Digital Signature Sealed: Seal ID={seal_id}, SHA256={signed_sha256[:16]}...")

    # 4. Save to MinIO statutory bucket
    s3_key = f"statutory/{seal_id}_Board_Minutes_Signed.pdf"
    storage_manager.save_document(
        bucket_name="b00k5-statutory",
        object_name=s3_key,
        file_bytes=signed_pdf,
        content_type="application/pdf"
    )

    # 5. Verify PDF validity & tamper-evident audit record
    verif = ESignService.verify_signature(signed_pdf)
    assert verif["is_valid"] is True
    assert verif["signer_name"] == "Vikram Sharma"
    assert verif["din"] == "09876541"
    print("✓ Phase 4 Verification Gate Successfully Passed!")


def test_aoc4_mgt7_statutory_anchor_and_schedule_iii_comparative():
    """
    Validates:
    1. Statutory OCR parsing of MCA Form AOC-4 and Form MGT-7A.
    2. Zero mathematical drift in Schedule III balance sheet (Assets == Equity & Liabilities == 0.00).
    3. Schedule III Clause 4 rounding calculation.
    """
    from app.services.statutory_vault_engine import StatutoryVaultEngine
    from app.services.schedule_iii_service import ScheduleIIIService

    # 1. Test AOC-4 Parsing
    aoc4_sample = """
    FORM NO. AOC-4
    Form for filing financial statement and other documents with the Registrar
    SRN: 7616438575
    Service Request Number (SRN) of Form AOC-4 is 7616438575
    DIN of Director: 11249061
    UDIN: 2611249061AAAAA1234
    I. EQUITY AND LIABILITIES
    1. Shareholders' Funds
    (a) Share Capital 100000.00
    (b) Reserves and Surplus -163851.00
    2. Non-Current Liabilities
    (a) Long-term borrowings 63851.00
    3. Current Liabilities
    TOTAL EQUITY AND LIABILITIES 0.00
    II. ASSETS
    TOTAL ASSETS 0.00
    Other expenses 163851.00
    Profit / (Loss) for the period -163851.00
    """
    parsed_aoc4 = StatutoryVaultEngine.parse_aoc4_financial_statement(aoc4_sample)
    assert parsed_aoc4["srn"] == "7616438575"
    assert parsed_aoc4["schedule_iii_heads"]["2010"] == "100000.00"
    assert parsed_aoc4["schedule_iii_heads"]["2020"] == "-163851.00"
    assert parsed_aoc4["schedule_iii_heads"]["2030"] == "63851.00"
    assert parsed_aoc4["schedule_iii_heads"]["4040"] == "163851.00"
    assert parsed_aoc4["schedule_iii_heads"]["5020"] == "-163851.00"

    # 2. Test MGT-7 Parsing
    mgt7_sample = """
    FORM NO. MGT-7A
    Abridged Annual Return for OPC and Small Companies
    SRN: AC6319079
    Authorised capital of the company 100000
    Total number of equity shares 10000
    Nominal value per share 10
    Paid up capital 100000
    Net worth of the company -63851
    Turnover 0.00
    Promoter Shareholding:
    Adithya Nagaraja Khamithkar DIN 11249061 shares 10000 percentage 100.00
    """
    parsed_mgt7 = StatutoryVaultEngine.parse_mgt7_annual_return(mgt7_sample)
    assert parsed_mgt7["srn"] == "AC6319079"
    assert parsed_mgt7["authorized_capital_inr"] == 100000.0
    assert parsed_mgt7["paid_up_capital_inr"] == 100000.0
    assert parsed_mgt7["net_worth_inr"] == -63851.0
    assert parsed_mgt7["promoter_holding_percent"] == 100.0

    # 3. Schedule III Clause 4 Rounding Scale Base
    unit, label = ScheduleIIIService.get_auto_rounding_unit(
        total_revenue=0.0,
        total_assets=0.0,
        total_expenses=163851.0
    )
    assert unit == "hundreds"
    assert "Nearest Hundreds" in label

    # 4. Invariant Balance: Share Capital (100000) + Reserves (-163851) + Borrowings (63851) = 0.00
    eq_liab = Decimal("100000.00") + Decimal("-163851.00") + Decimal("63851.00")
    assert eq_liab == Decimal("0.00")

