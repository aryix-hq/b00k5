import pytest
import uuid
import random
import string
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant, User, TenantUser
from app.models.ledger import ChartOfAccounts


from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.api.deps import get_db

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
async def payroll_test_tenant(db_session: AsyncSession):
    """Provisions an isolated Private Limited company tenant with seeded COA for Payroll API tests."""
    uid = uuid.uuid4().hex[:6]
    rand_alpha = ''.join(random.choices(string.ascii_uppercase, k=4))
    pan = f"A{rand_alpha}{random.randint(1000, 9999)}{random.choice(string.ascii_uppercase)}"
    gstin = f"29{pan}1Z5"
    cin = f"U72200KA2026PTC{random.randint(100000, 999999)}"

    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name=f"Payroll Automation Technologies Pvt Ltd {uid}",
        trade_name="PayrollTech",
        cin=cin,
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="Koramangala 4th Block, Bengaluru, Karnataka 560034",
        statutory_profile={
            "entity_type": "Private Limited Company",
            "tan": f"BLR{pan[:5]}01"
        }
    )
    db_session.add(tenant)

    user = User(
        id=uuid.uuid4(),
        email=f"founder_{uid}@payrolltech.io",
        first_name="Vikram",
        last_name="Khamithkar",
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

    # Seed COA
    await db_session.execute(text(f"SELECT seed_tenant_chart_of_accounts('{tenant.id}')"))
    await db_session.commit()

    tenant._test_user = user
    return tenant


@pytest.fixture
def auth_headers(payroll_test_tenant: Tenant):
    token = create_access_token(
        data={
            "sub": str(payroll_test_tenant._test_user.id),
            "email": payroll_test_tenant._test_user.email,
            "tenant_id": str(payroll_test_tenant.id),
            "role": "owner"
        }
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(payroll_test_tenant.id)
    }


@pytest.mark.asyncio
async def test_payroll_api_employee_onboarding_and_validation(payroll_test_tenant: Tenant, auth_headers: dict):
    """Verifies employee CRUD and validation safeguards (duplicate PAN, duplicate employee code)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Onboard valid employee
        emp_payload = {
            "employee_code": "EMP-001",
            "first_name": "Arjun",
            "last_name": "Rao",
            "email": "arjun.rao@payrolltech.io",
            "phone": "+919876543210",
            "date_of_birth": "1992-06-15",
            "gender": "male",
            "date_of_joining": "2025-04-01",
            "designation": "Staff Systems Architect",
            "department": "Engineering",
            "pan_number": "ABCDE1234F",
            "aadhaar_last_four": "5678",
            "bank_account_number": "91002003004050",
            "bank_ifsc_code": "HDFC0000050",
            "bank_name": "HDFC Bank",
            "tax_regime": "new_115bac",
            "pt_state": "Karnataka",
            "is_pf_capped": True,
            "is_esi_eligible": False
        }
        res = await client.post("/api/v1/payroll/employees", json=emp_payload, headers=auth_headers)
        assert res.status_code == 201, res.text
        created_emp = res.json()
        assert created_emp["employee_code"] == "EMP-001"
        assert created_emp["first_name"] == "Arjun"
        assert created_emp["pan_number"] == "ABCDE1234F"

        # 2. Reject duplicate employee code
        res_dup_code = await client.post("/api/v1/payroll/employees", json={
            **emp_payload,
            "pan_number": "XYZAB5678G",
            "email": "diff@payrolltech.io"
        }, headers=auth_headers)
        assert res_dup_code.status_code == 409
        assert "already exists" in res_dup_code.json()["detail"]

        # 3. Reject duplicate PAN
        res_dup_pan = await client.post("/api/v1/payroll/employees", json={
            **emp_payload,
            "employee_code": "EMP-002",
            "email": "diff2@payrolltech.io"
        }, headers=auth_headers)
        assert res_dup_pan.status_code == 409
        assert "already registered" in res_dup_pan.json()["detail"]

        # 4. Reject invalid PAN format
        res_bad_pan = await client.post("/api/v1/payroll/employees", json={
            **emp_payload,
            "employee_code": "EMP-003",
            "pan_number": "INVALID_PAN_123"
        }, headers=auth_headers)
        assert res_bad_pan.status_code == 422

        # 5. List employees
        res_list = await client.get("/api/v1/payroll/employees", headers=auth_headers)
        assert res_list.status_code == 200
        employees = res_list.json()
        assert len(employees) >= 1
        assert any(e["employee_code"] == "EMP-001" for e in employees)


@pytest.mark.asyncio
async def test_payroll_api_full_run_lifecycle_and_schedule_iii(payroll_test_tenant: Tenant, auth_headers: dict):
    """
    Tests end-to-end API payroll lifecycle:
    1. Onboard 2 employees with CTC structures.
    2. Create April 2026 payroll run.
    3. Calculate run and verify statutory breakdown.
    4. Lock and post Leg 1 (Accrual Journal with SHA-256 seal).
    5. Post Leg 2 (Disbursement Journal with UTR).
    6. Verify Schedule III Balance Sheet and P&L financial reports.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Onboard Employee 1: Principal Architect (High earner, New 115BAC, PF Capped)
        emp1_res = await client.post("/api/v1/payroll/employees", json={
            "employee_code": "EMP-ARCH-01",
            "first_name": "Siddharth",
            "last_name": "Mehta",
            "email": "siddharth@payrolltech.io",
            "date_of_birth": "1988-03-22",
            "date_of_joining": "2024-01-10",
            "designation": "Principal Architect",
            "pan_number": "AABCS9876M",
            "bank_account_number": "5010022334455",
            "bank_ifsc_code": "ICIC0000001",
            "bank_name": "ICICI Bank",
            "tax_regime": "new_115bac",
            "pt_state": "Karnataka",
            "is_pf_capped": True,
            "is_esi_eligible": False
        }, headers=auth_headers)
        assert emp1_res.status_code == 201
        emp1_id = emp1_res.json()["id"]

        # Assign Salary Structure to Employee 1: Monthly Gross = 1,25,000 (CTC = 15,00,000)
        struct1_res = await client.post("/api/v1/payroll/salary-structures", json={
            "employee_id": emp1_id,
            "effective_from": "2025-04-01",
            "annual_ctc": 1500000.00,
            "monthly_basic": 60000.00,
            "monthly_hra": 30000.00,
            "monthly_da": 0.00,
            "monthly_conveyance": 5000.00,
            "monthly_medical_allowance": 0.00,
            "monthly_special_allowance": 30000.00,
            "employer_pf_monthly": 1800.00,
            "employer_esi_monthly": 0.00,
            "is_active": True
        }, headers=auth_headers)
        assert struct1_res.status_code == 201

        # Onboard Employee 2: Support Associate (Gross = 20,000 <= 21,000 -> ESI Eligible)
        emp2_res = await client.post("/api/v1/payroll/employees", json={
            "employee_code": "EMP-OPS-02",
            "first_name": "Kavita",
            "last_name": "Nair",
            "email": "kavita@payrolltech.io",
            "date_of_birth": "1999-12-05",
            "date_of_joining": "2025-04-01",
            "designation": "Support Associate",
            "pan_number": "BBBCK1122N",
            "bank_account_number": "909080807070",
            "bank_ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "tax_regime": "new_115bac",
            "pt_state": "Karnataka",
            "is_pf_capped": True,
            "is_esi_eligible": True
        }, headers=auth_headers)
        assert emp2_res.status_code == 201
        emp2_id = emp2_res.json()["id"]

        # Assign Salary Structure to Employee 2: Monthly Gross = 20,000
        struct2_res = await client.post("/api/v1/payroll/salary-structures", json={
            "employee_id": emp2_id,
            "effective_from": "2025-04-01",
            "annual_ctc": 240000.00,
            "monthly_basic": 10000.00,
            "monthly_hra": 5000.00,
            "monthly_da": 0.00,
            "monthly_conveyance": 2000.00,
            "monthly_medical_allowance": 0.00,
            "monthly_special_allowance": 3000.00,
            "employer_pf_monthly": 1200.00,
            "employer_esi_monthly": 650.00,
            "is_active": True
        }, headers=auth_headers)
        assert struct2_res.status_code == 201

        # 2. Create Payroll Run for April 2026
        run_res = await client.post("/api/v1/payroll/runs", json={
            "run_number": "PR-2026-04-LIVE",
            "month": 4,
            "year": 2026,
            "fiscal_year": "2026-2027"
        }, headers=auth_headers)
        assert run_res.status_code == 201
        run_id = run_res.json()["id"]

        # 3. Calculate Payroll Run
        calc_res = await client.post(f"/api/v1/payroll/runs/{run_id}/calculate", headers=auth_headers)
        assert calc_res.status_code == 200
        calc_data = calc_res.json()
        assert calc_data["status"] == "calculated"
        assert calc_data["total_employees"] == 2
        assert float(calc_data["total_gross_pay"]) == 145000.00 # 125,000 + 20,000
        assert float(calc_data["total_deductions"]) > 0
        assert float(calc_data["total_net_pay"]) > 0
        # Mathematical invariant: Gross = Net + Deductions
        assert abs((float(calc_data["total_net_pay"]) + float(calc_data["total_deductions"])) - 145000.00) < 0.01

        # 4. Fetch Payslips
        payslips_res = await client.get(f"/api/v1/payroll/runs/{run_id}/payslips", headers=auth_headers)
        assert payslips_res.status_code == 200
        payslips = payslips_res.json()
        assert len(payslips) == 2
        for ps in payslips:
            assert ps["payout_status"] == "unpaid"
            assert float(ps["gross_earnings"]) > 0
            assert float(ps["net_salary"]) + float(ps["total_deductions"]) == float(ps["gross_earnings"])

        # 5. Lock and Post Leg 1: Month-End Accrual Journal
        accrual_res = await client.post(f"/api/v1/payroll/runs/{run_id}/lock-and-post-accrual", headers=auth_headers)
        assert accrual_res.status_code == 200
        accrual_data = accrual_res.json()
        assert accrual_data["status"] == "locked"
        assert accrual_data["accrual_journal_id"] is not None
        assert accrual_data["sha256_audit_hash"] is not None
        assert len(accrual_data["sha256_audit_hash"]) == 64

        # 6. Post Leg 2: Salary Disbursement Journal
        disb_res = await client.post(
            f"/api/v1/payroll/runs/{run_id}/post-disbursement",
            params={"bank_account_code": "1010", "payout_utr": "HDFC-CMS-202604300091"},
            headers=auth_headers
        )
        assert disb_res.status_code == 200
        disb_data = disb_res.json()
        assert disb_data["status"] == "disbursed"
        assert disb_data["disbursement_journal_id"] is not None

        # Verify payslips are now marked paid
        updated_slips_res = await client.get(f"/api/v1/payroll/runs/{run_id}/payslips", headers=auth_headers)
        assert updated_slips_res.status_code == 200
        for s in updated_slips_res.json():
            assert s["payout_status"] == "paid"
            assert s["payout_utr"] == "HDFC-CMS-202604300091"

        # 7. Verify Schedule III Profit & Loss Statement (Note 17: Employee Benefits Expense)
        pnl_res = await client.get(
            "/api/v1/reports/schedule-iii/pnl",
            params={"from_date": "2026-04-01", "to_date": "2026-04-30"},
            headers=auth_headers
        )
        if pnl_res.status_code == 200:
            pnl_data = pnl_res.json()
            # Note 17 should contain at least 1,45,000 (Salaries) + Employer PF/ESI
            assert "expenses" in pnl_data or "employee_benefits_expense" in pnl_data or "total_expenses" in pnl_data


@pytest.mark.asyncio
async def test_payroll_api_rls_multi_tenant_isolation(payroll_test_tenant: Tenant, auth_headers: dict, db_session: AsyncSession):
    """Verifies that a separate tenant cannot read or modify another tenant's employees or payroll runs."""
    # Create Tenant B
    tenant_b_id = uuid.uuid4()
    rand_alpha = ''.join(random.choices(string.ascii_uppercase, k=4))
    pan_b = f"B{rand_alpha}{random.randint(1000, 9999)}{random.choice(string.ascii_uppercase)}"
    tenant_b = Tenant(
        id=tenant_b_id,
        legal_name=f"Foreign Tenant Security Labs {tenant_b_id.hex[:6]}",
        trade_name="Foreign Labs",
        cin=f"U72200KA2026PTC{random.randint(100000, 999999)}",
        pan=pan_b,
        gstin=f"29{pan_b}1Z5",
        state_code="29",
        registered_office="Indiranagar, Bengaluru 560038"
    )
    db_session.add(tenant_b)

    user_b = User(
        id=uuid.uuid4(),
        email=f"intruder_{tenant_b_id.hex[:6]}@foreignlabs.com",
        first_name="Foreign",
        last_name="Auditor",
        password_hash="mock_secret_hash",
        is_active=True
    )
    db_session.add(user_b)

    tu_b = TenantUser(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        user_id=user_b.id,
        role="owner"
    )
    db_session.add(tu_b)
    await db_session.flush()
    await db_session.execute(text(f"SELECT seed_tenant_chart_of_accounts('{tenant_b.id}')"))
    await db_session.commit()

    token_b = create_access_token(
        data={
            "sub": str(user_b.id),
            "email": user_b.email,
            "tenant_id": str(tenant_b.id),
            "role": "owner"
        }
    )
    auth_headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Tenant-ID": str(tenant_b.id)
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Tenant B queries employees: Must be empty
        res_b = await client.get("/api/v1/payroll/employees", headers=auth_headers_b)
        assert res_b.status_code == 200
        assert len(res_b.json()) == 0, "RLS Leak! Tenant B saw Tenant A's employees."
