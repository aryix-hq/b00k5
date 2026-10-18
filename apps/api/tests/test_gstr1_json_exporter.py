import pytest
import uuid
import random
import string
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import select, and_, text

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.api.deps import get_db
from app.models.tenant import Tenant, User, TenantUser
from app.models.invoice import Invoice, InvoiceItem, Contact
from app.services.gstr1_export_service import GSTR1ExportService


test_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=False
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


@pytest.fixture(autouse=True)
def override_db():
    async def _get_db():
        async with TestAsyncSessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def db_session():
    async with TestAsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def gstr1_test_tenant(db_session: AsyncSession):
    """Provisions a test tenant with user and contacts."""
    uid = uuid.uuid4().hex[:6]
    pan = f"AABCG{random.randint(1000, 9999)}K"
    gstin = f"29{pan}1Z5"

    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name=f"GSTR1 Testing Enterprise {uid} Pvt Ltd",
        trade_name="GSTR1 Test",
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="456 Residency Road, Bangalore, Karnataka"
    )
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email=f"tax.{uid}@gstr1test.com",
        password_hash="mocked_pw_hash",
        first_name="Tax",
        last_name="Officer",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    tu = TenantUser(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        role="owner"
    )
    db_session.add(tu)
    await db_session.commit()
    await db_session.refresh(tenant)
    await db_session.refresh(user)

    return {"tenant": tenant, "user": user}


@pytest.mark.asyncio
async def test_gstr1_offline_json_export(db_session: AsyncSession, gstr1_test_tenant: dict):
    """
    Verifies that GSTR1ExportService produces official GSTN offline JSON with:
    - b2b registered customer invoices
    - b2cl inter-state unregistered > 2.5L
    - b2cs intra-state small invoices
    - Table 12 HSN outward summary
    - Table 13 Document issue summary
    """
    tenant = gstr1_test_tenant["tenant"]
    user = gstr1_test_tenant["user"]

    # 1. Registered Customer (B2B)
    c_b2b = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Infosys BPO Limited",
        is_customer=True,
        gstin="27AAACI4818R1ZP", # Maharashtra
        state_code="27",
        billing_address="Pune, Maharashtra"
    )
    db_session.add(c_b2b)

    # 2. Unregistered Large Customer (B2CL > 2.5L interstate)
    c_b2cl = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Dr. Arvind Swaminathan",
        is_customer=True,
        gstin=None,
        state_code="33", # Tamil Nadu (Interstate from 29)
        billing_address="Chennai, Tamil Nadu"
    )
    db_session.add(c_b2cl)

    # 3. Unregistered Small Customer (B2CS local)
    c_b2cs = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Local Retail Client",
        is_customer=True,
        gstin=None,
        state_code="29", # Karnataka (Intrastate)
        billing_address="Bangalore, Karnataka"
    )
    db_session.add(c_b2cs)
    await db_session.flush()

    # Create Invoice 1: B2B (Rs 1,00,000 + 18% IGST = Rs 1,18,000)
    inv1 = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        contact_id=c_b2b.id,
        invoice_number="INV-2026-B2B-001",
        type="tax_invoice",
        issue_date=date(2026, 9, 5),
        due_date=date(2026, 9, 20),
        place_of_supply="27",
        is_interstate=True,
        subtotal=Decimal("100000.00"),
        cgst_total=Decimal("0.00"),
        sgst_total=Decimal("0.00"),
        igst_total=Decimal("18000.00"),
        grand_total=Decimal("118000.00"),
        status="sent"
    )
    db_session.add(inv1)
    await db_session.flush()

    item1 = InvoiceItem(
        id=uuid.uuid4(),
        invoice_id=inv1.id,
        item_description="Enterprise ERP Platform License",
        hsn_sac_code="998313",
        quantity=Decimal("1.000"),
        unit_price=Decimal("100000.00"),
        taxable_value=Decimal("100000.00"),
        gst_rate_percent=Decimal("18.00"),
        cgst_amount=Decimal("0.00"),
        sgst_amount=Decimal("0.00"),
        igst_amount=Decimal("18000.00"),
        total_amount=Decimal("118000.00")
    )
    db_session.add(item1)

    # Create Invoice 2: B2CL (Rs 3,00,000 + 18% IGST = Rs 3,54,000 > 2.5L)
    inv2 = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        contact_id=c_b2cl.id,
        invoice_number="INV-2026-B2CL-002",
        type="tax_invoice",
        issue_date=date(2026, 9, 12),
        due_date=date(2026, 9, 25),
        place_of_supply="33",
        is_interstate=True,
        subtotal=Decimal("300000.00"),
        cgst_total=Decimal("0.00"),
        sgst_total=Decimal("0.00"),
        igst_total=Decimal("54000.00"),
        grand_total=Decimal("354000.00"),
        status="sent"
    )
    db_session.add(inv2)
    await db_session.flush()

    item2 = InvoiceItem(
        id=uuid.uuid4(),
        invoice_id=inv2.id,
        item_description="Architecture Advisory Consulting",
        hsn_sac_code="998311",
        quantity=Decimal("1.000"),
        unit_price=Decimal("300000.00"),
        taxable_value=Decimal("300000.00"),
        gst_rate_percent=Decimal("18.00"),
        cgst_amount=Decimal("0.00"),
        sgst_amount=Decimal("0.00"),
        igst_amount=Decimal("54000.00"),
        total_amount=Decimal("354000.00")
    )
    db_session.add(item2)

    # Create Invoice 3: B2CS (Rs 50,000 + 9% CGST + 9% SGST = Rs 59,000)
    inv3 = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        contact_id=c_b2cs.id,
        invoice_number="INV-2026-B2CS-003",
        type="tax_invoice",
        issue_date=date(2026, 9, 20),
        due_date=date(2026, 9, 30),
        place_of_supply="29",
        is_interstate=False,
        subtotal=Decimal("50000.00"),
        cgst_total=Decimal("4500.00"),
        sgst_total=Decimal("4500.00"),
        igst_total=Decimal("0.00"),
        grand_total=Decimal("59000.00"),
        status="paid"
    )
    db_session.add(inv3)
    await db_session.flush()

    item3 = InvoiceItem(
        id=uuid.uuid4(),
        invoice_id=inv3.id,
        item_description="Local Software Maintenance",
        hsn_sac_code="998314",
        quantity=Decimal("1.000"),
        unit_price=Decimal("50000.00"),
        taxable_value=Decimal("50000.00"),
        gst_rate_percent=Decimal("18.00"),
        cgst_amount=Decimal("4500.00"),
        sgst_amount=Decimal("4500.00"),
        igst_amount=Decimal("0.00"),
        total_amount=Decimal("59000.00")
    )
    db_session.add(item3)
    await db_session.commit()

    # 4. Generate GSTR-1 JSON via Service
    payload = await GSTR1ExportService.generate_gstr1_json(
        session=db_session,
        tenant_id=tenant.id,
        year=2026,
        month=9
    )

    assert payload["gstin"] == tenant.gstin
    assert payload["fp"] == "092026"
    assert payload["version"] == "GSTR1_1.0"

    # Verify B2B Table
    assert len(payload["b2b"]) == 1
    assert payload["b2b"][0]["ctin"] == "27AAACI4818R1ZP"
    assert payload["b2b"][0]["inv"][0]["inum"] == "INV-2026-B2B-001"
    assert payload["b2b"][0]["inv"][0]["val"] == 118000.0

    # Verify B2CL Table
    assert len(payload["b2cl"]) == 1
    assert payload["b2cl"][0]["pos"] == "33"
    assert payload["b2cl"][0]["inv"][0]["inum"] == "INV-2026-B2CL-002"
    assert payload["b2cl"][0]["inv"][0]["val"] == 354000.0

    # Verify B2CS Table
    assert len(payload["b2cs"]) == 1
    assert payload["b2cs"][0]["sply_ty"] == "INTRA"
    assert payload["b2cs"][0]["pos"] == "29"
    assert payload["b2cs"][0]["camt"] == 4500.0
    assert payload["b2cs"][0]["samt"] == 4500.0

    # Verify HSN Table 12
    hsn_codes = [h["hsn_sc"] for h in payload["hsn"]["data"]]
    assert "998313" in hsn_codes
    assert "998311" in hsn_codes
    assert "998314" in hsn_codes

    # Verify Document Issue Table 13
    assert payload["doc_issue"]["doc_det"][0]["docs"][0]["totnum"] == 3
    assert payload["doc_issue"]["doc_det"][0]["docs"][0]["canc"] == 0

    # 5. Verify REST API Endpoint
    token = create_access_token({"sub": str(user.id), "tenant_id": str(tenant.id)})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/invoices/export/gstr-1?year=2026&month=9", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["fp"] == "092026"
        assert len(data["b2b"]) == 1
        assert "attachment" in resp.headers["content-disposition"]
        assert f"GSTR1_{tenant.gstin}_092026.json" in resp.headers["content-disposition"]

