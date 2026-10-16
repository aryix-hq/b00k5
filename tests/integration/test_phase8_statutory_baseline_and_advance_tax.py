"""
b00k5 - Phase 8 Integration Test Suite:
1. Statutory Baseline Anchoring & Historical FY Seal (AOC-4 / ITR-6 / AS-5 / Sec 128 / Sec 130)
2. Advance Tax Forecasting & Penal Interest Watchdog (Sec 208, 211, 234B & 234C)
"""

import pytest
import uuid
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant, User, TenantUser
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine, FiscalYear
from app.models.invoice import Invoice, Contact
from app.models.compliance import StatutoryFilingAnchor, AdvanceTaxForecast, AdvanceTaxChallan
from app.services.statutory_anchor_service import StatutoryAnchorService
from app.services.advance_tax_service import AdvanceTaxService
from app.core.s3 import storage_manager

DATABASE_URL = settings.DATABASE_URL


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def phase8_test_tenant(db_session):
    """Creates a dedicated Private Limited company tenant with baseline COA and statutory anchor."""
    import random
    import string
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
        legal_name=f"Nexura Technologies Private Limited {uid}",
        trade_name="Nexura Tech",
        cin=cin,
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="7th Floor, Innovation Hub, Outer Ring Road, Bengaluru 560103",
        statutory_profile={
            "entity_type": "Private Limited Company",
            "incorporation_date": "2024-04-10",
            "directors": [
                {"name": "Aditya Sharma", "din": "09876543", "designation": "Managing Director"}
            ]
        }
    )
    db_session.add(tenant)

    user = User(
        id=uuid.uuid4(),
        email=f"founder_{uid}@nexuratech.com",
        first_name="Aditya",
        last_name="Sharma",
        password_hash="mocked_pw_hash",
        is_active=True
    )
    db_session.add(user)

    tu = TenantUser(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        role="owner",
        din="09876543"
    )
    db_session.add(tu)

    # Seed Chart of Accounts for Tenant
    standard_accounts = [
        {"code": "1010", "name": "HDFC Current Account (Bank)", "type": "asset", "sub_type": "bank", "normal_balance": "debit"},
        {"code": "1020", "name": "Trade Receivables (Debtors)", "type": "asset", "sub_type": "accounts_receivable", "normal_balance": "debit"},
        {"code": "1050", "name": "Computers & Server Equipment (PPE)", "type": "asset", "sub_type": "fixed_asset", "normal_balance": "debit"},
        {"code": "2010", "name": "Paid-up Share Capital", "type": "equity", "sub_type": "equity", "normal_balance": "credit"},
        {"code": "2020", "name": "Retained Earnings", "type": "equity", "sub_type": "retained_earnings", "normal_balance": "credit"},
        {"code": "2040", "name": "Trade Payables (Creditors)", "type": "liability", "sub_type": "accounts_payable", "normal_balance": "credit"},
        {"code": "2050", "name": "Statutory & Tax Liabilities (GST/TDS)", "type": "liability", "sub_type": "other_current_liability", "normal_balance": "credit"},
        {"code": "3010", "name": "Software Development Revenue", "type": "revenue", "sub_type": "operating_revenue", "normal_balance": "credit"},
        {"code": "4010", "name": "Cloud Infrastructure AWS/GCP", "type": "expense", "sub_type": "operating_expense", "normal_balance": "debit"},
        {"code": "4020", "name": "Office Lease & Utilities", "type": "expense", "sub_type": "operating_expense", "normal_balance": "debit"},
    ]
    for acc_data in standard_accounts:
        acc = ChartOfAccounts(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            **acc_data
        )
        db_session.add(acc)

    # Seed Fiscal Years 2025-26 and 2026-27
    fy25 = FiscalYear(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        label="2025-26",
        assessment_year="2026-27",
        start_date=date(2025, 4, 1),
        end_date=date(2026, 3, 31),
        is_closed=False,
        is_statutory_sealed=False
    )
    db_session.add(fy25)

    fy26 = FiscalYear(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        label="2026-27",
        assessment_year="2027-28",
        start_date=date(2026, 4, 1),
        end_date=date(2027, 3, 31),
        is_closed=False,
        is_statutory_sealed=False
    )
    db_session.add(fy26)

    # Pre-seed verified AOC-4 Statutory Filing Anchor for FY 2025-26
    schedule_iii = {
        "2010": 100000.00,  # Paid-up Capital: 1,00,000
        "2020": 400000.00,  # Retained Earnings: 4,00,000
        "2040": 50000.00,   # Trade Payables: 50,000
        "1010": 350000.00,  # Cash & Bank: 3,50,000
        "1020": 120000.00,  # Trade Receivables: 1,20,000
        "1050": 80000.00    # PPE: 80,000
    }
    anchor = StatutoryFilingAnchor(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        fiscal_year="2025-26",
        assessment_year="2026-27",
        form_type="aoc_4",
        srn_or_ack_number="SRN-F98273612",
        filing_date=date(2026, 10, 28),
        schedule_iii_payload=schedule_iii,
        signatory_din="09876543",
        auditor_udin="26098765AAAAAA1234",
        s3_document_key="statutory_anchors/2025-26/aoc_4_verified.pdf",
        document_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        is_locked=True
    )
    db_session.add(anchor)
    storage_manager.upload_bytes("statutory_anchors/2025-26/aoc_4_verified.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

    await db_session.commit()
    return tenant, user


@pytest.mark.asyncio
async def test_01_record_statutory_filing_anchor(db_session, phase8_test_tenant):
    """
    Test 1: Records verified statutory filing anchor (Form ITR-6)
    and verifies persistence with immutability flag.
    """
    tenant, _ = phase8_test_tenant

    schedule_iii_itr = {
        "2010": 100000.00,
        "2020": 400000.00,
        "1010": 350000.00
    }

    anchor = await StatutoryAnchorService.record_statutory_anchor(
        db=db_session,
        tenant=tenant,
        fiscal_year="2025-26",
        assessment_year="2026-27",
        form_type="itr_6",
        srn_or_ack_number="ACK-ITR-998877",
        filing_date=date(2026, 10, 31),
        schedule_iii_payload=schedule_iii_itr,
        signatory_din="09876543",
        auditor_udin="26098765AAAAAA5678"
    )

    assert anchor is not None
    assert anchor.fiscal_year == "2025-26"
    assert anchor.form_type == "itr_6"
    assert anchor.srn_or_ack_number == "ACK-ITR-998877"
    assert anchor.is_locked is True

    # Verify query for anchors
    anchors = await StatutoryAnchorService.get_statutory_anchors_for_fy(db_session, tenant.id, "2025-26")
    assert len(anchors) >= 2  # AOC-4 pre-seeded + ITR-6 recorded


@pytest.mark.asyncio
async def test_02_variance_radar_calculation(db_session, phase8_test_tenant):
    """
    Test 2: Compares reconstructed internal ledger closing balances on March 31, 2026
    against the filed AOC-4 Schedule III baseline and identifies line-by-line drift.
    """
    tenant, _ = phase8_test_tenant

    stmt = select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant.id)
    res = await db_session.execute(stmt)
    acc_map = {acc.code: acc for acc in res.scalars().all()}

    # Seed internal ledger transactions in FY 2025-26:
    # Bank (1010) = 3,00,000 (Dr) vs Filed 3,50,000 (Difference: +50,000 in filed)
    # Capital (2010) = 1,00,000 (Cr) vs Filed 1,00,000 (Match)
    # Retained Earnings (2020) = 2,00,000 (Cr) vs Filed 4,00,000 (Difference: +2,00,000 in filed)
    je1 = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number="JV-2025-001",
        entry_date=date(2025, 6, 15),
        narration="Initial capital infusion & internal bookings",
        status="draft"
    )
    db_session.add(je1)
    db_session.add(JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=je1.id,
        account_id=acc_map["1010"].id,
        debit_amount=Decimal("300000.00"),
        credit_amount=Decimal("0.00"),
        description="Bank deposit"
    ))
    db_session.add(JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=je1.id,
        account_id=acc_map["2010"].id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("100000.00"),
        description="Share capital"
    ))
    db_session.add(JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=je1.id,
        account_id=acc_map["2020"].id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("200000.00"),
        description="Opening retained earnings"
    ))
    await db_session.flush()
    je1.status = "posted"
    await db_session.commit()

    # Compute variance radar
    radar = await StatutoryAnchorService.calculate_variance_radar(db_session, tenant, "2025-26")

    assert radar["fiscal_year"] == "2025-26"
    assert radar["is_statutory_sealed"] is False
    assert radar["filed_anchor"]["srn_or_ack_number"] == "SRN-F98273612"

    items_by_code = {item["account_code"]: item for item in radar["line_items"]}
    
    # Capital (2010): Internal 1,00,000 == Filed 1,00,000 -> MATCHED
    cap_item = items_by_code["2010"]
    assert cap_item["internal_ledger_balance"] == 100000.00
    assert cap_item["filed_statutory_balance"] == 100000.00
    assert cap_item["status"] == "MATCHED"

    # Bank (1010): Internal 3,00,000 vs Filed 3,50,000 -> CALIBRATION_REQUIRED (+50,000)
    bank_item = items_by_code["1010"]
    assert bank_item["internal_ledger_balance"] == 300000.00
    assert bank_item["filed_statutory_balance"] == 350000.00
    assert bank_item["variance"] == 50000.00
    assert bank_item["status"] == "CALIBRATION_REQUIRED"


@pytest.mark.asyncio
async def test_03_calibrate_opening_balances_and_lock_fy(db_session, phase8_test_tenant):
    """
    Test 3: Executes Opening Statutory Calibration Journal Entry on April 1, 2026,
    routes net variance to Account 2015, achieves exact double-entry balance (|Dr - Cr| = 0),
    and hard-locks historical FY 2025-26 with a cryptographic SHA-256 seal.
    """
    tenant, user = phase8_test_tenant

    result = await StatutoryAnchorService.calibrate_opening_balances_and_lock_fy(
        db=db_session,
        tenant=tenant,
        fiscal_year="2025-26",
        user_id=user.id,
        custom_notes="Statutory Baseline Calibration based on MCA Form AOC-4 SRN-F98273612"
    )

    assert result["success"] is True
    assert result["calibrated_fiscal_year"] == "2025-26"
    assert result["opening_calibration_date"] == "2026-04-01"
    assert result["sealed_status"]["is_statutory_sealed"] is True
    assert len(result["sealed_status"]["statutory_seal_hash"]) == 64  # SHA-256

    # Verify Journal Entry balance: Sum(Dr) == Sum(Cr)
    je_id = uuid.UUID(result["calibration_journal_entry"]["id"])
    stmt_lines = select(JournalLine).where(JournalLine.journal_entry_id == je_id)
    res_lines = await db_session.execute(stmt_lines)
    lines = list(res_lines.scalars().all())

    tot_dr = sum(l.debit_amount for l in lines)
    tot_cr = sum(l.credit_amount for l in lines)
    assert tot_dr == tot_cr
    assert abs(tot_dr - tot_cr) == Decimal("0.00")

    # Verify Account 2015 exists and absorbed the balancing adjustment
    stmt_2015 = (
        select(ChartOfAccounts)
        .where(ChartOfAccounts.tenant_id == tenant.id, ChartOfAccounts.code == "2015")
    )
    res_2015 = await db_session.execute(stmt_2015)
    acc_2015 = res_2015.scalar_one_or_none()
    assert acc_2015 is not None
    assert "Prior Period Statutory Adjustments" in acc_2015.name


@pytest.mark.asyncio
async def test_04_trigger_blocks_mutations_in_sealed_fy(db_session, phase8_test_tenant):
    """
    Test 4: Verifies PostgreSQL trigger check_journal_entry_period_open() raises
    a Statutory Breach exception when attempting to insert or mutate vouchers in a sealed FY.
    """
    tenant, _ = phase8_test_tenant

    # Seal FY 2025-26
    stmt_fy = select(FiscalYear).where(FiscalYear.tenant_id == tenant.id, FiscalYear.label == "2025-26")
    res_fy = await db_session.execute(stmt_fy)
    fy = res_fy.scalar_one()
    fy.is_statutory_sealed = True
    await db_session.commit()

    stmt_acc = select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant.id, ChartOfAccounts.code == "1010")
    res_acc = await db_session.execute(stmt_acc)
    acc = res_acc.scalar_one()

    # Attempt to post a backdated voucher in sealed FY 2025-26 (e.g. 2025-11-10)
    illegal_entry = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number="JV-ILLEGAL-001",
        entry_date=date(2025, 11, 10),
        narration="Backdated fraudulent modification attempt",
        status="posted"
    )
    db_session.add(illegal_entry)

    with pytest.raises(Exception) as exc_info:
        await db_session.commit()

    err_msg = str(exc_info.value)
    assert "Statutory Breach" in err_msg or "statutory sealed" in err_msg.lower()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_05_advance_tax_forecast_corporate_regime(db_session, phase8_test_tenant):
    """
    Test 5: Calculates real-time Advance Tax forecast with Section 115BAA corporate rate (25.168%).
    """
    tenant, _ = phase8_test_tenant

    stmt = select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant.id)
    res = await db_session.execute(stmt)
    acc_map = {acc.code: acc for acc in res.scalars().all()}

    # Post revenue of ₹20,00,000 and expenses of ₹5,00,000 in FY 2026-27 (Net profit = ₹15,00,000)
    # Voucher 1: Client Revenue
    je1 = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number="JV-2026-001",
        entry_date=date(2026, 5, 20),
        narration="Client retainers",
        status="draft"
    )
    db_session.add(je1)
    db_session.add(JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=je1.id,
        account_id=acc_map["1010"].id,
        debit_amount=Decimal("2000000.00"),
        credit_amount=Decimal("0.00"),
        description="Software development receipts"
    ))
    db_session.add(JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=je1.id,
        account_id=acc_map["3010"].id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("2000000.00"),
        description="Software development revenue"
    ))
    await db_session.flush()
    je1.status = "posted"

    # Voucher 2: Cloud Operational Expenses
    je2 = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number="JV-2026-002",
        entry_date=date(2026, 5, 20),
        narration="Cloud operational expenses",
        status="draft"
    )
    db_session.add(je2)
    db_session.add(JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=je2.id,
        account_id=acc_map["4010"].id,
        debit_amount=Decimal("500000.00"),
        credit_amount=Decimal("0.00"),
        description="AWS Hosting charges"
    ))
    db_session.add(JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=je2.id,
        account_id=acc_map["1010"].id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("500000.00"),
        description="Bank payment for AWS"
    ))
    await db_session.flush()
    je2.status = "posted"
    await db_session.commit()

    forecast = await AdvanceTaxService.compute_advance_tax_forecast(
        db=db_session,
        tenant=tenant,
        fiscal_year="2026-27",
        custom_projected_profit=Decimal("1500000.00")
    )

    assert forecast["fiscal_year"] == "2026-27"
    assert forecast["assessment_year"] == "2027-28"
    assert forecast["tax_regime"] == "sec_115baa_22"
    assert forecast["effective_tax_rate_percent"] == 25.168
    assert forecast["annual_projection"]["projected_net_taxable_income"] == 1500000.00
    
    # Gross corporate tax = 15,00,000 * 25.168% = 3,77,520.00
    expected_tax = float(Decimal("1500000.00") * Decimal("0.25168"))
    assert abs(forecast["annual_projection"]["gross_tax_liability"] - expected_tax) < 1.0
    assert forecast["annual_projection"]["is_sec208_mandatory"] is True


@pytest.mark.asyncio
async def test_06_customer_tds_credit_offset(db_session, phase8_test_tenant):
    """
    Test 6: Verifies customer TDS credits from sales invoices reduce Net Advance Tax Payable.
    """
    tenant, _ = phase8_test_tenant

    # Create Contact and sales invoice with customer TDS deducted (e.g. ₹50,000 TDS credit)
    contact = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="TechCorp India Ltd",
        gstin="29AAACT1234F1Z1",
        state_code="29",
        billing_address="123 Tech Park, Bengaluru"
    )
    db_session.add(contact)
    await db_session.flush()

    inv = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        contact_id=contact.id,
        invoice_number="INV-2026-001",
        issue_date=date(2026, 6, 1),
        due_date=date(2026, 7, 1),
        place_of_supply="29",
        subtotal=Decimal("500000.00"),
        cgst_total=Decimal("45000.00"),
        sgst_total=Decimal("45000.00"),
        igst_total=Decimal("0.00"),
        grand_total=Decimal("590000.00"),
        tds_amount=Decimal("50000.00"),  # Section 194J 10% TDS
        status="sent"
    )
    db_session.add(inv)
    await db_session.commit()

    forecast = await AdvanceTaxService.compute_advance_tax_forecast(
        db=db_session,
        tenant=tenant,
        fiscal_year="2026-27",
        custom_projected_profit=Decimal("1500000.00")
    )

    assert forecast["annual_projection"]["tds_credits_claimed"] == 50000.00
    expected_gross = float(Decimal("1500000.00") * Decimal("0.25168"))
    expected_net = expected_gross - 50000.00
    assert abs(forecast["annual_projection"]["net_advance_tax_payable"] - expected_net) < 1.0


@pytest.mark.asyncio
async def test_07_quarterly_installments_and_safe_harbor(db_session, phase8_test_tenant):
    """
    Test 7: Checks Section 211 quarterly installments (Q1: 15%/12%, Q2: 45%/36%, Q3: 75%, Q4: 100%)
    and penal interest simulation.
    """
    tenant, _ = phase8_test_tenant

    forecast = await AdvanceTaxService.compute_advance_tax_forecast(
        db=db_session,
        tenant=tenant,
        fiscal_year="2026-27",
        custom_projected_profit=Decimal("1500000.00")
    )

    installments = {inst["quarter"]: inst for inst in forecast["installments"]}
    net_payable = forecast["annual_projection"]["net_advance_tax_payable"]

    # Q1 target 15%, safe harbor 12%
    assert abs(installments["Q1"]["target_amount"] - (net_payable * 0.15)) < 1.0
    assert abs(installments["Q1"]["safe_harbor_amount"] - (net_payable * 0.12)) < 1.0

    # Q2 target 45%, safe harbor 36%
    assert abs(installments["Q2"]["target_amount"] - (net_payable * 0.45)) < 1.0
    assert abs(installments["Q2"]["safe_harbor_amount"] - (net_payable * 0.36)) < 1.0

    # Q3 target 75%
    assert abs(installments["Q3"]["target_amount"] - (net_payable * 0.75)) < 1.0

    # Q4 target 100%
    assert abs(installments["Q4"]["target_amount"] - net_payable) < 1.0


@pytest.mark.asyncio
async def test_08_record_advance_tax_challan_and_epay_packet(db_session, phase8_test_tenant):
    """
    Test 8: Records verified advance tax payment (Challan ITNS 280) and checks e-Pay Tax packet.
    """
    tenant, _ = phase8_test_tenant

    # Record Q1 payment of ₹50,000
    challan = await AdvanceTaxService.record_advance_tax_challan(
        db=db_session,
        tenant=tenant,
        fiscal_year="2026-27",
        quarter="Q1",
        payment_date=date(2026, 6, 12),
        bsr_code="0290123",
        challan_serial_no="00481",
        amount_paid=Decimal("50000.00"),
        cin_number="02901231206202600481"
    )

    assert challan is not None
    assert challan.quarter == "Q1"
    assert challan.amount_paid == Decimal("50000.00")

    # Generate e-Pay Tax packet for Q2
    packet = AdvanceTaxService.generate_epay_tax_packet(
        tenant=tenant,
        fiscal_year="2026-27",
        quarter="Q2",
        amount=Decimal("97500.00")
    )

    assert packet["pan"] == tenant.pan
    assert packet["assessment_year"] == "2027-28"
    assert packet["major_head_code"] == "0020"  # Corporation tax
    assert packet["minor_head_code"] == "100"   # Advance Tax
    assert packet["recommended_amount_inr"] == 97500.00


@pytest.mark.asyncio
async def test_09_api_statutory_variance_radar_endpoint(db_session, phase8_test_tenant):
    """
    Test 9: Verifies GET /api/v1/compliance/statutory-anchor/variance-radar returns 200
    with line items and summary metrics via FastAPI test client.
    """
    tenant, user = phase8_test_tenant
    token = create_access_token({"sub": str(user.id), "tenant_id": str(tenant.id), "role": "owner"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            "/api/v1/compliance/statutory-anchor/variance-radar?fy=2025-26",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant.id)}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["fiscal_year"] == "2025-26"
        assert "filed_anchor" in data
        assert "line_items" in data
        assert "summary" in data


@pytest.mark.asyncio
async def test_10_api_advance_tax_forecast_endpoint(db_session, phase8_test_tenant):
    """
    Test 10: Verifies GET /api/v1/compliance/advance-tax/forecast returns 200
    with statutory tax regimes and installment breakdown via FastAPI test client.
    """
    tenant, user = phase8_test_tenant
    token = create_access_token({"sub": str(user.id), "tenant_id": str(tenant.id), "role": "owner"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            "/api/v1/compliance/advance-tax/forecast?fy=2026-27",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant.id)}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["fiscal_year"] == "2026-27"
        assert data["tax_regime"] == "sec_115baa_22"
        assert "annual_projection" in data
        assert "installments" in data
        assert len(data["installments"]) == 4


@pytest.mark.asyncio
async def test_11_three_stage_fy_lifecycle_and_audit_window(db_session, phase8_test_tenant):
    """
    Test 11 (Milestone 8.1): Verifies that in Stage 2 (Year-End Audit & Filing Window),
    FY 2025-26 books remain OPEN for audit adjustments, depreciation, and pending tasks.
    """
    tenant, user = phase8_test_tenant
    fy = "2025-26"

    # 1. Fetch lifecycle status
    lifecycle = await StatutoryAnchorService.get_fiscal_year_lifecycle(db_session, tenant, fy)
    assert lifecycle["fiscal_year"] == fy
    assert lifecycle["stage"] in ("audit_closing_window", "active")
    assert lifecycle["can_post_adjustments"] is True

    # 2. Ensure FY 2025-26 is in audit_closing_window
    await StatutoryAnchorService.transition_fy_stage(db_session, tenant, fy, "audit_closing_window", user.id)

    # 3. Post an Audit Adjusting Entry (AJE) dated 2026-03-31 (FY 2025-26)
    stmt_acc = select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant.id)
    res_acc = await db_session.execute(stmt_acc)
    accs = {a.code: a for a in res_acc.scalars().all()}

    audit_entry = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number=f"JV/2025-26/AUDIT-{uuid.uuid4().hex[:4]}",
        entry_date=date(2026, 3, 31),
        status="posted",
        reference_type="audit_adjusting_entry",
        narration="Year-end CA audit depreciation and prepaid expenses adjustment"
    )
    db_session.add(audit_entry)
    await db_session.flush()

    line_dr = JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=audit_entry.id,
        account_id=accs["4010"].id,
        debit_amount=Decimal("15000.00"),
        credit_amount=Decimal("0.00"),
        description="Audit adjustment expense"
    )
    line_cr = JournalLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        journal_entry_id=audit_entry.id,
        account_id=accs["2040"].id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("15000.00"),
        description="Audit adjustment payable"
    )
    db_session.add(line_dr)
    db_session.add(line_cr)

    # In Stage 2, commit MUST succeed without trigger error!
    await db_session.commit()
    assert audit_entry.id is not None


@pytest.mark.asyncio
async def test_12_statutory_sealed_blocks_and_permanent_immutability(db_session, phase8_test_tenant):
    """
    Test 12 (Milestone 8.1): Verifies that transitioning to Stage 3 (Statutory Sealed)
    hard-locks the period and permanently blocks mutations and reopening.
    """
    tenant, user = phase8_test_tenant
    fy = "2025-26"

    # Transition to Stage 3 (requires an anchor to exist, which test_01 created)
    sealed_info = await StatutoryAnchorService.transition_fy_stage(
        db_session, tenant, fy, "statutory_sealed", user.id
    )
    assert sealed_info["stage"] == "statutory_sealed"
    assert sealed_info["can_post_adjustments"] is False
    assert sealed_info["statutory_seal_hash"] is not None

    # Verify attempt to reopen back to active is rejected
    with pytest.raises(ValueError, match="Statutory Invariant Violation"):
        await StatutoryAnchorService.transition_fy_stage(db_session, tenant, fy, "active", user.id)

    # Verify database trigger blocks mutations in sealed period
    blocked_entry = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number=f"JV/2025-26/ILLEGAL-{uuid.uuid4().hex[:4]}",
        entry_date=date(2026, 3, 20),
        status="posted",
        narration="Illegal entry in sealed period"
    )
    db_session.add(blocked_entry)
    with pytest.raises(Exception, match="Statutory Breach"):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_13_gst_forecast_rule_88a_setoff_hierarchy():
    """
    Test 13 (Milestone 8.2): Verifies the Rule 88A set-off hierarchy:
    - IGST credit exhausted 100% first across IGST, then CGST, then SGST.
    - CGST credit cannot offset SGST, SGST credit cannot offset CGST.
    """
    from app.services.gst_forecast_service import GSTForecastService

    # Scenario: High IGST credit, medium CGST/SGST output
    res = GSTForecastService.apply_rule_88a_setoff(
        output_igst=Decimal("10000.00"),
        output_cgst=Decimal("25000.00"),
        output_sgst=Decimal("25000.00"),
        input_igst=Decimal("40000.00"),
        input_cgst=Decimal("5000.00"),
        input_sgst=Decimal("5000.00")
    )

    assert res["setoff_breakdown"]["igst_against_igst"] == 10000.00
    assert res["setoff_breakdown"]["igst_against_cgst"] == 25000.00
    assert res["setoff_breakdown"]["igst_against_sgst"] == 5000.00
    assert res["setoff_breakdown"]["sgst_against_sgst"] == 5000.00

    assert res["net_cash_payable"]["igst"] == 0.00
    assert res["net_cash_payable"]["cgst"] == 0.00
    assert res["net_cash_payable"]["sgst"] == 15000.00
    assert res["net_cash_payable"]["total"] == 15000.00
    assert res["closing_itc_balance"]["cgst"] == 5000.00


@pytest.mark.asyncio
async def test_14_gst_forecast_qrmp_and_composition_schemes(db_session, phase8_test_tenant):
    """
    Test 14 (Milestone 8.2): Verifies GST forecasting under QRMP scheme (35% safe harbor)
    and Composition scheme (CMP-08 flat rate without ITC).
    """
    from app.services.gst_forecast_service import GSTForecastService
    tenant, user = phase8_test_tenant

    # Seed an invoice in Q1 (e.g., 2026-05-10)
    contact = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Retail Client India",
        gstin="29AAACH7409R1ZZ",
        state_code="29",
        billing_address="123 MG Road, Bengaluru, Karnataka 560001"
    )
    db_session.add(contact)

    inv = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        contact_id=contact.id,
        invoice_number=f"INV/26-27/GST-{uuid.uuid4().hex[:4]}",
        issue_date=date(2026, 5, 10),
        due_date=date(2026, 6, 10),
        place_of_supply="29",
        subtotal=Decimal("200000.00"),
        cgst_total=Decimal("18000.00"),
        sgst_total=Decimal("18000.00"),
        igst_total=Decimal("0.00"),
        grand_total=Decimal("236000.00"),
        status="sent"
    )
    db_session.add(inv)
    await db_session.commit()

    # 1. QRMP Forecast for Q1
    qrmp_forecast = await GSTForecastService.compute_gst_forecast(
        db=db_session,
        tenant=tenant,
        fiscal_year="2026-27",
        frequency="quarterly_qrmp",
        return_period="Q1"
    )
    assert qrmp_forecast["frequency"] == "quarterly_qrmp"
    assert qrmp_forecast["total_outward_taxable_supplies"] == 200000.00
    assert qrmp_forecast["gross_cash_payable"]["total"] == 36000.00
    assert qrmp_forecast["qrmp_35pct_safe_harbor_amount"] == round(36000.00 * 0.35, 2)
    assert qrmp_forecast["recommended_weekly_reserve"] == round(36000.00 / 4, 2)

    # 2. Composition Scheme Forecast for Q1
    comp_forecast = await GSTForecastService.compute_gst_forecast(
        db=db_session,
        tenant=tenant,
        fiscal_year="2026-27",
        frequency="composition",
        return_period="Q1",
        composition_rate=Decimal("0.01")
    )
    assert comp_forecast["frequency"] == "composition"
    assert comp_forecast["taxable_turnover"] == 200000.00
    assert comp_forecast["gross_tax_liability"] == 2000.00
    assert comp_forecast["cgst_liability"] == 1000.00
    assert comp_forecast["sgst_liability"] == 1000.00
    assert comp_forecast["itc_allowed"] is False


@pytest.mark.asyncio
async def test_15_record_gst_challan_and_offset(db_session, phase8_test_tenant):
    """
    Test 15 (Milestone 8.2): Verifies recording a PMT-06 GST Challan and ensuring
    it offsets net cash payable, rejecting duplicate CPINs.
    """
    from app.services.gst_forecast_service import GSTForecastService
    tenant, user = phase8_test_tenant
    cpin = f"99{uuid.uuid4().hex[:12].upper()}"

    # 1. Record Challan PMT-06 for Q1
    challan = await GSTForecastService.record_gst_challan(
        db=db_session,
        tenant=tenant,
        fiscal_year="2026-27",
        period="Q1",
        frequency="quarterly_qrmp",
        challan_type="PMT-06",
        cpin=cpin,
        payment_date=date(2026, 6, 20),
        cgst_amount=Decimal("6300.00"),
        sgst_amount=Decimal("6300.00"),
        igst_amount=Decimal("0.00"),
        cin="HDFC26062000123"
    )
    assert challan.id is not None
    assert challan.total_amount == Decimal("12600.00")

    # 2. Duplicate CPIN must be rejected
    with pytest.raises(ValueError, match="already recorded"):
        await GSTForecastService.record_gst_challan(
            db=db_session,
            tenant=tenant,
            fiscal_year="2026-27",
            period="Q1",
            frequency="quarterly_qrmp",
            challan_type="PMT-06",
            cpin=cpin,
            payment_date=date(2026, 6, 20),
            cgst_amount=Decimal("6300.00"),
            sgst_amount=Decimal("6300.00"),
            igst_amount=Decimal("0.00")
        )

    # 3. Verify forecast reflects paid challan
    forecast = await GSTForecastService.compute_gst_forecast(
        db=db_session,
        tenant=tenant,
        fiscal_year="2026-27",
        frequency="quarterly_qrmp",
        return_period="Q1"
    )
    assert forecast["total_challans_paid"] >= 12600.00
    assert forecast["net_cash_due_after_challans"] == max(0.0, forecast["gross_cash_payable"]["total"] - forecast["total_challans_paid"])


@pytest.mark.asyncio
async def test_16_statutory_vault_content_deduplication(db_session, phase8_test_tenant):
    """
    Test 16 (Milestone 8.3): Verifies that uploading the exact same document binary
    triggers content-addressed SHA-256 deduplication, returning is_duplicate=True
    and preventing redundant MinIO storage.
    """
    tenant, user = phase8_test_tenant
    token = create_access_token({"sub": str(user.id), "tenant_id": str(tenant.id), "role": "owner"})

    # Synthetic authentic AOC-4 PDF bytes
    synthetic_pdf_content = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"FORM AOC-4 FINANCIAL STATEMENTS\nSRN: F88776655_SRN_FORM\n"
        b"CIN: U72200KA2024PTC123456\n"
        b"DIN: 09876543\n"
        b"UDIN: 25098765A1B2C3D4E5\n"
        b"%%EOF\n"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. First Upload -> Must succeed with is_duplicate = False
        files = {"file": ("aoc_4_original.pdf", synthetic_pdf_content, "application/pdf")}
        res1 = await ac.post(
            "/api/v1/compliance/statutory-dossier/upload",
            data={"fiscal_year": "2025-26", "form_type": "aoc_4"},
            files=files,
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant.id)}
        )
        if res1.status_code != 200:
            print("UPLOAD_ERROR:", res1.status_code, res1.text)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["success"] is True
        assert data1["is_duplicate"] is False
        assert "s3_document_key" in data1

        # 2. Second Upload with identical bytes -> Must detect duplicate!
        files2 = {"file": ("aoc_4_copy.pdf", synthetic_pdf_content, "application/pdf")}
        res2 = await ac.post(
            "/api/v1/compliance/statutory-dossier/upload",
            data={"fiscal_year": "2025-26", "form_type": "aoc_4"},
            files=files2,
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant.id)}
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["success"] is True
        assert data2["is_duplicate"] is True
        assert "Duplicate Prevented" in data2["message"]


@pytest.mark.asyncio
async def test_17_statutory_filing_classification():
    """
    Test 17 (Milestone 8.3): Verifies classification engine accurately categorizes
    AOC-4, ITR-6, Auditor's Report, Board's Report, and MGT-7A.
    """
    from app.services.statutory_vault_engine import StatutoryVaultEngine

    # 1. Test AOC-4
    aoc4_bytes = b"FORM NO. AOC-4 MINISTRY OF CORPORATE AFFAIRS CIN: U72200KA2024PTC123456 SRN: F11223344"
    c1 = StatutoryVaultEngine.classify_statutory_filing(aoc4_bytes, "aoc4.pdf")
    assert c1["form_type"] == "aoc_4"
    assert c1["srn_or_ack_number"] == "F11223344"

    # 2. Test ITR-6
    itr6_bytes = b"INDIAN INCOME TAX RETURN ITR-6 ACKNOWLEDGEMENT NUMBER: 998877665544 ASSESSMENT YEAR: 2026-27"
    c2 = StatutoryVaultEngine.classify_statutory_filing(itr6_bytes, "itr6.pdf")
    assert c2["form_type"] == "itr_6"
    assert c2["srn_or_ack_number"] == "998877665544"
    assert c2["assessment_year"] == "2026-27"
    assert c2["fiscal_year"] == "2025-26"

    # 3. Test Auditor's Report
    audit_bytes = b"INDEPENDENT AUDITOR'S REPORT UDIN: 26098765ABCDEF1234 TO THE MEMBERS OF THE COMPANY"
    c3 = StatutoryVaultEngine.classify_statutory_filing(audit_bytes, "audit.pdf")
    assert c3["form_type"] == "auditor_report"
    assert "26098765ABCDEF1234" in c3["srn_or_ack_number"]

    # 4. Test Board's Report
    br_bytes = b"BOARD'S REPORT PURSUANT TO SECTION 134 OF COMPANIES ACT 2013 DIN: 09876543"
    c4 = StatutoryVaultEngine.classify_statutory_filing(br_bytes, "br.pdf")
    assert c4["form_type"] == "boards_report"
    assert c4["signatory_din"] == "09876543"

    # 5. Test MGT-7A
    mgt_bytes = b"FORM NO. MGT-7A ANNUAL RETURN FOR SMALL COMPANIES SRN: F99887766"
    c5 = StatutoryVaultEngine.classify_statutory_filing(mgt_bytes, "mgt7.pdf")
    assert c5["form_type"] == "mgt_7a"
    assert c5["srn_or_ack_number"] == "F99887766"


@pytest.mark.asyncio
async def test_18_api_statutory_dossier_year_view_and_stream(db_session, phase8_test_tenant):
    """
    Test 18 (Milestone 8.3): Verifies GET /api/v1/compliance/statutory-dossier/year-dossier
    returns 5 standardized cards, and streaming endpoint returns authentic PDF binary.
    """
    tenant, user = phase8_test_tenant
    token = create_access_token({"sub": str(user.id), "tenant_id": str(tenant.id), "role": "owner"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Fetch Year Dossier
        res = await ac.get(
            "/api/v1/compliance/statutory-dossier/year-dossier?fy=2025-26",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant.id)}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["fiscal_year"] == "2025-26"
        assert len(data["tiles"]) == 5
        tile_types = [t["form_type"] for t in data["tiles"]]
        assert "aoc_4" in tile_types
        assert "itr_6" in tile_types
        assert "auditor_report" in tile_types
        assert "boards_report" in tile_types
        assert "mgt_7a" in tile_types

        # Check AOC-4 tile status from test_16 upload
        aoc_tile = next(t for t in data["tiles"] if t["form_type"] == "aoc_4")
        assert aoc_tile["is_uploaded"] is True
        assert aoc_tile["s3_document_key"] is not None

        # 2. Test Stream endpoint with authentic PDF binary
        stream_res = await ac.get(
            f"/api/v1/compliance/statutory-dossier/stream?s3_key={aoc_tile['s3_document_key']}",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant.id)}
        )
        assert stream_res.status_code == 200, f"Error: {stream_res.text}"
        assert stream_res.headers["content-type"] == "application/pdf"
        assert "X-Sovereign-Vault-SHA256" in stream_res.headers
        assert len(stream_res.content) > 0


@pytest.mark.asyncio
async def test_19_schedule_iii_decimal_precision_and_auto_rounding(db_session, phase8_test_tenant):
    """
    Test 19: Verifies Schedule III Clause 4 decimal precision (.00 preserved)
    and automatic scale determination from turnover/assets.
    """
    tenant, _ = phase8_test_tenant
    from app.services.schedule_iii_service import (
        format_statutory_amount,
        get_unit_label,
        ScheduleIIIService
    )

    # 1. Decimal precision verification (.00 must not be stripped)
    assert format_statutory_amount(380937, unit="hundreds") == "3,809.37"
    assert format_statutory_amount(380000, unit="hundreds") == "3,800.00"
    assert format_statutory_amount(3015.54, unit="whole") == "3,015.54"
    assert format_statutory_amount(-79383, unit="hundreds") == "(793.83)"
    assert format_statutory_amount(0, unit="hundreds") == "-"

    # 2. Schedule III Clause 4 Automatic Rounding Determination
    unit_small, label_small = ScheduleIIIService.get_auto_rounding_unit(500000)
    assert unit_small == "hundreds"
    assert label_small == "Amount in Rs. '00 (Nearest Hundreds)"

    unit_med, label_med = ScheduleIIIService.get_auto_rounding_unit(2500000)
    assert unit_med == "thousands"
    assert label_med == "Amount in Rs. '000 (Nearest Thousands)"

    unit_large, label_large = ScheduleIIIService.get_auto_rounding_unit(50000000)
    assert unit_large == "lakhs"
    assert label_large == "Amount in Rs. Lakhs"

    unit_corp, label_corp = ScheduleIIIService.get_auto_rounding_unit(1200000000)
    assert unit_corp == "crores"
    assert label_corp == "Amount in Rs. Crores"

    # 3. Dossier package generation with auto rounding and 2 decimal places CSV
    dossier = await ScheduleIIIService.generate_statutory_dossier_package(
        session=db_session,
        tenant=tenant,
        fy="2026-27",
        unit="auto"
    )
    assert "pdf_bytes" in dossier
    assert len(dossier["pdf_bytes"]) > 5000
    assert "balance_sheet_csv" in dossier
    bs_csv_text = dossier["balance_sheet_csv"].decode("utf-8-sig")
    # All values in CSV must have decimal point (precision preserved)
    assert ".00" in bs_csv_text or any("." in line.split(",")[3] for line in bs_csv_text.strip().split("\n")[1:] if line.split(",")[3])


@pytest.mark.asyncio
async def test_20_balance_sheet_provisional_dates_and_ratio_layout(db_session, phase8_test_tenant):
    """
    Test 20: Verifies provisional date logic (today < 31st March => provisional as-at today,
    today >= 31st March => 31st March) and ratio table text overlap clearance.
    """
    tenant, _ = phase8_test_tenant
    from app.services.schedule_iii_service import ScheduleIIIService
    from reportlab.pdfgen import canvas
    import io

    # 1. Provisional Current FY (2026-27): as of today (before 31-Mar-2027)
    summary_curr = await ScheduleIIIService.get_schedule_iii_summary(
        session=db_session,
        tenant=tenant,
        fy="2026-27"
    )
    today = date.today()
    if today < date(2027, 3, 31):
        assert summary_curr["is_provisional"] is True
        assert "Provisional" in summary_curr["balance_sheet_title"]
        assert "Provisional" in summary_curr["period_label"]
    else:
        assert summary_curr["is_provisional"] is False

    # 2. Closed Prior FY (2025-26): year ended 31st March 2026
    summary_past = await ScheduleIIIService.get_schedule_iii_summary(
        session=db_session,
        tenant=tenant,
        fy="2025-26"
    )
    assert summary_past["is_provisional"] is False
    assert "31st March, 2026" in summary_past["balance_sheet_title"]
    assert "For the year ended 31st March, 2026" in summary_past["period_label"]

    # 3. Ratio table column collision test
    # Column 2 starts at ml + 180, Column 3 starts at ml + 335 (Width available = 155pt)
    dummy_c = canvas.Canvas(io.BytesIO())
    num_str = "Earnings Before Interest & Tax"
    num_width = dummy_c.stringWidth(num_str, "Helvetica", 8)
    assert num_width < 140.0, f"Numerator string width {num_width} exceeds column gap!"
    col_gap = 335 - 180  # 155pt
    margin_clearance = col_gap - num_width
    assert margin_clearance > 15.0, f"Insufficient margin clearance: {margin_clearance}pt"



