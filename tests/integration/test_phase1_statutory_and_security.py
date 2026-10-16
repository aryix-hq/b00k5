import pytest
import io
import uuid
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant, User, TenantUser
from app.services.bank_parser import validate_uploaded_document_safety
from app.api.v1.ledger import get_current_indian_fy

DATABASE_URL = settings.DATABASE_URL


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def test_def16_encrypted_government_pdf_allowed_and_launch_blocked():
    """
    DEF-16 Verification:
    - Encrypted government PDF (containing /Encrypt and /JavaScript without plaintext keywords)
      MUST pass SEC-05 safety validation.
    - Any PDF with /Launch MUST still be rejected unconditionally.
    """
    # 1. Encrypted government PDF with cipher stream and Adobe /JavaScript
    # Simulates password-protected ITR-V or SBI/HDFC statement
    encrypted_gov_pdf = (
        b"%PDF-1.6\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Pages 2 0 R /Encrypt 3 0 R /AcroForm 4 0 R >>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Filter /Standard /V 5 /R 6 /Length 256 /O <a1b2c3d4> /U <e5f6g7h8> >>\n"
        b"endobj\n"
        b"4 0 obj\n"
        b"<< /Fields [] /JS (app.calculateNow()) /S /JavaScript >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages /Count 1 /Kids [5 0 R] >>\n"
        b"endobj\n"
        b"5 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R >>\n"
        b"endobj\n"
        b"trailer\n"
        b"<< /Root 1 0 R /Encrypt 3 0 R >>\n"
        b"%%EOF"
    )

    # Filename does not contain "itr" — relies on /Encrypt and PDF structure
    res = validate_uploaded_document_safety("Statutory_Filing_2026.pdf", encrypted_gov_pdf, "application/pdf")
    assert res["is_safe"] is True, f"Failed on encrypted PDF: {res.get('reason')}"
    assert res["safe"] is True

    # 2. Malicious encrypted PDF with /Launch must STILL be blocked
    malicious_launch_pdf = (
        b"%PDF-1.6\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Encrypt 2 0 R /OpenAction << /S /Launch /F (cmd.exe) >> >>\n"
        b"endobj\n"
        b"%%EOF"
    )
    res_mal = validate_uploaded_document_safety("Malicious_Filing.pdf", malicious_launch_pdf, "application/pdf")
    assert res_mal["is_safe"] is False
    assert "/Launch" in res_mal["reason"]


def test_def18_dynamic_current_indian_fy():
    """
    DEF-18 Verification:
    Dynamic calculation of Indian Financial Year must match current date.
    For October 2026, it must return '2026-27'.
    """
    cur_fy = get_current_indian_fy()
    today = date.today()
    expected_start = today.year if today.month >= 4 else today.year - 1
    expected_fy = f"{expected_start}-{str(expected_start + 1)[-2:]}"
    assert cur_fy == expected_fy


@pytest.mark.asyncio
async def test_def18_fiscal_years_api_endpoint(db_session: AsyncSession):
    """
    DEF-18 Verification:
    GET /api/v1/ledger/fiscal-years must return the dynamically calculated active year
    and recent available years.
    """
    t_id = uuid.uuid4()
    u_id = uuid.uuid4()
    rand_sfx = uuid.uuid4().hex[:6].upper()
    tenant = Tenant(
        id=t_id,
        legal_name=f"Phase1 Audit Dynamics Ltd {rand_sfx}",
        trade_name=f"Phase1 Ltd {rand_sfx}",
        cin=f"U72900KA2026PTC{rand_sfx}",
        pan=f"ABCDE{rand_sfx[:4]}F",
        gstin=f"29ABCDE{rand_sfx[:4]}F1Z5",
        state_code="29",
        registered_office="123 Tech Park, Bengaluru, Karnataka 560001"
    )
    user = User(
        id=u_id,
        email=f"auditor_{rand_sfx.lower()}@phase1.in",
        first_name="Auditor",
        last_name="Test",
        password_hash="hashed_test_password"
    )
    membership = TenantUser(
        tenant_id=t_id,
        user_id=u_id,
        role="owner"
    )
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(membership)
    await db_session.commit()

    token = create_access_token({"sub": str(u_id), "tenant_id": str(t_id), "role": "owner"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            "/api/v1/ledger/fiscal-years",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(t_id)}
        )
        assert res.status_code == 200
        data = res.json()
        expected_fy = get_current_indian_fy()
        assert data["current_active_year"] == expected_fy
        avail = [y["fiscal_year"] for y in data["available_years"]]
        assert expected_fy in avail
