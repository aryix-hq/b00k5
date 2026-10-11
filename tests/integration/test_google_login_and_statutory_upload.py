import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.main import app
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.tenant import Tenant, User, TenantUser
from app.services.onboarding_inspector import OnboardingInspectorService

DATABASE_URL = settings.DATABASE_URL

from app.core.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_google_login_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Successful Google Login with valid email & name
        resp = await client.post("/api/v1/auth/google/login", json={
            "email": "director@acme.corp",
            "name": "Vikram Sharma",
            "id_token": "google_oauth_token_simulated_xyz789"
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == "director@acme.corp"
        assert data["user_id"] is not None
        assert data["role"] is not None
        
        # Verify decoded JWT
        payload = decode_access_token(data["access_token"])
        assert payload is not None
        assert payload.get("sub") == data["user_id"]
        assert payload.get("email") == "director@acme.corp"

        # 2. Re-login with same email logs into existing user and tenant
        resp2 = await client.post("/api/v1/auth/google/login", json={
            "email": "director@acme.corp",
            "name": "Vikram Sharma",
            "id_token": "google_oauth_token_simulated_xyz789"
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["user_id"] == data["user_id"]
        assert data2["tenant_id"] == data["tenant_id"]

        # 3. Validation failure when email is invalid or missing @
        resp_invalid = await client.post("/api/v1/auth/google/login", json={
            "email": "invalid_email_format",
            "name": "Invalid User"
        })
        assert resp_invalid.status_code in [400, 422]

@pytest.mark.asyncio
async def test_statutory_verification_moa_aoa_tan_gst():
    inspector = OnboardingInspectorService()

    # 1. MOA Verification & Extraction
    moa_bytes = b"""
    %PDF-1.4
    MEMORANDUM OF ASSOCIATION OF ZENITH TECHNOLOGIES PRIVATE LIMITED
    Clause III: The objects to be pursued by the company on its incorporation are software development and cloud hosting.
    Clause V: The Authorized Share Capital of the Company is Rs. 15,00,000/- (Rupees Fifteen Lakhs only) 
    divided into 1,50,000 (One Lakh Fifty Thousand) Equity Shares of Rs. 10/- (Rupees Ten) each.
    """
    res_moa = inspector.verify_statutory_document(
        file_bytes=moa_bytes,
        filename="MOA_Zenith.pdf",
        expected_doc_type="moa"
    )
    assert res_moa["is_authentic"] is True
    assert res_moa["extracted_data"]["authorized_capital_inr"] == 1500000.0
    assert res_moa["extracted_data"]["total_equity_shares"] == 150000
    assert res_moa["extracted_data"]["face_value_inr"] == 10.0
    assert "software development" in res_moa["extracted_data"]["main_objects"]

    # 2. AOA Verification & Extraction
    aoa_bytes = b"""
    %PDF-1.4
    ARTICLES OF ASSOCIATION OF ZENITH TECHNOLOGIES PRIVATE LIMITED
    Section 174: The quorum for a meeting of the Board of Directors shall be one-third of its total strength or two directors, 
    whichever is higher. Minimum 2 directors present throughout.
    Borrowing powers: The Board may borrow moneys not exceeding aggregate of paid-up capital and free reserves.
    """
    res_aoa = inspector.verify_statutory_document(
        file_bytes=aoa_bytes,
        filename="AOA_Zenith.pdf",
        expected_doc_type="aoa"
    )
    assert res_aoa["is_authentic"] is True
    assert res_aoa["extracted_data"]["board_meeting_quorum"] == 2
    assert "paid-up capital" in res_aoa["extracted_data"]["borrowing_power_clause"]

    # 3. TAN Verification & Extraction
    tan_bytes = b"""
    %PDF-1.4
    INCOME TAX DEPARTMENT - ALLOTMENT LETTER FOR TAX DEDUCTION ACCOUNT NUMBER (TAN)
    Government of India, Ministry of Finance, Central Board of Direct Taxes.
    This is to certify that Tax Deduction Account Number BLRK12345F has been allotted to ZENITH TECHNOLOGIES PVT LTD.
    TAN: BLRK12345F
    """
    res_tan = inspector.verify_statutory_document(
        file_bytes=tan_bytes,
        filename="TAN_Allotment.pdf",
        expected_doc_type="tan"
    )
    assert res_tan["is_authentic"] is True
    assert res_tan["extracted_data"]["tan"] == "BLRK12345F"
    assert res_tan["extracted_data"]["status"] == "ALLOTTED"

    # 4. GST REG-06 Verification & Extraction
    gst_bytes = b"""
    %PDF-1.4
    Government of India - Form GST REG-06
    Registration Certificate issued under Central Goods and Services Tax Act, 2017
    Registration Number (GSTIN): 29AABCK9012F1Z5
    Legal Name: ZENITH TECHNOLOGIES PRIVATE LIMITED
    Trade Name: ZENITH TECHNOLOGIES
    State: Karnataka
    """
    res_gst = inspector.verify_statutory_document(
        file_bytes=gst_bytes,
        filename="GST_REG_06.pdf",
        expected_doc_type="gst_reg06"
    )
    assert res_gst["is_authentic"] is True
    assert res_gst["extracted_data"]["gstin"] == "29AABCK9012F1Z5"
    assert res_gst["extracted_data"]["state_code"] == "29"
    assert "ZENITH" in res_gst["extracted_data"]["legal_name"]

@pytest.mark.asyncio
async def test_statutory_document_first_governance():
    async with AsyncSessionLocal() as db_session:
        tenant_id = uuid.uuid4()
        # New tenant initialized without GSTIN or TAN
        tenant = Tenant(
            id=tenant_id,
            legal_name="Zenith Digital Systems Private Limited",
            trade_name="Zenith",
            cin=f"U72900KA2025PTC{tenant_id.hex[:6].upper()}",
            pan=f"AABCA{tenant_id.hex[:4].upper()}F",
            gstin=None,  # No GSTIN uploaded yet
            state_code="29",
            registered_office="Indiranagar, Bengaluru, Karnataka 560038",
            statutory_profile={}  # No TAN uploaded yet
        )
        db_session.add(tenant)
        await db_session.commit()

        # Verify initial state: GSTIN is None, TAN is None
        fetched = await db_session.get(Tenant, tenant_id)
        assert fetched.gstin is None
        assert fetched.statutory_profile.get("tan") is None

        # Now verify that setting GSTIN and TAN requires authentic verification
        inspector = OnboardingInspectorService()
        pan_digits = f"{tenant_id.int % 9000 + 1000:04d}"
        tan_digits = f"{tenant_id.int % 90000 + 10000:05d}"
        dynamic_pan = f"AABCA{pan_digits}F"
        dynamic_gstin = f"29{dynamic_pan}1Z2"
        dynamic_tan = f"BLRA{tan_digits}A"

        gst_bytes = f"""
        Form GST REG-06 Registration Certificate
        GSTIN: {dynamic_gstin}
        Legal Name: ZENITH DIGITAL SYSTEMS PRIVATE LIMITED
        """.encode('utf-8')
        res_gst = inspector.verify_statutory_document(
            file_bytes=gst_bytes,
            filename="GST_REG06.pdf",
            expected_doc_type="gst_reg06"
        )
        assert res_gst["is_authentic"] is True
        
        tan_bytes = f"""
        FORM 49B - TAN ALLOTMENT LETTER - CBDT
        TAN Number: {dynamic_tan}
        Name: ZENITH DIGITAL SYSTEMS PRIVATE LIMITED
        """.encode('utf-8')
        res_tan = inspector.verify_statutory_document(
            file_bytes=tan_bytes,
            filename="TAN_Certificate.pdf",
            expected_doc_type="tan"
        )
        assert res_tan["is_authentic"] is True

        # Update tenant profile using verified extraction only
        fetched.gstin = res_gst["extracted_data"]["gstin"]
        profile = dict(fetched.statutory_profile or {})
        profile["tan"] = res_tan["extracted_data"]["tan"]
        fetched.statutory_profile = profile
        await db_session.commit()

        # Verify updated state has properly bound verified credentials
        updated = await db_session.get(Tenant, tenant_id)
        assert updated.gstin == dynamic_gstin
        assert updated.statutory_profile["tan"] == dynamic_tan
