import pytest
import uuid
import random
import string
from decimal import Decimal
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import select, and_, text

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.api.deps import get_db
from app.models.tenant import Tenant, User, TenantUser
from app.models.payroll import Contractor, ContractorPayment
from app.models.ledger import JournalEntry, JournalLine
from app.schemas.payroll import ContractorCreate, ContractorPaymentCreate
from app.services.payroll_service import PayrollService, round_curr


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
async def contractor_test_tenant(db_session: AsyncSession):
    """Provisions an isolated Private Limited company tenant with seeded COA."""
    uid = uuid.uuid4().hex[:6]
    rand_alpha = ''.join(random.choices(string.ascii_uppercase, k=4))
    pan = f"A{rand_alpha}{random.randint(1000, 9999)}{random.choice(string.ascii_uppercase)}"
    gstin = f"29{pan}1Z5"
    cin = f"U72200KA2026PTC{random.randint(100000, 999999)}"

    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name=f"Contractor & Tech Services Pvt Ltd {uid}",
        trade_name="ContractorServices",
        cin=cin,
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="Koramangala, Bengaluru, Karnataka 560034",
        statutory_profile={
            "entity_type": "Private Limited Company",
            "tan": f"BLR{pan[:5]}01"
        }
    )
    db_session.add(tenant)

    user = User(
        id=uuid.uuid4(),
        email=f"founder_{uid}@contractors.in",
        first_name="Vikram",
        last_name="Reddy",
        password_hash="mock_secret_hash",
        is_active=True
    )
    db_session.add(user)

    tu = TenantUser(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        role="owner"
    )
    db_session.add(tu)
    await db_session.flush()

    await db_session.execute(text(f"SELECT seed_tenant_chart_of_accounts('{tenant.id}')"))
    await db_session.commit()

    tenant._test_user = user
    return tenant


@pytest.mark.asyncio
async def test_contractor_onboarding_and_tds_calculation(contractor_test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies contractor onboarding and automated statutory TDS calculation:
    - Section 194C (Individual @ 1%, Company @ 2%)
    - Section 194J_TECH (2%)
    - Section 194J_PROF (10%)
    - CBDT Circular 23/2017: TDS is deducted on base value excluding GST
    """
    tenant = contractor_test_tenant

    # 1. Onboard Individual Contractor u/s 194C
    c1_data = ContractorCreate(
        contractor_code="CON-194C-01",
        name="Ramesh Construction Services",
        contractor_type="individual_huf",
        pan_number="ABCDE1234F",
        tds_section="194C",
        tds_rate=Decimal("1.00"),
        email="ramesh@example.com",
        phone="9876543210",
        bank_name="HDFC Bank",
        bank_account_number="50100234567890",
        bank_ifsc_code="HDFC0001234"
    )
    c1 = await PayrollService.onboard_contractor(db_session, tenant.id, c1_data)
    assert c1.id is not None
    assert c1.contractor_code == "CON-194C-01"
    assert c1.tds_rate == Decimal("1.00")

    # 2. Onboard Professional Consultant u/s 194J_PROF
    c2_data = ContractorCreate(
        contractor_code="CON-194J-01",
        name="Sharma & Associates Legal Counsel",
        contractor_type="individual_huf",
        pan_number="ABCPD9876K",
        tds_section="194J_PROF",
        tds_rate=Decimal("10.00"),
        email="sharma@law.com",
        phone="9876500000",
        bank_name="ICICI Bank",
        bank_account_number="001105009876",
        bank_ifsc_code="ICIC0000011"
    )
    c2 = await PayrollService.onboard_contractor(db_session, tenant.id, c2_data)
    assert c2.id is not None
    assert c2.tds_section == "194J_PROF"

    # 3. Create Payment for 194C: Gross ₹1,00,000 + 18% GST (₹18,000). TDS 1% = ₹1,000. Net Payable = ₹1,17,000.
    p1_data = ContractorPaymentCreate(
        contractor_id=c1.id,
        invoice_number="INV-2026-001",
        invoice_date=date(2026, 10, 1),
        payment_date=date(2026, 10, 5),
        description="Office civil maintenance and repairs",
        gross_amount=Decimal("100000.00"),
        gst_rate=Decimal("18.00"),
        gst_amount=Decimal("18000.00")
    )
    p1 = await PayrollService.create_contractor_payment(db_session, tenant.id, p1_data)
    assert p1.tds_amount == Decimal("1000.00")
    assert p1.net_payable == Decimal("117000.00")

    # 4. Create Payment for 194J: Gross ₹50,000. No GST. TDS 10% = ₹5,000. Net Payable = ₹45,000.
    p2_data = ContractorPaymentCreate(
        contractor_id=c2.id,
        invoice_number="LEGAL-OCT-26",
        invoice_date=date(2026, 10, 10),
        payment_date=date(2026, 10, 12),
        description="Retainer for corporate advisory & trademark filing",
        gross_amount=Decimal("50000.00"),
        gst_rate=Decimal("0.00")
    )
    p2 = await PayrollService.create_contractor_payment(db_session, tenant.id, p2_data)
    assert p2.tds_amount == Decimal("5000.00")
    assert p2.net_payable == Decimal("45000.00")


@pytest.mark.asyncio
async def test_contractor_ledger_posting_and_form_16a(contractor_test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies full lifecycle of contractor payment:
    - Leg 1 Accrual journal entry (Debit Expense + GST, Credit TDS + Payables)
    - Leg 2 Disbursement journal entry (Debit Payables, Credit Bank)
    - Form 16A calculations and certified ReportLab PDF generation
    """
    tenant = contractor_test_tenant
    user = tenant._test_user

    # Onboard Tech Freelancer
    c_data = ContractorCreate(
        contractor_code="DEV-FREELANCE-01",
        name="Aditi Rao DevOps Consulting",
        contractor_type="individual_huf",
        pan_number="ABCPD5555L",
        tds_section="194J_TECH",
        tds_rate=Decimal("2.00"),
        email="aditi.dev@example.com",
        phone="9988776655",
        bank_name="State Bank of India",
        bank_account_number="30291827364",
        bank_ifsc_code="SBIN0000456"
    )
    c = await PayrollService.onboard_contractor(db_session, tenant.id, c_data)

    # Create Invoice: ₹80,000 + 18% GST (₹14,400). TDS 2% = ₹1,600. Net Payable = ₹92,800.
    pay_data = ContractorPaymentCreate(
        contractor_id=c.id,
        invoice_number="ADITI-INV-101",
        invoice_date=date(2026, 10, 15),
        payment_date=date(2026, 10, 18),
        description="Kubernetes cluster hardening and CI/CD automation",
        gross_amount=Decimal("80000.00"),
        gst_rate=Decimal("18.00"),
        gst_amount=Decimal("14400.00")
    )
    payment = await PayrollService.create_contractor_payment(db_session, tenant.id, pay_data)

    # Leg 1 Accrual
    accrued_payment = await PayrollService.accrue_contractor_payment(db_session, tenant.id, payment.id, user.id)
    assert accrued_payment.status == "approved"
    assert accrued_payment.accrual_journal_id is not None

    # Verify Leg 1 Journal Lines
    entry1 = await db_session.get(JournalEntry, accrued_payment.accrual_journal_id)
    assert entry1 is not None
    stmt_lines1 = select(JournalLine).where(JournalLine.journal_entry_id == entry1.id)
    lines1 = list((await db_session.execute(stmt_lines1)).scalars().all())
    tot_dr1 = sum(l.debit_amount for l in lines1)
    tot_cr1 = sum(l.credit_amount for l in lines1)
    assert tot_dr1 == tot_cr1 == Decimal("94400.00")  # 80000 gross + 14400 GST = 1600 TDS + 92800 Payable

    # Leg 2 Disbursement
    disbursed_payment = await PayrollService.disburse_contractor_payment(
        db_session, tenant.id, payment.id, user.id, utr="HDFCR9202610180001"
    )
    assert disbursed_payment.status == "disbursed"
    assert disbursed_payment.disbursement_journal_id is not None
    assert disbursed_payment.payout_utr == "HDFCR9202610180001"

    # Verify Leg 2 Journal Lines
    entry2 = await db_session.get(JournalEntry, disbursed_payment.disbursement_journal_id)
    assert entry2 is not None
    stmt_lines2 = select(JournalLine).where(JournalLine.journal_entry_id == entry2.id)
    lines2 = list((await db_session.execute(stmt_lines2)).scalars().all())
    tot_dr2 = sum(l.debit_amount for l in lines2)
    tot_cr2 = sum(l.credit_amount for l in lines2)
    assert tot_dr2 == tot_cr2 == Decimal("92800.00")

    # Form 16A Computation
    form16a = await PayrollService.calculate_form_16a(db_session, c.id, "2026-27")
    assert form16a["contractor_pan"] == "ABCPD5555L"
    assert form16a["total_gross_amount"] == 80000.00
    assert form16a["total_tds_deducted"] == 1600.00
    assert len(form16a["payments_breakdown"]) == 1

    # Form 16A Certified PDF Generation
    pdf_bytes = await PayrollService.generate_form_16a_pdf_for_contractor(db_session, c.id, "2026-27")
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_contractor_rest_api_e2e(contractor_test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies full end-to-end HTTP REST API flow for Contractors:
    1. POST /api/v1/payroll/contractors -> Onboard contractor
    2. GET /api/v1/payroll/contractors -> List contractors
    3. POST /api/v1/payroll/contractor-payments -> Create payment claim
    4. GET /api/v1/payroll/contractor-payments -> List payments
    5. POST /api/v1/payroll/contractor-payments/{id}/accrue -> Leg 1 accrual voucher
    6. POST /api/v1/payroll/contractor-payments/{id}/disburse -> Leg 2 disbursement voucher
    7. GET /api/v1/payroll/contractors/{id}/form-16a -> JSON Form 16A data
    8. GET /api/v1/payroll/contractors/{id}/form-16a/pdf -> Certified PDF download
    """
    tenant = contractor_test_tenant
    user = tenant._test_user

    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "tenant_id": str(tenant.id),
            "role": "owner"
        }
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(tenant.id)
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Onboard Contractor
        res1 = await client.post(
            "/api/v1/payroll/contractors",
            json={
                "contractor_code": "CON-API-01",
                "name": "Acme IT Solutions LLP",
                "contractor_type": "company_firm",
                "pan_number": "AABCA9999C",
                "gstin": "29AABCA9999C1Z5",
                "tds_section": "194C",
                "tds_rate": 2.00,
                "email": "finance@acmeit.com",
                "phone": "9800011122",
                "address": "Electronic City, Bangalore",
                "bank_name": "Axis Bank",
                "bank_account_number": "91201004567890",
                "bank_ifsc_code": "UTIB0000123"
            },
            headers=headers
        )
        assert res1.status_code == 201, res1.text
        c_data = res1.json()
        contractor_id = c_data["id"]
        assert c_data["contractor_code"] == "CON-API-01"

        # 2. List Contractors
        res2 = await client.get("/api/v1/payroll/contractors", headers=headers)
        assert res2.status_code == 200
        assert any(c["id"] == contractor_id for c in res2.json())

        # 3. Create Payment Claim: ₹2,00,000 + 18% GST (₹36,000). TDS 2% = ₹4,000. Net Payable = ₹2,32,000.
        res3 = await client.post(
            "/api/v1/payroll/contractor-payments",
            json={
                "contractor_id": contractor_id,
                "invoice_number": "ACME-OCT-001",
                "invoice_date": "2026-10-10",
                "payment_date": "2026-10-15",
                "description": "Enterprise cloud security review and penetration testing",
                "gross_amount": 200000.00,
                "gst_rate": 18.00,
                "gst_amount": 36000.00,
                "tds_section": "194C",
                "tds_rate": 2.00
            },
            headers=headers
        )
        assert res3.status_code == 201, res3.text
        pay_data = res3.json()
        payment_id = pay_data["id"]
        assert float(pay_data["tds_amount"]) == 4000.00
        assert float(pay_data["net_payable"]) == 232000.00

        # 4. List Payments
        res4 = await client.get("/api/v1/payroll/contractor-payments", headers=headers)
        assert res4.status_code == 200
        assert any(p["id"] == payment_id for p in res4.json())

        # 5. Leg 1 Accrue
        res5 = await client.post(f"/api/v1/payroll/contractor-payments/{payment_id}/accrue", headers=headers)
        assert res5.status_code == 200
        assert res5.json()["status"] == "approved"
        assert res5.json()["accrual_journal_id"] is not None

        # 6. Leg 2 Disburse
        res6 = await client.post(
            f"/api/v1/payroll/contractor-payments/{payment_id}/disburse?utr=CMSPAY202610150001",
            headers=headers
        )
        assert res6.status_code == 200
        assert res6.json()["status"] == "disbursed"
        assert res6.json()["payout_utr"] == "CMSPAY202610150001"

        # 7. Get Form 16A JSON
        res7 = await client.get(f"/api/v1/payroll/contractors/{contractor_id}/form-16a", headers=headers)
        assert res7.status_code == 200
        f16a = res7.json()
        assert float(f16a["total_gross_amount"]) == 200000.00
        assert float(f16a["total_tds_deducted"]) == 4000.00

        # 8. Download Form 16A PDF
        res8 = await client.get(f"/api/v1/payroll/contractors/{contractor_id}/form-16a/pdf", headers=headers)
        assert res8.status_code == 200
        assert res8.headers["content-type"] == "application/pdf"
        assert "attachment; filename=\"Form16A_CON-API-01_2026-27.pdf\"" in res8.headers["content-disposition"]
        assert res8.content.startswith(b"%PDF")

