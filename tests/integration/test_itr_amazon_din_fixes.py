import io
import uuid
import pytest
from datetime import date, datetime
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant, User, TenantUser
from app.models.expense import Expense
from app.services.bank_parser import validate_uploaded_document_safety
from app.services.bill_analyzer import StatutoryBillAnalyzer
from app.services.statutory_vault_engine import StatutoryVaultEngine
from app.services.onboarding_inspector import OnboardingInspectorService


@pytest.mark.asyncio
async def test_sec05_flexible_header_validation():
    """
    Verifies SEC-05 validator accepts:
    1. Standard PDF (%PDF-1.4)
    2. PDF preceded by UTF-8 BOM (\xef\xbb\xbf%PDF-1.4) - typical government ITR downloads
    3. PDF preceded by leading newlines/whitespace
    4. PDF with %PDF- header within first 1024 bytes
    5. ITR e-filing JSON files
    6. ITR XML export files
    """
    # 1. Standard PDF
    std_pdf = b"%PDF-1.4\n%trailer\n/Type /Catalog\n/Type /Page\n%%EOF"
    res1 = validate_uploaded_document_safety("ITR_6_2025.pdf", std_pdf, "application/pdf")
    assert res1["is_safe"] is True

    # 2. PDF with UTF-8 BOM
    bom_pdf = b"\xef\xbb\xbf%PDF-1.7\n%trailer\n/Type /Catalog\n/Type /Page\n%%EOF"
    res2 = validate_uploaded_document_safety("ITR_Ack_AY2025.pdf", bom_pdf, "application/pdf")
    assert res2["is_safe"] is True

    # 3. PDF with leading newlines and spaces
    whitespace_pdf = b"\r\n\r\n  %PDF-1.5\n%trailer\n/Type /Catalog\n/Type /Page\n%%EOF"
    res3 = validate_uploaded_document_safety("ITR_V_Filed.pdf", whitespace_pdf, "application/pdf")
    assert res3["is_safe"] is True

    # 4. PDF header within first 200 bytes
    offset_pdf = b"<!-- Income Tax Portal Export -->\r\n" * 3 + b"%PDF-1.4\n/Type /Page\n%%EOF"
    res4 = validate_uploaded_document_safety("ITR_Receipt.pdf", offset_pdf, "application/pdf")
    assert res4["is_safe"] is True

    # 5. ITR e-filing JSON
    itr_json = b'{"assessmentYear": "2025-26", "pan": "AABCA9603R", "itrType": "ITR-6", "totalIncome": 1250000}'
    res5 = validate_uploaded_document_safety("ITR6_AY2025-26.json", itr_json, "application/json")
    assert res5["is_safe"] is True

    # 6. ITR XML export
    itr_xml = b'<?xml version="1.0" encoding="UTF-8"?><ITR><ITR6><AssessmentYear>2025</AssessmentYear></ITR6></ITR>'
    res6 = validate_uploaded_document_safety("ITR_Export.xml", itr_xml, "application/xml")
    assert res6["is_safe"] is True


def test_amazon_merchant_name_extraction_ignores_signature_valid():
    """
    Verifies that Adobe digital signature blocks ("Signature valid", "Digitally signed by")
    are filtered out and the genuine merchant (Amazon / Seller) is correctly extracted.
    """
    # Sample Amazon invoice text with digital signature noise at top
    amazon_invoice_text = """
    Signature valid
    Digitally signed by DS APPARIO RETAIL PRIVATE LIMITED
    Date: 2025.10.26 14:22:10 IST
    Tax Invoice / Bill of Supply
    Sold By : Appario Retail Private Limited
    Billing Address:
    Aryix Innovations Private Limited
    Invoice Number: IN-2025-99128
    Invoice Date: 26.10.2025
    Description: High Back Ergonomic Office Chair
    HSN: 94013000
    Total Amount: 1,493.24
    """
    merchant = StatutoryBillAnalyzer._extract_merchant_name(amazon_invoice_text, "office chair 2.pdf")
    assert "Signature" not in merchant
    assert "valid" not in merchant.lower()
    assert "Appario" in merchant or "Amazon" in merchant

    # Sample invoice with only Amazon header and digital signature block
    amazon_generic_text = """
    Signature valid
    Digitally signed by Amazon Seller Services
    Tax Invoice
    Amazon.in
    Invoice Date: 26.10.2025
    Total: 1493.24
    """
    merchant2 = StatutoryBillAnalyzer._extract_merchant_name(amazon_generic_text, "office chair 1.pdf")
    assert "Signature" not in merchant2
    assert "Amazon" in merchant2


def test_din_approval_letter_extraction():
    """
    Verifies that the StatutoryVaultEngine accurately classifies and extracts:
    - Document Title: DIN Approval Letter (Form DIR-3 Allotment)
    - 8-digit Director Identification Number (DIN)
    - Full Director Legal Name
    - Father's Name and Allotment Date
    """
    mca_din_letter_text = """
    GOVERNMENT OF INDIA
    MINISTRY OF CORPORATE AFFAIRS
    OFFICE OF THE REGISTRAR OF COMPANIES / DIN CELL
    
    Subject: Allotment of Director Identification Number (DIN) under Companies Act, 2013
    
    Sir/Madam,
    With reference to your application in Form DIR-3, it is hereby informed that the
    Director Identification Number (DIN) has been allotted to you as per details given below:
    
    1. Director Identification Number (DIN) : 11249061
    2. Name of the Director : ADITHYA NAGARAJA KHAMITHKAR
    3. Father's Name : NAGARAJA KHAMITHKAR
    4. Date of Birth : 15/08/1990
    5. Date of Allotment : 12/04/2021
    6. Nationality : Indian
    
    Registrar of Companies
    """
    file_bytes = mca_din_letter_text.encode("utf-8")
    extracted = StatutoryVaultEngine.identify_and_extract(
        file_bytes=file_bytes,
        filename="DIN_Approval_Letter.pdf"
    )

    assert extracted["document_type"] == "din_approval"
    assert "DIN Approval Letter" in extracted["document_title"]
    fields = extracted["extracted_fields"]
    assert fields["din"] == "11249061"
    assert "Adithya" in fields["director_name"]
    assert "Khamithkar" in fields["director_name"]
    assert fields["din_verified"] is True

    # Test via OnboardingInspectorService
    inspect_res = OnboardingInspectorService.verify_statutory_document(
        file_bytes=file_bytes,
        filename="DIN_Approval_Letter.pdf",
        expected_doc_type="din_approval"
    )
    assert inspect_res["is_authentic"] is True
    assert inspect_res["extracted_entity"]["din"] == "11249061"
    assert "Adithya" in inspect_res["extracted_entity"]["director_name"]


@pytest.mark.asyncio
async def test_allow_multiple_expenses_same_receipt_hash():
    """
    Verifies that uploading 2 bills / expense records sharing the same receipt SHA-256
    (e.g., 2 office chairs from an Amazon order, or re-uploading an invoice)
    succeeds cleanly without throwing a PostgreSQL UniqueViolationError on uq_expense_receipt.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    shared_receipt_sha = "cc33403b12e0498fa9a823c78e718bdfb988180261d76186aa440c0259cd01d3"

    async with AsyncSessionLocal() as session:
        # Create temporary tenant with valid PAN format: 5 letters, 4 digits, 1 letter
        pan_num = str(uuid.uuid4().int)[:4]
        tenant = Tenant(
            id=tenant_id,
            legal_name="Chair Test Org Pvt Ltd",
            trade_name="Chair Test Org",
            pan=f"AABCU{pan_num}P",
            state_code="29",
            registered_office="123 MG Road, Bangalore, Karnataka, 560001"
        )
        user = User(
            id=user_id,
            email=f"chair_tester_{tenant_id.hex[:6]}@test.org",
            password_hash="test_hash",
            first_name="Adithya",
            last_name="Khamithkar",
            is_active=True
        )
        membership = TenantUser(
            tenant_id=tenant_id,
            user_id=user_id,
            role="company_owner"
        )
        session.add_all([tenant, user, membership])
        await session.flush()

        # Insert Expense 1 (Office Chair 1)
        exp1 = Expense(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            employee_id=user_id,
            merchant_name="Amazon Seller Services Private Limited",
            expense_date=date(2025, 10, 26),
            currency="INR",
            total_amount=Decimal("1493.24"),
            category="Office Equipment",
            receipt_s3_key=f"{tenant_id}/receipts/chair_1.pdf",
            receipt_sha256=shared_receipt_sha,
            paid_personally=True,
            director_name="Adithya Khamithkar",
            status="approved"
        )
        session.add(exp1)
        await session.commit()

        # Insert Expense 2 (Office Chair 2 - same receipt SHA-256)
        exp2 = Expense(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            employee_id=user_id,
            merchant_name="Amazon Seller Services Private Limited",
            expense_date=date(2025, 10, 26),
            currency="INR",
            total_amount=Decimal("1493.24"),
            category="Office Equipment",
            receipt_s3_key=f"{tenant_id}/receipts/chair_2.pdf",
            receipt_sha256=shared_receipt_sha,
            paid_personally=True,
            director_name="Adithya Khamithkar",
            status="approved"
        )
        session.add(exp2)
        # MUST COMMIT CLEANLY without duplicate key violation
        await session.commit()

        # Verify both expenses exist in DB for this tenant
        res = await session.execute(
            select(Expense).where(Expense.tenant_id == tenant_id, Expense.receipt_sha256 == shared_receipt_sha)
        )
        exps = res.scalars().all()
        assert len(exps) == 2

        # Clean up
        await session.execute(text(f"DELETE FROM expenses WHERE tenant_id = '{tenant_id}';"))
        await session.execute(text(f"DELETE FROM tenant_users WHERE tenant_id = '{tenant_id}';"))
        await session.execute(text(f"DELETE FROM tenants WHERE id = '{tenant_id}';"))
        await session.execute(text(f"DELETE FROM users WHERE id = '{user_id}';"))
        await session.commit()
