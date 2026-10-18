import pytest
import uuid
import random
import string
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.api.deps import get_db
from app.models.tenant import Tenant, User, TenantUser
from app.models.payroll import Employee, SalaryStructure, PayrollRun, Payslip
from app.services.payroll_service import PayrollService


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
async def exporter_test_tenant(db_session: AsyncSession):
    """Provisions an isolated Private Limited company tenant with seeded COA."""
    uid = uuid.uuid4().hex[:6]
    rand_alpha = ''.join(random.choices(string.ascii_uppercase, k=4))
    pan = f"A{rand_alpha}{random.randint(1000, 9999)}{random.choice(string.ascii_uppercase)}"
    gstin = f"29{pan}1Z5"
    cin = f"U72200KA2026PTC{random.randint(100000, 999999)}"

    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name=f"Statutory Exporters Pvt Ltd {uid}",
        trade_name="StatExporters",
        cin=cin,
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="Indiranagar, Bengaluru, Karnataka 560038",
        statutory_profile={
            "entity_type": "Private Limited Company",
            "tan": f"BLR{pan[:5]}01"
        }
    )
    db_session.add(tenant)

    user = User(
        id=uuid.uuid4(),
        email=f"founder_{uid}@statexporters.in",
        first_name="Rohan",
        last_name="Murthy",
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


@pytest.fixture
def auth_headers(exporter_test_tenant: Tenant):
    token = create_access_token(
        data={
            "sub": str(exporter_test_tenant._test_user.id),
            "email": exporter_test_tenant._test_user.email,
            "tenant_id": str(exporter_test_tenant.id),
            "role": "owner"
        }
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(exporter_test_tenant.id)
    }


@pytest.mark.asyncio
async def test_epfo_ecr_text_exporter(exporter_test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies EPFO ECR 2.0 text file formatting rules:
    - Delimiter #~#
    - 11 fields per record
    - Wage caps (EPF wages capped at 15,000 for is_pf_capped=True)
    - 12% EE share, 8.33% EPS share (capped at 1,250), 3.67% ER share
    """
    tenant = exporter_test_tenant

    emp = Employee(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_code="EMP-PF-001",
        first_name="Pooja",
        last_name="Shukla",
        email="pooja.shukla@statexporters.in",
        date_of_birth=date(1995, 5, 12),
        date_of_joining=date(2024, 4, 1),
        status="active",
        employment_type="full_time",
        designation="Lead Systems Engineer",
        pan_number="AABCS8891P",
        uan_number="100984920192",
        bank_account_number="912010048192019",
        bank_ifsc_code="HDFC0001234",
        bank_name="HDFC Bank",
        tax_regime="new_115bac",
        pt_state="Karnataka",
        pf_opt_out=False,
        is_pf_capped=True,
        is_esi_eligible=False
    )
    db_session.add(emp)

    struct = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=emp.id,
        effective_from=date(2024, 4, 1),
        annual_ctc=Decimal("1200000.00"),
        monthly_basic=Decimal("50000.00"),
        monthly_hra=Decimal("25000.00"),
        monthly_special_allowance=Decimal("25000.00"),
        is_active=True
    )
    db_session.add(struct)

    run = PayrollRun(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        run_number="RUN-2026-05-EXPO",
        month=5,
        year=2026,
        fiscal_year="2026-27",
        status="draft"
    )
    db_session.add(run)
    await db_session.commit()

    # Calculate run
    await PayrollService.calculate_payroll_run(db_session, run.id)
    await db_session.commit()

    # Generate EPFO ECR
    ecr_txt = await PayrollService.generate_epfo_ecr_txt(db_session, run.id)
    assert isinstance(ecr_txt, str)
    assert len(ecr_txt.strip()) > 0

    lines = [l for l in ecr_txt.strip().split("\n") if l and not l.startswith("#")]
    assert len(lines) == 1

    fields = lines[0].split("#~#")
    assert len(fields) == 11, f"Expected 11 fields separated by #~#, got {len(fields)}: {fields}"

    assert fields[0] == "100984920192"  # UAN
    assert fields[1] == "POOJA SHUKLA"  # Uppercase Name
    assert int(fields[2]) == 100000     # Gross wages (50k basic + 25k hra + 25k special)
    assert int(fields[3]) == 15000      # EPF wages capped at 15,000
    assert int(fields[4]) == 15000      # EPS wages capped at 15,000
    assert int(fields[5]) == 15000      # EDLI wages capped at 15,000
    assert int(fields[6]) == 1800       # EE Share (12% of 15,000)
    assert int(fields[7]) == 1250       # EPS Share (8.33% capped at 1,250)
    assert int(fields[8]) == 550        # ER Share (1800 - 1250 = 550)
    assert int(fields[9]) == 0          # NCP days (0 LOP)
    assert int(fields[10]) == 0         # Refund of advances


@pytest.mark.asyncio
async def test_esic_and_pt_return_exporters(exporter_test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies ESIC monthly portal CSV return and Professional Tax state summary exporter.
    """
    tenant = exporter_test_tenant

    emp_esi = Employee(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_code="EMP-ESI-002",
        first_name="Ramesh",
        last_name="Yadav",
        email="ramesh.yadav@statexporters.in",
        date_of_birth=date(1998, 8, 20),
        date_of_joining=date(2025, 1, 15),
        status="active",
        employment_type="full_time",
        designation="Operations Associate",
        pan_number="AAACA1120Q",
        esic_number="3109849201",
        bank_account_number="6010048192019",
        bank_ifsc_code="SBIN0001234",
        bank_name="State Bank of India",
        tax_regime="new_115bac",
        pt_state="Karnataka",
        pf_opt_out=False,
        is_pf_capped=True,
        is_esi_eligible=True
    )
    db_session.add(emp_esi)

    struct = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=emp_esi.id,
        effective_from=date(2025, 1, 15),
        annual_ctc=Decimal("240000.00"),
        monthly_basic=Decimal("12000.00"),
        monthly_hra=Decimal("5000.00"),
        monthly_special_allowance=Decimal("3000.00"),
        is_active=True
    )
    db_session.add(struct)

    # Also add a PT-paying employee (gross >= 25,000 in Karnataka)
    emp_pt = Employee(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_code="EMP-PT-003",
        first_name="Deepa",
        last_name="Rao",
        email="deepa.rao@statexporters.in",
        date_of_birth=date(1996, 4, 10),
        date_of_joining=date(2025, 2, 1),
        status="active",
        employment_type="full_time",
        designation="Senior Analyst",
        pan_number="AABCA1120M",
        bank_account_number="6010048192020",
        bank_ifsc_code="SBIN0001234",
        bank_name="State Bank of India",
        tax_regime="new_115bac",
        pt_state="Karnataka",
        pf_opt_out=False,
        is_pf_capped=True,
        is_esi_eligible=False
    )
    db_session.add(emp_pt)

    struct_pt = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=emp_pt.id,
        effective_from=date(2025, 2, 1),
        annual_ctc=Decimal("480000.00"),
        monthly_basic=Decimal("20000.00"),
        monthly_hra=Decimal("10000.00"),
        monthly_special_allowance=Decimal("10000.00"),
        is_active=True
    )
    db_session.add(struct_pt)

    run = PayrollRun(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        run_number="RUN-2026-05-ESI",
        month=5,
        year=2026,
        fiscal_year="2026-27",
        status="draft"
    )
    db_session.add(run)
    await db_session.commit()

    # Calculate run
    await PayrollService.calculate_payroll_run(db_session, run.id)
    await db_session.commit()

    # 1. ESIC Return Export
    esic_csv = await PayrollService.generate_esic_return_csv(db_session, run.id)
    assert "IP Number,IP Name,No of Days for which wages paid,Total Monthly Wages" in esic_csv
    assert "3109849201" in esic_csv
    assert "Ramesh Yadav" in esic_csv
    assert "20000" in esic_csv

    # 2. PT Return Export
    pt_csv = await PayrollService.generate_pt_return_csv(db_session, run.id)
    assert "State,Employee Code,Employee Name,PAN,Gross Earnings,Professional Tax Deducted" in pt_csv
    assert "Karnataka" in pt_csv
    assert "EMP-PT-003" in pt_csv
    assert "SUMMARY: ALL STATES" in pt_csv


@pytest.mark.asyncio
async def test_form_16_calculation_and_pdf_generation(exporter_test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies Section 192 Form 16 Part A & Part B computation and PDF certificate generation.
    Checks New Tax Regime (Section 115BAC) standard deduction of Rs 75,000 and 4% cess.
    """
    tenant = exporter_test_tenant

    emp = Employee(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_code="EMP-DIR-003",
        first_name="Ananya",
        last_name="Deshmukh",
        email="ananya.deshmukh@statexporters.in",
        date_of_birth=date(1992, 11, 4),
        date_of_joining=date(2023, 4, 1),
        status="active",
        employment_type="full_time",
        designation="VP of Engineering",
        pan_number="ABCPD9901M",
        uan_number="100984920199",
        bank_account_number="12010048192019",
        bank_ifsc_code="ICIC0001234",
        bank_name="ICICI Bank",
        tax_regime="new_115bac",
        pt_state="Karnataka",
        pf_opt_out=False,
        is_pf_capped=True,
        is_esi_eligible=False
    )
    db_session.add(emp)

    struct = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=emp.id,
        effective_from=date(2023, 4, 1),
        annual_ctc=Decimal("1800000.00"),
        monthly_basic=Decimal("75000.00"),
        monthly_hra=Decimal("37500.00"),
        monthly_special_allowance=Decimal("37500.00"),
        is_active=True
    )
    db_session.add(struct)
    await db_session.commit()

    # 1. Compute Form 16 JSON
    f16_data = await PayrollService.calculate_form_16(db_session, emp.id, "2026-27")
    assert f16_data["employee_name"] == "Ananya Deshmukh"
    assert f16_data["pan_number"] == "ABCPD9901M"
    assert f16_data["tax_regime"] == "new_115bac"
    assert f16_data["gross_salary"] == 1800000.0
    assert f16_data["standard_deduction"] == 75000.0  # Standard deduction under 115BAC
    assert f16_data["total_taxable_income"] == (1800000.0 - 75000.0)
    assert f16_data["total_tax_payable"] > 0.0
    assert len(f16_data["quarterly_tds_summary"]) == 4

    # 2. Generate Form 16 PDF
    pdf_bytes = await PayrollService.generate_form_16_pdf_for_employee(db_session, emp.id, "2026-27")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_api_statutory_export_endpoints(exporter_test_tenant: Tenant, auth_headers: dict, db_session: AsyncSession):
    """
    Verifies REST API endpoints:
    - GET /runs/{run_id}/export/epfo-ecr -> 200 attachment .txt
    - GET /runs/{run_id}/export/esic -> 200 attachment .csv
    - GET /runs/{run_id}/export/pt -> 200 attachment .csv
    - GET /employees/{employee_id}/form-16 -> 200 Form16Response
    - GET /employees/{employee_id}/form-16/pdf -> 200 attachment .pdf
    """
    tenant = exporter_test_tenant

    emp = Employee(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_code="EMP-API-004",
        first_name="Arjun",
        last_name="Menon",
        email="arjun.menon@statexporters.in",
        date_of_birth=date(1994, 3, 10),
        date_of_joining=date(2024, 6, 1),
        status="active",
        employment_type="full_time",
        designation="Staff Architect",
        pan_number="ABCPD1101K",
        uan_number="100984920194",
        esic_number="3109849204",
        bank_account_number="33010048192019",
        bank_ifsc_code="KKBK0001234",
        bank_name="Kotak Mahindra Bank",
        tax_regime="new_115bac",
        pt_state="Karnataka",
        pf_opt_out=False,
        is_pf_capped=True,
        is_esi_eligible=False
    )
    db_session.add(emp)

    struct = SalaryStructure(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=emp.id,
        effective_from=date(2024, 6, 1),
        annual_ctc=Decimal("1500000.00"),
        monthly_basic=Decimal("60000.00"),
        monthly_hra=Decimal("30000.00"),
        monthly_special_allowance=Decimal("35000.00"),
        is_active=True
    )
    db_session.add(struct)

    run = PayrollRun(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        run_number="RUN-2026-05-API",
        month=5,
        year=2026,
        fiscal_year="2026-27",
        status="draft"
    )
    db_session.add(run)
    await db_session.commit()

    # Calculate run
    await PayrollService.calculate_payroll_run(db_session, run.id)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. EPFO ECR Export
        res_ecr = await ac.get(f"/api/v1/payroll/runs/{run.id}/export/epfo-ecr", headers=auth_headers)
        assert res_ecr.status_code == 200
        assert "text/plain" in res_ecr.headers["content-type"]
        assert "attachment; filename=" in res_ecr.headers["content-disposition"]
        assert "100984920194" in res_ecr.text
        assert "ARJUN MENON" in res_ecr.text

        # 2. ESIC Return Export
        res_esic = await ac.get(f"/api/v1/payroll/runs/{run.id}/export/esic", headers=auth_headers)
        assert res_esic.status_code == 200
        assert "text/csv" in res_esic.headers["content-type"]
        assert "attachment; filename=" in res_esic.headers["content-disposition"]

        # 3. PT Return Export
        res_pt = await ac.get(f"/api/v1/payroll/runs/{run.id}/export/pt", headers=auth_headers)
        assert res_pt.status_code == 200
        assert "text/csv" in res_pt.headers["content-type"]
        assert "EMP-API-004" in res_pt.text

        # 4. Form 16 JSON
        res_f16 = await ac.get(f"/api/v1/payroll/employees/{emp.id}/form-16?financial_year=2026-27", headers=auth_headers)
        assert res_f16.status_code == 200
        data = res_f16.json()
        assert data["employee_code"] == "EMP-API-004"
        assert data["tax_regime"] == "new_115bac"
        assert float(data["standard_deduction"]) == 75000.0

        # 5. Form 16 PDF
        res_f16_pdf = await ac.get(f"/api/v1/payroll/employees/{emp.id}/form-16/pdf?financial_year=2026-27", headers=auth_headers)
        assert res_f16_pdf.status_code == 200
        assert "application/pdf" in res_f16_pdf.headers["content-type"]
        assert "attachment; filename=" in res_f16_pdf.headers["content-disposition"]
        assert res_f16_pdf.content.startswith(b"%PDF")
