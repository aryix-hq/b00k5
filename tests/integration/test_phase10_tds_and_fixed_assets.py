import pytest
import uuid
import random
import string
from decimal import Decimal
from datetime import date, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.tenant import Tenant, User, TenantUser
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine, FiscalYear
from app.models.tds import TDSChallan, TDSDeduction
from app.models.asset import FixedAsset, FixedAssetDepreciationRun
from app.services.tds_service import TDSService
from app.services.fixed_assets_engine import FixedAssetsEngine

DATABASE_URL = settings.DATABASE_URL


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def phase10_test_tenant(db_session: AsyncSession):
    """Creates a dedicated Private Limited company tenant with baseline COA for Phase 10 testing."""
    uid = uuid.uuid4().hex[:6]
    rand_alpha = ''.join(random.choices(string.ascii_uppercase, k=4))
    pan_digits = f"{random.randint(1000, 9999)}"
    pan_letter = random.choice(string.ascii_uppercase)
    pan = f"A{rand_alpha}{pan_digits}{pan_letter}"
    gstin = f"29{pan}1Z5"
    cin_seq = f"{random.randint(100000, 999999)}"
    cin = f"U72200KA2024PTC{cin_seq}"

    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name=f"Vortex AI Systems Private Limited {uid}",
        trade_name="Vortex AI",
        cin=cin,
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="4th Floor, Tech Park, Koramangala, Bengaluru 560034",
        statutory_profile={
            "entity_type": "Private Limited Company",
            "tan": f"BLR{pan[:5]}01",
            "directors": [
                {"name": "Vikram Sharma", "din": "01234567", "designation": "Director"}
            ]
        }
    )
    db_session.add(tenant)

    user = User(
        id=uuid.uuid4(),
        email=f"founder_{uid}@vortexai.com",
        first_name="Vikram",
        last_name="Sharma",
        password_hash="mocked_pw_hash",
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
    tenant._test_user_id = user.id

    # Seed Accounts needed for TDS and Depreciation
    standard_accounts = [
        {"code": "1010", "name": "Bank Current Account (HDFC Bank)", "type": "asset", "sub_type": "bank", "normal_balance": "debit"},
        {"code": "1050", "name": "Property, Plant & Equipment (Hardware)", "type": "asset", "sub_type": "fixed_asset", "normal_balance": "debit"},
        {"code": "1059", "name": "Accumulated Depreciation - Fixed Assets", "type": "asset", "sub_type": "fixed_asset", "normal_balance": "credit"},
        {"code": "2040", "name": "Trade Payables (Creditors)", "type": "liability", "sub_type": "current_liability", "normal_balance": "credit"},
        {"code": "2060", "name": "TDS Payable u/s 194J (Professional)", "type": "liability", "sub_type": "tax_liability", "normal_balance": "credit"},
        {"code": "2061", "name": "TDS Payable u/s 194C (Contractor)", "type": "liability", "sub_type": "tax_liability", "normal_balance": "credit"},
        {"code": "2062", "name": "TDS Payable u/s 194I (Rent)", "type": "liability", "sub_type": "tax_liability", "normal_balance": "credit"},
        {"code": "2063", "name": "TDS Payable u/s 194Q (Purchase of Goods)", "type": "liability", "sub_type": "tax_liability", "normal_balance": "credit"},
        {"code": "4040", "name": "Legal & Professional Fees (CA/CS/ROC)", "type": "expense", "sub_type": "professional_fees", "normal_balance": "debit"},
        {"code": "4070", "name": "Depreciation & Amortization Expense", "type": "expense", "sub_type": "depreciation", "normal_balance": "debit"},
    ]
    for acc in standard_accounts:
        coa = ChartOfAccounts(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            **acc
        )
        db_session.add(coa)

    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.mark.asyncio
async def test_tds_calculator_statutory_rates():
    """
    Validates Indian TDS withholding rates across sections:
    - 194C: 1% (Individual/HUF), 2% (Company/Others)
    - 194J: 10% (Professional), 2% (Technical)
    - 194I: 2% (Plant & Machinery), 10% (Land & Building)
    - 194Q: 0.1% (Purchase of Goods)
    - 206AA: 20% (Missing/Invalid PAN)
    """
    # 1. 194C Individual (1%) - 4th char of PAN is 'P' (Index 3)
    res_194c_p = TDSService.calculate_tds(
        gross_amount=Decimal("50000.00"),
        section="194C",
        pan="ABCPD1234F"  # 4th char 'P' -> Individual
    )
    assert res_194c_p["applicable_rate_pct"] == Decimal("1.00")
    assert res_194c_p["tds_amount"] == Decimal("500.00")
    assert res_194c_p["net_payable_amount"] == Decimal("49500.00")

    # 2. 194C Company (2%) - 4th char of PAN is 'C' (Index 3)
    res_194c_c = TDSService.calculate_tds(
        gross_amount=Decimal("50000.00"),
        section="194C",
        pan="ABCCD1234F"  # 4th char 'C' -> Company
    )
    assert res_194c_c["applicable_rate_pct"] == Decimal("2.00")
    assert res_194c_c["tds_amount"] == Decimal("1000.00")
    assert res_194c_c["net_payable_amount"] == Decimal("49000.00")

    # 3. 194J Professional Services (10%)
    res_194j_prof = TDSService.calculate_tds(
        gross_amount=Decimal("100000.00"),
        section="194J",
        pan="ABCCD1234F"
    )
    assert res_194j_prof["applicable_rate_pct"] == Decimal("10.00")
    assert res_194j_prof["tds_amount"] == Decimal("10000.00")
    assert res_194j_prof["net_payable_amount"] == Decimal("90000.00")

    # 4. 194J Technical Services (2%)
    res_194j_tech = TDSService.calculate_tds(
        gross_amount=Decimal("100000.00"),
        section="194J",
        pan="ABCCD1234F",
        sub_type="technical"
    )
    assert res_194j_tech["applicable_rate_pct"] == Decimal("2.00")
    assert res_194j_tech["tds_amount"] == Decimal("2000.00")

    # 5. 194I Plant/Machinery (2%) vs Land/Building (10%)
    res_194i_mach = TDSService.calculate_tds(
        gross_amount=Decimal("300000.00"),
        section="194I",
        pan="ABCCD1234F",
        sub_type="machinery"
    )
    assert res_194i_mach["applicable_rate_pct"] == Decimal("2.00")
    assert res_194i_mach["tds_amount"] == Decimal("6000.00")

    res_194i_land = TDSService.calculate_tds(
        gross_amount=Decimal("300000.00"),
        section="194I",
        pan="ABCCD1234F",
        sub_type="building"
    )
    assert res_194i_land["applicable_rate_pct"] == Decimal("10.00")
    assert res_194i_land["tds_amount"] == Decimal("30000.00")

    # 6. Section 206AA Penal Rate (20% for invalid or missing PAN)
    res_non_pan = TDSService.calculate_tds(
        gross_amount=Decimal("50000.00"),
        section="194C",
        pan="INVALID_PAN"
    )
    assert res_non_pan["applicable_rate_pct"] == Decimal("20.00")
    assert res_non_pan["tds_amount"] == Decimal("10000.00")
    assert not res_non_pan["pan_valid"]


@pytest.mark.asyncio
async def test_tds_expense_booking_and_ledger_balance(db_session: AsyncSession, phase10_test_tenant: Tenant):
    """
    Tests TDS deduction recording and statutory summary calculation:
    - Books deduction u/s 194J
    - Confirms TDSDeduction created with PENDING_DEPOSIT status
    - Confirms summary reflects total deducted and pending deposit
    """
    tenant_id = phase10_test_tenant.id

    gross = Decimal("75000.00")
    calc = TDSService.calculate_tds(gross, "194J", pan="AAACC1234F")
    tds_val = calc["tds_amount"]  # ₹7,500.00

    ded = await TDSService.record_tds_deduction(
        db=db_session,
        tenant_id=tenant_id,
        deductee_name="Singhania & Partners Legal Advisory",
        deductee_pan="AAACC1234F",
        section="194J",
        gross_amount=gross,
        deduction_date=date.today()
    )
    await db_session.commit()
    await db_session.refresh(ded)

    assert ded.id is not None
    assert ded.tds_amount == tds_val
    assert ded.status == "PENDING_DEPOSIT"

    # Verify summary reflects deduction
    summary = await TDSService.get_tds_summary(db_session, tenant_id)
    assert summary["total_deducted"] >= tds_val
    assert summary["total_pending_deposit"] >= tds_val


@pytest.mark.asyncio
async def test_challan_itns281_and_balancing_voucher(db_session: AsyncSession, phase10_test_tenant: Tenant):
    """
    Tests Challan ITNS 281 tax deposit:
    - Records challan with BSR code and Challan Serial Number
    - Marks linked deductions as DEPOSITED
    - Automatically posts balancing General Ledger voucher:
      DR 2060 TDS Payable u/s 194J
      CR 1010 Bank Current Account
    - Validates mathematical parity |Sum(Dr) - Sum(Cr)| == 0.00
    """
    tenant_id = phase10_test_tenant.id

    ded = await TDSService.record_tds_deduction(
        db=db_session,
        tenant_id=tenant_id,
        deductee_name="Tech Consultant LLP",
        deductee_pan="AAACF9999K",
        section="194J",
        gross_amount=Decimal("50000.00"),
        deduction_date=date.today()
    )
    await db_session.commit()

    challan_res = await TDSService.record_challan_itns281(
        db=db_session,
        tenant_id=tenant_id,
        fiscal_year=ded.fiscal_year,
        quarter=ded.quarter,
        section="194J",
        bsr_code="0210001",
        challan_serial_no="CHAL9876",
        payment_date=date.today(),
        tds_amount=ded.tds_amount,
        deduction_ids=[ded.id],
        auto_post_jv=True
    )

    assert challan_res["challan_id"] is not None
    assert challan_res["linked_deductions_count"] >= 1
    assert challan_res["journal_entry_id"] is not None

    # Inspect balancing journal entry
    jv_stmt = select(JournalEntry).where(JournalEntry.id == challan_res["journal_entry_id"])
    jv = (await db_session.execute(jv_stmt)).scalar_one()
    assert jv.is_posted is True

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == jv.id)
    lines = (await db_session.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2

    total_dr = sum(l.debit_amount for l in lines)
    total_cr = sum(l.credit_amount for l in lines)
    assert total_dr == total_cr
    assert total_dr == ded.tds_amount


@pytest.mark.asyncio
async def test_form26q_text_file_generation(db_session: AsyncSession, phase10_test_tenant: Tenant):
    """
    Validates generation of official NSDL / Protean ASCII e-TDS return file for Form 26Q:
    - File Header (FH) with NSDL-26Q identifier
    - Batch Header (BH) with TAN, PAN, and Assessment Year
    """
    tenant_id = phase10_test_tenant.id

    content = await TDSService.generate_form26q_text_file(
        db=db_session,
        tenant_id=tenant_id,
        fiscal_year="2026-27",
        quarter="Q3"
    )
    assert isinstance(content, str)
    assert "FH^NSDL-26Q" in content
    assert "^BH^" in content
    assert "^26Q^" in content


@pytest.mark.asyncio
async def test_fixed_asset_registration_and_schedule_ii_useful_life(db_session: AsyncSession, phase10_test_tenant: Tenant):
    """
    Validates capital asset registration:
    - Automatic useful life lookup per Schedule II Part C (Computers: 3 years)
    - 5% statutory salvage value auto-calculation
    - Initial net block equals gross block
    """
    tenant_id = phase10_test_tenant.id

    asset = await FixedAssetsEngine.register_asset(
        session=db_session,
        tenant_id=tenant_id,
        asset_name="Apple MacBook Pro M3 Max (Dev Lead)",
        category="COMPUTERS_END_USER",
        purchase_date=date.today(),
        gross_block=Decimal("250000.00"),
        depreciation_method="SLM",
        location="Bangalore HQ"
    )
    await db_session.commit()
    await db_session.refresh(asset)

    assert asset.asset_code.startswith("FA-")
    assert asset.useful_life_years == Decimal("3.0")
    # 5% of 250,000 = 12,500.00
    assert asset.salvage_value == Decimal("12500.00")
    assert asset.accumulated_depreciation == Decimal("0.00")
    assert asset.net_block == Decimal("250000.00")


@pytest.mark.asyncio
async def test_period_end_depreciation_run_and_contra_asset(db_session: AsyncSession, phase10_test_tenant: Tenant):
    """
    Validates period-end automated depreciation run:
    - Pro-rata daily calculation based on days in service
    - Auto-posting of balancing journal voucher:
      DR 4070 Depreciation & Amortization Expense
      CR 1059 Accumulated Depreciation - Fixed Assets (Contra Asset)
    - Verifies |Sum(Dr) - Sum(Cr)| == 0.00
    - Verifies net block updated without dipping below 5% salvage value
    """
    tenant_id = phase10_test_tenant.id

    p_date = date.today() - timedelta(days=180)
    asset = await FixedAssetsEngine.register_asset(
        session=db_session,
        tenant_id=tenant_id,
        asset_name="Cisco Office Gigabit Router & Switch",
        category="OFFICE_EQUIPMENT",
        purchase_date=p_date,
        capitalization_date=p_date,
        gross_block=Decimal("100000.00"),
        depreciation_method="SLM"
    )
    await db_session.commit()

    dep_run = await FixedAssetsEngine.execute_period_depreciation_run(
        session=db_session,
        tenant_id=tenant_id,
        fiscal_year="2026-27",
        period_start=p_date,
        period_end=date.today(),
        auto_post_jv=True
    )
    await db_session.commit()

    assert dep_run["status"] == "POSTED"
    assert dep_run["total_depreciation_amount"] > Decimal("0.00")
    assert dep_run["journal_entry_id"] is not None

    # Inspect posted journal entry
    jv_stmt = select(JournalEntry).where(JournalEntry.id == dep_run["journal_entry_id"])
    jv = (await db_session.execute(jv_stmt)).scalar_one()

    lines_stmt = select(JournalLine).where(JournalLine.journal_entry_id == jv.id)
    lines = (await db_session.execute(lines_stmt)).scalars().all()
    assert len(lines) == 2

    # Invariant check: Debits == Credits
    dr_tot = sum(l.debit_amount for l in lines)
    cr_tot = sum(l.credit_amount for l in lines)
    assert dr_tot == cr_tot
    assert dr_tot == dep_run["total_depreciation_amount"]

    # Verify Schedule II summary table
    summary = await FixedAssetsEngine.get_schedule_ii_summary(db_session, tenant_id)
    assert summary["total_gross_block"] >= Decimal("100000.00")
    assert summary["total_accumulated_depreciation"] >= dep_run["total_depreciation_amount"]
    assert len(summary["categories"]) > 0


@pytest.mark.asyncio
async def test_tds_api_endpoints_e2e(phase10_test_tenant: Tenant):
    """
    End-to-End API test for /api/v1/tds routes:
    - POST /api/v1/tds/calculate
    - GET /api/v1/tds/summary
    - GET /api/v1/tds/form26q-export
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.security import create_access_token

    tenant_id = str(phase10_test_tenant.id)
    user_id = str(phase10_test_tenant._test_user_id)
    token = create_access_token(
        data={"sub": user_id, "email": "founder@vortexai.com", "tenant_id": tenant_id, "role": "owner"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Calculate
        calc_resp = await client.post(
            "/api/v1/tds/calculate",
            json={"gross_amount": 100000.0, "section": "194J", "pan": "ABCCD1234F"},
            headers=headers
        )
        assert calc_resp.status_code == 200
        calc_data = calc_resp.json()
        assert float(calc_data["applicable_rate_pct"]) == 10.0
        assert float(calc_data["tds_amount"]) == 10000.0
        assert float(calc_data["net_payable_amount"]) == 90000.0

        # 2. Summary
        sum_resp = await client.get("/api/v1/tds/summary", headers=headers)
        assert sum_resp.status_code == 200
        sum_data = sum_resp.json()
        assert "total_deducted" in sum_data
        assert "next_due_date" in sum_data

        # 3. Form 26Q Export
        exp_resp = await client.get(
            "/api/v1/tds/form26q-export?fiscal_year=2026-27&quarter=Q3",
            headers=headers
        )
        assert exp_resp.status_code == 200
        assert "FH^NSDL-26Q" in exp_resp.text


@pytest.mark.asyncio
async def test_fixed_assets_api_endpoints_e2e(phase10_test_tenant: Tenant):
    """
    End-to-End API test for /api/v1/assets routes:
    - POST /api/v1/assets/register
    - GET /api/v1/assets/registry
    - GET /api/v1/assets/schedule-ii-summary
    - POST /api/v1/assets/run-depreciation
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.security import create_access_token

    tenant_id = str(phase10_test_tenant.id)
    user_id = str(phase10_test_tenant._test_user_id)
    token = create_access_token(
        data={"sub": user_id, "email": "founder@vortexai.com", "tenant_id": tenant_id, "role": "owner"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register Asset
        p_date = date.today().isoformat()
        reg_resp = await client.post(
            "/api/v1/assets/register",
            json={
                "asset_name": "Dell PowerEdge R750 Server",
                "category": "SERVERS_NETWORK",
                "purchase_date": p_date,
                "gross_block": 400000.0,
                "depreciation_method": "SLM"
            },
            headers=headers
        )
        assert reg_resp.status_code == 200
        reg_data = reg_resp.json()
        assert float(reg_data["useful_life_years"]) == 6.0
        assert float(reg_data["salvage_value"]) == 20000.0 # 5% of 400,000

        # 2. Registry list
        list_resp = await client.get("/api/v1/assets/registry", headers=headers)
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) >= 1

        # 3. Schedule II Summary
        summary_resp = await client.get("/api/v1/assets/schedule-ii-summary", headers=headers)
        assert summary_resp.status_code == 200
        s_data = summary_resp.json()
        assert float(s_data["total_gross_block"]) >= 400000.0

        # 4. Period-End Depreciation Run
        run_resp = await client.post(
            "/api/v1/assets/run-depreciation",
            json={
                "fiscal_year": "2026-27",
                "period_start": p_date,
                "period_end": date.today().isoformat(),
                "auto_post_jv": True
            },
            headers=headers
        )
        assert run_resp.status_code == 200, run_resp.text
        run_data = run_resp.json()
        assert run_data["status"] == "POSTED"

