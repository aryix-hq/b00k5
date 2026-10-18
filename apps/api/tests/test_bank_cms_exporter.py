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
from app.models.payroll import Employee, SalaryStructure, PayrollRun, Payslip, Contractor, ContractorPayment
from app.schemas.payroll import EmployeeCreate, ContractorCreate, ContractorPaymentCreate
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
async def cms_test_tenant(db_session: AsyncSession):
    """Provisions a test tenant with user and account."""
    uid = uuid.uuid4().hex[:6]
    rand_alpha = ''.join(random.choices(string.ascii_uppercase, k=4))
    pan = f"A{rand_alpha}{random.randint(1000, 9999)}{random.choice(string.ascii_uppercase)}"
    gstin = f"29{pan}1Z5"

    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name=f"CMS Test Corp {uid} Pvt Ltd",
        trade_name="CMS Corp",
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="123 MG Road, Bangalore, Karnataka"
    )
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email=f"finance.{uid}@cmstest.com",
        password_hash="argon2id$mocked$password",
        first_name="Finance",
        last_name="Manager",
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
async def test_payroll_bank_cms_formats(db_session: AsyncSession, cms_test_tenant: dict):
    """Verifies HDFC ENet, ICICI CMS, and SBI CMP CSV generation for salaried payroll."""
    tenant = cms_test_tenant["tenant"]

    # 1. Onboard 2 employees
    emp1 = Employee(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_code=f"E{random.randint(100, 999)}",
        first_name="Rohan",
        last_name="Sharma",
        email=f"rohan.{random.randint(100, 999)}@cmstest.com",
        date_of_birth=date(1990, 1, 1),
        date_of_joining=date(2025, 1, 1),
        designation="Software Engineer",
        pan_number=f"ABCDE{random.randint(1000, 9999)}F",
        bank_name="HDFC Bank",
        bank_account_number="50100492819201",
        bank_ifsc_code="HDFC0000123",
        tax_regime="new_115bac"
    )
    db_session.add(emp1)

    struct1 = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=emp1.id,
        effective_from=date(2025, 1, 1),
        annual_ctc=Decimal("1800000.00"),
        monthly_basic=Decimal("75000.00"),
        monthly_hra=Decimal("37500.00"),
        monthly_special_allowance=Decimal("37500.00"),
        is_active=True
    )
    db_session.add(struct1)

    emp2 = Employee(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_code=f"E{random.randint(100, 999)}",
        first_name="Priya",
        last_name="Nair",
        email=f"priya.{random.randint(100, 999)}@cmstest.com",
        date_of_birth=date(1992, 5, 10),
        date_of_joining=date(2025, 1, 1),
        designation="Product Manager",
        pan_number=f"XYZPQ{random.randint(1000, 9999)}R",
        bank_name="ICICI Bank",
        bank_account_number="001105002918",
        bank_ifsc_code="ICIC0000011",
        tax_regime="new_115bac"
    )
    db_session.add(emp2)

    struct2 = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=emp2.id,
        effective_from=date(2025, 1, 1),
        annual_ctc=Decimal("3000000.00"),
        monthly_basic=Decimal("125000.00"),
        monthly_hra=Decimal("62500.00"),
        monthly_special_allowance=Decimal("62500.00"),
        is_active=True
    )
    db_session.add(struct2)

    # Seed COA for run calculation
    await db_session.execute(text(f"SELECT seed_tenant_chart_of_accounts('{tenant.id}')"))
    await db_session.commit()

    # 2. Run monthly payroll
    run = PayrollRun(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        run_number=f"RUN-2026-09-CMS",
        month=9,
        year=2026,
        fiscal_year="2026-27",
        status="draft"
    )
    db_session.add(run)
    await db_session.commit()
    await PayrollService.calculate_payroll_run(db_session, run.id)

    # 3. Test HDFC ENet CSV
    hdfc_csv = await PayrollService.generate_payroll_bank_cms_csv(
        db_session,
        run_id=run.id,
        bank_format="hdfc_enet",
        debit_account="50200012345678"
    )
    assert "Transaction Type,Beneficiary Code,Beneficiary Account Number" in hdfc_csv
    assert "ROHAN SHARMA" in hdfc_csv
    assert "50100492819201" in hdfc_csv
    assert "HDFC0000123" in hdfc_csv
    assert "PRIYA NAIR" in hdfc_csv

    # 4. Test ICICI CMS CSV
    icici_csv = await PayrollService.generate_payroll_bank_cms_csv(
        db_session,
        run_id=run.id,
        bank_format="icici_cms",
        debit_account="001105009999"
    )
    assert "Client Code,Product Code,Payment Type,Payment Ref Number" in icici_csv
    assert "B00K5PAY,NEFT" in icici_csv
    assert "001105009999" in icici_csv
    assert "ICIC0000011" in icici_csv

    # 5. Test SBI CMP CSV
    sbi_csv = await PayrollService.generate_payroll_bank_cms_csv(
        db_session,
        run_id=run.id,
        bank_format="sbi_cmp"
    )
    assert "Debit Account No,Beneficiary Account No,Beneficiary Name" in sbi_csv
    assert "ROHAN SHARMA" in sbi_csv
    assert "NEFT" in sbi_csv


@pytest.mark.asyncio
async def test_contractor_bank_cms_and_rest_api(db_session: AsyncSession, cms_test_tenant: dict):
    """Verifies Contractor CMS CSV and REST API endpoints."""
    tenant = cms_test_tenant["tenant"]
    user = cms_test_tenant["user"]

    # 1. Onboard contractor
    contractor_data = ContractorCreate(
        contractor_code=f"CNT-{random.randint(100, 999)}",
        name="Apex DevOps Solutions LLP",
        contractor_type="company_firm",
        pan_number="AABCA1234F",
        tds_section="194J_TECH",
        tds_rate=Decimal("2.00"),
        bank_name="HDFC Bank",
        bank_account_number="987654321012",
        bank_ifsc_code="HDFC0000456",
        email="billing@apexdevops.com"
    )
    contractor = await PayrollService.onboard_contractor(db_session, tenant.id, contractor_data)

    # 2. Record contractor payment
    payment_data = ContractorPaymentCreate(
        contractor_id=contractor.id,
        invoice_number=f"INV-APEX-{random.randint(1000, 9999)}",
        invoice_date=date(2026, 9, 15),
        payment_date=date(2026, 9, 20),
        description="Cloud Infrastructure & DevOps Support",
        gross_amount=Decimal("100000.00"),
        gst_rate=Decimal("18.00"),
        tds_section="194J_TECH"
    )
    payment = await PayrollService.create_contractor_payment(db_session, tenant.id, payment_data)

    # 3. Test Contractor CSV formats
    c_hdfc = await PayrollService.generate_contractor_bank_cms_csv(
        db_session,
        tenant_id=tenant.id,
        payment_ids=[payment.id],
        bank_format="hdfc_enet"
    )
    assert "APEX DEVOPS SOLUTIONS LLP" in c_hdfc
    assert "987654321012" in c_hdfc
    assert "116000.00" in c_hdfc # 1,00,000 + 18,000 - 2,000 = 1,16,000

    c_icici = await PayrollService.generate_contractor_bank_cms_csv(
        db_session,
        tenant_id=tenant.id,
        bank_format="icici_cms"
    )
    assert "Client Code,Product Code" in c_icici
    assert "116000.00" in c_icici

    # 4. REST API test
    token = create_access_token({"sub": str(user.id), "tenant_id": str(tenant.id)})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Contractor CMS endpoint
        resp = await client.get("/api/v1/payroll/contractor-payments/export/bank-cms?bank_format=hdfc_enet", headers=headers)
        assert resp.status_code == 200
        assert "APEX DEVOPS SOLUTIONS LLP" in resp.text
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in resp.headers["content-disposition"]
