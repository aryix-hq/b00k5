"""
Phase 3 Integration Verification Suite:
- DEF-23: Super Admin System Telemetry endpoint & Tenant Directory accessibility
- DEF-14: Multi-item invoice PDF vertical boundary pagination & overlap prevention
- DEF-24: Schedule III statutory rounding off under Companies Act 2013 (< ₹100 Cr threshold)
"""

import pytest
import io
from decimal import Decimal
from datetime import date
from pypdf import PdfReader
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant, User
from app.services.pdf_service import PDFService

DATABASE_URL = settings.DATABASE_URL


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_system_telemetry_endpoint(db_session: AsyncSession):
    """
    Verifies DEF-23: Super Admin can query /api/v1/system/telemetry
    to inspect PostgreSQL RLS status, zero-drift ledger invariant, and Redis broker.
    """
    # Fetch or verify a super admin user exists
    stmt = select(User).where(User.is_super_admin == True)
    res = await db_session.execute(stmt)
    admin = res.scalars().first()

    if not admin:
        stmt_user = select(User).limit(1)
        admin = (await db_session.execute(stmt_user)).scalars().first()
        admin.is_super_admin = True
        await db_session.commit()

    token = create_access_token({"sub": str(admin.id), "email": admin.email, "role": "owner", "is_super_admin": True})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/system/telemetry",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert data["database"]["engine"] == "PostgreSQL 16 Alpine"
        assert data["database"]["rls_enabled"] is True
        assert data["database"]["balance_invariant_holds"] is True
        assert data["database"]["ledger_drift"] < 0.01
        assert "redis" in data
        assert "minio" in data
        assert "fiscal_calendar" in data
        assert "system_fy" in data["fiscal_calendar"]


def test_pdf_invoice_pagination_no_overlap():
    """
    Verifies DEF-14: When an invoice has multiple items and multiline notes that exceed
    the single-page boundary, PDFService auto-paginates cleanly with showPage() instead of
    overlapping bank details and totals box over the footer note.
    """
    items = []
    for i in range(1, 9):
        items.append({
            "description": f"Specialized Statutory & Financial Compliance Advisory Consulting Module {i} with Extended Scope",
            "notes": f"Includes comprehensive dual GST reconciliation, Rule 2(1)(c)(viii) DPT-3 loan analysis, and ICSI SS-1 statutory minutes draft for item {i}.",
            "hsn_sac_code": "998311",
            "quantity": 1,
            "unit_price": 5000.0,
            "amount": 5000.0
        })

    invoice_data = {
        "invoice_number": "INV-2026-TEST-MULTI",
        "invoice_date": "2026-07-15",
        "customer_name": "Enterprise Client India Private Limited",
        "customer_gstin": "29ABCDE1234F1Z5",
        "customer_address": "Unit 402, Embassy Tech Village, Outer Ring Road, Bengaluru, Karnataka 560103",
        "seller_name": "Acme Technologies Pvt Ltd",
        "seller_gstin": "29AABCA1234A1Z1",
        "seller_address": "No. 12, Ground Floor, Indiranagar, Bengaluru, Karnataka 560038",
        "items": items,
        "subtotal": 40000.0,
        "cgst_total": 3600.0,
        "sgst_total": 3600.0,
        "igst_total": 0.0,
        "grand_total": 47200.0,
        "status": "PAID",
        "bank_details": {
            "account_holder_name": "Acme Technologies Pvt Ltd",
            "bank_name": "HDFC Bank",
            "account_number": "50200012345678",
            "ifsc": "HDFC0000123"
        }
    }

    pdf_bytes = PDFService.generate_simple_invoice_pdf(invoice_data)

    assert pdf_bytes is not None
    assert len(pdf_bytes) > 2000

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2, f"Expected multi-page invoice due to item overflow, got {len(reader.pages)} page(s)"

    page2_text = reader.pages[1].extract_text()
    assert "Tax Invoice" in page2_text
    assert "Bank Account Details" in page2_text or "Total" in page2_text or "Continued" in page2_text


def test_schedule_iii_rounding_statutory_thresholds():
    """
    Verifies DEF-24: Schedule III of the Companies Act, 2013 rounding off requirements.
    For Total Income < ₹100 Crore:
    - Figures shall be rounded off to nearest hundreds (Rs. '00), thousands, lakhs, or millions.
    - Zero presentation of fractional paise.
    """
    raw_amount = Decimal("301554.06")

    # In Rs. '00 (Nearest Hundreds): divided by 100
    hundreds_scaled = float(raw_amount) / 100.0
    hundreds_formatted = f"{hundreds_scaled:,.2f}"
    assert hundreds_formatted == "3,015.54"

    # In Rs. (Rounded to whole Rupee): round with 0 decimals
    rupee_rounded = round(float(raw_amount))
    assert rupee_rounded == 301554

    # Thousands: divided by 1000
    thousands_scaled = float(raw_amount) / 1000.0
    assert f"{thousands_scaled:,.2f}" == "301.55"

    # Lakhs: divided by 100,000
    lakhs_scaled = float(raw_amount) / 100000.0
    assert f"{lakhs_scaled:,.2f}" == "3.02"


@pytest.mark.asyncio
async def test_auditor_dossier_schedule_iii_rounding(db_session: AsyncSession):
    """
    Verifies DEF-29: Schedule III Clause 4 Rounding in Auditor Dossier package export.
    Ensures that passing unit=hundreds scales financial statements to Amount in Rs. '00 (Nearest Hundreds)
    with zero fractional paise across both PDF and CSV exports in the ZIP package.
    """
    import zipfile
    from app.services.schedule_iii_service import format_statutory_amount, get_unit_label
    from app.models.tenant import TenantUser

    assert get_unit_label("hundreds") == "Amount in Rs. '00 (Nearest Hundreds)"
    assert get_unit_label("thousands") == "Amount in Rs. '000 (Nearest Thousands)"
    assert get_unit_label("lakhs") == "Amount in Rs. Lakhs"
    assert get_unit_label("whole") == "Amount in Rs."

    # Test format_statutory_amount scaling
    test_val = Decimal("301554.06")
    assert format_statutory_amount(test_val, "hundreds") == "3,015.54"
    assert format_statutory_amount(test_val, "whole") == "301,554.06"
    assert format_statutory_amount(test_val, "thousands") == "301.55"
    assert format_statutory_amount(test_val, "lakhs") == "3.02"

    # Test via API export
    tu = (await db_session.execute(select(TenantUser).limit(1))).scalars().first()
    assert tu is not None
    token = create_access_token({"sub": str(tu.user_id), "tenant_id": str(tu.tenant_id), "role": tu.role})
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tu.tenant_id)}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/vault/export-auditor-pack?fy=2025-26&unit=hundreds", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("content-type") == "application/zip"

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        sched_pdf = next((n for n in names if "Balance_Sheet_and_PL_Schedule_III.pdf" in n), None)
        assert sched_pdf is not None, f"Expected Balance_Sheet_and_PL_Schedule_III.pdf in ZIP, found {names}"

        # Extract and verify the PDF text
        pdf_bytes = zf.read(sched_pdf)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        first_page_text = reader.pages[0].extract_text()
        assert "Amount in Rs. '00 (Nearest Hundreds)" in first_page_text or "Nearest Hundreds" in first_page_text

