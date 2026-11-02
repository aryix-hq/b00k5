"""
Unit and Integration Tests for Stakeholder-Centric Auditor Dossier
and Dual-Plane BCP / Disaster Recovery Cloud Backup Hierarchy.
Governed by FEAT-OPS-06 / PLAN-006.
"""

import io
import json
import zipfile
import hashlib
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.tenant import Tenant
from app.models.invoice import Invoice
from app.models.expense import Expense
from app.models.bank import BankStatement
from app.models.vault import DocumentVault
from app.services.auditor_dossier_service import AuditorDossierService
from app.services.gdrive_virtualizer import DirectoryVirtualizer, get_indian_fy_ay_label, get_indian_fiscal_year


def test_get_indian_fy_ay_label():
    """Validates Indian Financial Year and Assessment Year string generation."""
    # Test April 15, 2025 -> FY 2025-26, AY 2026-27
    fy, ay, folder = get_indian_fy_ay_label(date(2025, 4, 15))
    assert fy == "2025-26"
    assert ay == "2026-27"
    assert folder == "FY 2025-26 (AY 2026-27)"

    # Test March 31, 2026 -> FY 2025-26, AY 2026-27
    fy2, ay2, folder2 = get_indian_fy_ay_label(date(2026, 3, 31))
    assert fy2 == "2025-26"
    assert ay2 == "2026-27"
    assert folder2 == "FY 2025-26 (AY 2026-27)"

    # Test April 1, 2026 -> FY 2026-27, AY 2027-28
    fy3, ay3, folder3 = get_indian_fy_ay_label(date(2026, 4, 1))
    assert fy3 == "2026-27"
    assert ay3 == "2027-28"
    assert folder3 == "FY 2026-27 (AY 2027-28)"


def test_directory_virtualizer_statutory_dossier_path():
    """Validates stakeholder-aligned dossier paths for cloud mirroring."""
    root = "b00k5_ARYIX_OPC"

    # 1. Invoice path
    inv_path = DirectoryVirtualizer.build_statutory_dossier_path(
        category="invoices",
        file_name="INV_2025_001.pdf",
        doc_date=date(2025, 6, 15),
        root_folder=root
    )
    assert inv_path == f"{root}/FY 2025-26 (AY 2026-27)/05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/Monthly_Sales_Invoices/INV_2025_001.pdf"

    # 2. Bank statement path
    stmt_path = DirectoryVirtualizer.build_statutory_dossier_path(
        category="statements",
        file_name="HDFC_May_2025.pdf",
        doc_date=date(2025, 5, 31),
        root_folder=root
    )
    assert stmt_path == f"{root}/FY 2025-26 (AY 2026-27)/04_BANKING_CASH_AND_TREASURY_RECONCILIATION/Statements/HDFC_May_2025.pdf"

    # 3. Permanent vault document path (Root-level, outside FY)
    vault_path = DirectoryVirtualizer.build_statutory_dossier_path(
        category="vault",
        file_name="Certificate_of_Incorporation.pdf",
        doc_date=date(2024, 1, 10),
        root_folder=root
    )
    assert vault_path == f"{root}/00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/Permanent_Records/Certificate_of_Incorporation.pdf"

    # 4. Machine-Plane Checkpoint path
    cp_path = DirectoryVirtualizer.build_statutory_dossier_path(
        category="checkpoints",
        file_name="b00k5_snapshot_20260401.dump.enc",
        root_folder=root
    )
    assert cp_path == f"{root}/checkpoints/b00k5_snapshot_20260401.dump.enc"


@pytest.mark.asyncio
async def test_auditor_dossier_9_section_stakeholder_hierarchy():
    """
    Validates that AuditorDossierService generates the complete 9-section stakeholder hierarchy
    and produces a cryptographically sealed ZIP package.
    """
    # 1. Mock Tenant
    tenant = MagicMock(spec=Tenant)
    tenant.id = "00000000-0000-0000-0000-000000000001"
    tenant.legal_name = "ARYIX (OPC) PRIVATE LIMITED"
    tenant.trade_name = "ARYIX"
    tenant.cin = "U72200KA2024OPC186412"
    tenant.pan = "AABCA1234F"
    tenant.gstin = "29AABCA1234F1Z5"
    tenant.registered_office = "No. 42, Sovereign Tech Park, Bangalore, KA, India"
    tenant.statutory_profile = {
        "auditor_name": "Sharma & Associates",
        "auditor_frn": "123456N",
        "membership_no": "543210",
        "inc20a_verified": True,
        "aoc4_verified": True,
        "mgt7_verified": True,
        "itr_verified": True
    }

    # 2. Mock Invoices
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.id = "11111111-1111-1111-1111-111111111111"
    mock_inv.invoice_number = "INV/2025-26/001"
    mock_inv.issue_date = date(2025, 5, 10)
    mock_inv.due_date = date(2025, 6, 10)
    mock_inv.subtotal = Decimal("10000.00")
    mock_inv.cgst_total = Decimal("900.00")
    mock_inv.sgst_total = Decimal("900.00")
    mock_inv.igst_total = Decimal("0.00")
    mock_inv.grand_total = Decimal("11800.00")
    mock_inv.status = "paid"
    mock_inv.place_of_supply = "29"
    mock_inv.is_interstate = False
    mock_inv.contact = None
    mock_inv.pdf_s3_key = None

    # 3. Mock Expenses
    mock_exp = MagicMock(spec=Expense)
    mock_exp.id = "22222222-2222-2222-2222-222222222222"
    mock_exp.journal_entry_number = "EXP-2025-001"
    mock_exp.merchant_name = "AWS Cloud India"
    mock_exp.category = "Software & Cloud Services"
    mock_exp.expense_date = date(2025, 5, 12)
    mock_exp.total_amount = Decimal("2360.00")
    mock_exp.cgst_amount = Decimal("180.00")
    mock_exp.sgst_amount = Decimal("180.00")
    mock_exp.igst_amount = Decimal("0.00")
    mock_exp.itc_eligible = True
    mock_exp.payment_mode = "company_bank"
    mock_exp.paid_personally = False
    mock_exp.director_name = None
    mock_exp.merchant_gstin = "29AAACW1234F1Z1"
    mock_exp.status = "approved"
    mock_exp.settlement_status = "settled"
    mock_exp.notes = "Monthly cloud server hosting"
    mock_exp.receipt_s3_key = None
    mock_exp.receipt_sha256 = None

    # 4. Mock Bank Statements
    mock_stmt = MagicMock(spec=BankStatement)
    mock_stmt.id = "33333333-3333-3333-3333-333333333333"
    mock_stmt.bank_name = "HDFC Bank"
    mock_stmt.account_number = "50200012345678"
    mock_stmt.statement_from = date(2025, 5, 1)
    mock_stmt.statement_to = date(2025, 5, 31)
    mock_stmt.opening_balance = Decimal("50000.00")
    mock_stmt.total_deposits = Decimal("11800.00")
    mock_stmt.total_withdrawals = Decimal("2360.00")
    mock_stmt.closing_balance = Decimal("59440.00")
    mock_stmt.file_name = "HDFC_Statement_May2025.pdf"
    mock_stmt.s3_key = None
    mock_stmt.status = "verified"
    mock_stmt.lines = []

    # 5. Mock Permanent & Annual Vault Documents
    mock_coi = MagicMock(spec=DocumentVault)
    mock_coi.id = "44444444-4444-4444-4444-444444444444"
    mock_coi.document_name = "Certificate_of_Incorporation"
    mock_coi.category = "corporate_legal"
    mock_coi.document_number = "U72200KA2024OPC186412"
    mock_coi.minio_s3_key = None
    mock_coi.sha256_hash = "fake_sha256_coi"
    mock_coi.metadata_json = {"document_type": "coi"}

    mock_aoc4 = MagicMock(spec=DocumentVault)
    mock_aoc4.id = "55555555-5555-5555-5555-555555555555"
    mock_aoc4.document_name = "Form_AOC-4_Financials"
    mock_aoc4.category = "statutory_filing"
    mock_aoc4.document_number = "SRN-AOC4-2025"
    mock_aoc4.minio_s3_key = None
    mock_aoc4.sha256_hash = "fake_sha256_aoc4"
    mock_aoc4.metadata_json = {"fiscal_year": "2025-26", "document_type": "aoc_4"}

    # Mock DB queries
    async def mock_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_inv]
        elif "FROM expenses" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_exp]
        elif "FROM bank_statements" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_stmt]
        elif "FROM document_vault" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_coi, mock_aoc4]
        else:
            mock_result.scalars.return_value.all.return_value = []
        return mock_result

    db = AsyncMock()
    db.execute.side_effect = mock_execute

    # 6. Generate Auditor Dossier for FY 2025-26
    zip_bytes, zip_filename = await AuditorDossierService.generate_auditor_dossier(
        db=db,
        tenant=tenant,
        fy="2025-26"
    )

    assert zip_filename.endswith(".zip")
    assert "2025-26" in zip_filename

    # Unpack ZIP and assert 9-section structure
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    namelist = zf.namelist()

    # SECTION 0: Founder & CFO Executive Overview & Permanent Identity
    assert any("00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/01_Executive_Financial_And_Compliance_Briefing.txt" in n for n in namelist)
    assert any("00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/02_Statutory_Compliance_Health_Scorecard.txt" in n for n in namelist)
    assert any("00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/03_Permanent_Corporate_Identity/Certificate_of_Incorporation.pdf" in n for n in namelist)
    assert any("00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/Statutory_Governance_Profile.json" in n for n in namelist)

    # SECTION 1: CA & External Auditor Schedule III Financials & CARO 2020
    assert any("01_STATUTORY_FINANCIAL_STATEMENTS_SCHEDULE_III/CARO_2020_Companies_Auditor_Report_Order.txt" in n for n in namelist)

    # SECTION 2: Company Secretary (CS) Governance & MCA
    assert any("02_CORPORATE_GOVERNANCE_AND_SECRETARIAL_MCA/03_MCA_Annual_Filings/Form_AOC-4_Financials.pdf" in n for n in namelist)

    # SECTION 4: Banking, Cash & Treasury
    assert any("04_BANKING_CASH_AND_TREASURY_RECONCILIATION/Statements/HDFC_Statement_May2025.pdf" in n for n in namelist)
    assert any("04_BANKING_CASH_AND_TREASURY_RECONCILIATION/Bank_Statements_Register_FY2025-26.csv" in n for n in namelist)
    assert any("04_BANKING_CASH_AND_TREASURY_RECONCILIATION/BRS_Summary_FY2025-26.csv" in n for n in namelist)

    # SECTION 5: Sales Revenue & Debtors Ageing
    assert any("05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/Monthly_Sales_Invoices" in n for n in namelist)
    assert any("05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/Invoices_Summary_FY2025-26.csv" in n for n in namelist)
    assert any("05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/Trade_Receivables_Debtors_Ageing_Schedule.csv" in n for n in namelist)

    # SECTION 6: Expenses, Bills, MSME Creditors Ageing & ITC Register
    assert any("06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/Monthly_Vendor_Bills_And_Vouchers" in n for n in namelist)
    assert any("06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/Bills_Expenses_Summary_FY2025-26.csv" in n for n in namelist)
    assert any("06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/Input_Tax_Credit_ITC_Eligibility_Register.csv" in n for n in namelist)
    assert any("06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/Trade_Payables_MSME_Ageing_Schedule.csv" in n for n in namelist)

    # SECTION 7: Payroll & Personnel
    assert any("07_PAYROLL_PERSONNEL_AND_LABOR_LAW_COMPLIANCE/Payroll_And_Personnel_Summary_FY2025-26.csv" in n for n in namelist)

    # SECTION 8: Audit Trail & Integrity Manifests
    assert any("08_AUDIT_TRAIL_AND_CRYPTOGRAPHIC_INTEGRITY/STATUTORY_CLOSE_AND_MCA_CHECKLIST.txt" in n for n in namelist)
    assert any("08_AUDIT_TRAIL_AND_CRYPTOGRAPHIC_INTEGRITY/MCA_Section_128_Audit_Trail_Certificate.txt" in n for n in namelist)
    assert any("08_AUDIT_TRAIL_AND_CRYPTOGRAPHIC_INTEGRITY/AUDIT_AUTHENTICITY_MANIFEST_SHA256.txt" in n for n in namelist)

    # Root Backward Compatibility
    assert "STATUTORY_CLOSE_AND_MCA_CHECKLIST.txt" in namelist
    assert "AUDIT_AUTHENTICITY_MANIFEST_SHA256.txt" in namelist

    # Cryptographic SHA-256 Manifest Verification
    manifest_content = zf.read("AUDIT_AUTHENTICITY_MANIFEST_SHA256.txt").decode("utf-8")
    assert "FINANCIAL YEAR: 2025-26" in manifest_content
    assert "PERIOD COVERED: 2025-04-01 to 2026-03-31" in manifest_content

    # Executive Briefing content validation
    briefing = zf.read("00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/01_Executive_Financial_And_Compliance_Briefing.txt").decode("utf-8")
    assert "Gross Outward Sales Turnover (Grand Total) : INR 11,800.00" in briefing
    assert "Total Inward Vendor Bills & Expenses       : INR 2,360.00" in briefing
    assert "Input Tax Credit (ITC) Eligible Claimed    : INR 360.00" in briefing
