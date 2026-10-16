"""
b00k5 - Phase 7 Integration Test Suite: Advanced Statutory Compliance & Multi-Entity Expansion
Tests:
1. Direct GSTR-2B Monthly JSON Reconciliation Engine (Sec 16(2)(aa) & Sec 17(5) CGST Act, 2017)
2. MCA Secretarial Standards for Limited Liability Partnerships (Form 11, Form 8, Partner Meetings)
3. Real-time Section 40A(3) Income Tax Act Daily Cash Threshold Watchdog & Form 3CD Tax Audit Annexure
"""

import pytest
import uuid
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import select

from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.tenant import Tenant, User, TenantUser
from app.models.expense import Expense
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.gstr2b_reconciler import GSTR2BReconciler
from app.services.llp_secretarial_service import LLPSecretarialService
from app.services.compliance_watchdog import ComplianceWatchdogService

DATABASE_URL = settings.DATABASE_URL

@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()

@pytest.fixture
async def phase7_test_tenant(db_session):
    """Creates a deterministic multi-entity test tenant (LLP) for Phase 7."""
    import random
    import string
    uid = uuid.uuid4().hex[:6]
    rand_alpha = ''.join(random.choices(string.ascii_uppercase, k=4))
    pan_digits = f"{random.randint(1000, 9999)}"
    pan_letter = random.choice(string.ascii_uppercase)
    pan = f"A{rand_alpha}{pan_digits}{pan_letter}"
    gstin = f"29{pan}1Z5"
    cin = f"AAB-{pan_digits}-{uuid.uuid4().hex[:4].upper()}"

    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name=f"Vanguard Logistics LLP {uid}",
        trade_name="Vanguard Logistics",
        cin=cin,
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="404 Sovereign Tower, Bengaluru, Karnataka 560001",
        statutory_profile={
            "entity_type": "Limited Liability Partnership (LLP)",
            "llpin": f"AAB-{pan_digits}",
            "registered_address": "404 Sovereign Tower, Bengaluru, Karnataka 560001",
            "partners": [
                {
                    "name": "Adithya Khamithkar",
                    "din": "09876543",
                    "dpin": "09876543",
                    "is_designated": True,
                    "contribution_inr": "50000.00",
                    "profit_sharing_ratio": "50.00"
                },
                {
                    "name": "Co-Partner Partner",
                    "din": "09876544",
                    "dpin": "09876544",
                    "is_designated": True,
                    "contribution_inr": "50000.00",
                    "profit_sharing_ratio": "50.00"
                }
            ]
        }
    )
    db_session.add(tenant)

    user = User(
        id=uuid.uuid4(),
        email=f"partner_{uid}@vanguard.llp",
        first_name="Adithya",
        last_name="Khamithkar",
        password_hash="dummy_hash_for_test_2026",
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
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant, user


# ============================================================================
# 1. GSTR-2B JSON RECONCILIATION ENGINE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_gstr2b_reconciliation_exact_and_fuzzy_matches(db_session, phase7_test_tenant):
    tenant, user = phase7_test_tenant

    # 1. Seed two recorded expenses in books
    # Expense 1: Matches GSTR-2B perfectly (AWS Cloud Hosting)
    exp1 = Expense(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=user.id,
        merchant_name="Amazon Web Services India Pvt Ltd",
        merchant_gstin="29AABCA1234A1Z5",
        expense_date=date(2026, 5, 10),
        total_amount=Decimal("11800.00"),
        cgst_amount=Decimal("900.00"),
        sgst_amount=Decimal("900.00"),
        igst_amount=Decimal("0.00"),
        category="[4010] Cloud Infrastructure & Hosting (AWS/GCP)",
        notes="Tax Invoice INV-2026-AWS-001",
        status="approved"
    )
    # Expense 2: Tax Mismatch (Book CGST=500, but 2B has CGST=900)
    exp2 = Expense(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=user.id,
        merchant_name="Zoom Video Communications",
        merchant_gstin="29ZOOM1234F1Z8",
        expense_date=date(2026, 5, 12),
        total_amount=Decimal("11800.00"),
        cgst_amount=Decimal("500.00"),
        sgst_amount=Decimal("500.00"),
        igst_amount=Decimal("0.00"),
        category="[4020] Software Licenses & SaaS Subscriptions",
        notes="Invoice INV-ZOOM-2026",
        status="approved"
    )
    # Expense 3: Missing in GSTR-2B (Book expense, supplier never filed)
    exp3 = Expense(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=user.id,
        merchant_name="Unregistered Office Supplies",
        merchant_gstin="29XYZAB9999K1Z2",
        expense_date=date(2026, 5, 15),
        total_amount=Decimal("5900.00"),
        cgst_amount=Decimal("450.00"),
        sgst_amount=Decimal("450.00"),
        igst_amount=Decimal("0.00"),
        category="[4060] Office Equipment, Computers & IT Hardware",
        notes="Invoice INV-SUPPLY-44",
        status="approved"
    )
    db_session.add_all([exp1, exp2, exp3])
    await db_session.commit()

    # 2. Construct mock official GSTR-2B payload
    gstr2b_payload = {
        "gstin": tenant.gstin,
        "fp": "052026",
        "data": {
            "b2b": [
                {
                    "ctin": "29AABCA1234A1Z5", # AWS
                    "cfs": "Y",
                    "inv": [
                        {
                            "inum": "INV-2026-AWS-001",
                            "idt": "10-05-2026",
                            "val": 11800.00,
                            "pos": "29",
                            "itcavl": "Y",
                            "items": [
                                {
                                    "txval": 10000.00,
                                    "camt": 900.00,
                                    "samt": 900.00,
                                    "iamt": 0.00
                                }
                            ]
                        }
                    ]
                },
                {
                    "ctin": "29ZOOM1234F1Z8", # Zoom
                    "cfs": "Y",
                    "inv": [
                        {
                            "inum": "INV-ZOOM-2026",
                            "idt": "12-05-2026",
                            "val": 11800.00,
                            "pos": "29",
                            "itcavl": "Y",
                            "items": [
                                {
                                    "txval": 10000.00,
                                    "camt": 900.00,
                                    "samt": 900.00,
                                    "iamt": 0.00
                                }
                            ]
                        }
                    ]
                },
                {
                    "ctin": "29HOTEL1234F1Z1", # Missing in Books (Unclaimed ITC!)
                    "cfs": "Y",
                    "inv": [
                        {
                            "inum": "HTL-9988",
                            "idt": "20-05-2026",
                            "val": 7080.00,
                            "pos": "29",
                            "itcavl": "Y",
                            "items": [
                                {
                                    "txval": 6000.00,
                                    "camt": 540.00,
                                    "samt": 540.00,
                                    "iamt": 0.00
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }

    parsed = GSTR2BReconciler.parse_gstr2b_json(gstr2b_payload)
    assert parsed["total_records"] == 3
    assert parsed["recipient_gstin"] == tenant.gstin.upper()

    # Execute reconciliation against books
    report = await GSTR2BReconciler.reconcile_against_books(
        db=db_session,
        tenant=tenant,
        parsed_2b=parsed,
        auto_update_eligible_itc=True
    )

    summary = report["reconciliation_summary"]
    # 1 Matched (AWS), 1 Tax Mismatch (Zoom), 1 Missing in Books (Hotel)
    assert summary["matched_count"] == 1
    assert summary["tax_mismatch_count"] == 1
    assert summary["missing_in_books_count"] == 1
    # Expense 3 was in books but not in 2B
    assert summary["missing_in_2b_count"] >= 1

    # Check auto-update of eligible ITC
    await db_session.refresh(exp1)
    assert exp1.itc_eligible is True
    assert exp1.has_company_gstin is True


@pytest.mark.asyncio
async def test_gstr2b_blocked_credit_sec17_5(db_session, phase7_test_tenant):
    tenant, user = phase7_test_tenant

    # Seed an expense in books for food/beverages (Section 17(5) blocked credit)
    exp_food = Expense(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=user.id,
        merchant_name="Luxury Dining & Catering Services",
        merchant_gstin="29FOODS1234F1Z3",
        expense_date=date(2026, 5, 18),
        total_amount=Decimal("5900.00"),
        cgst_amount=Decimal("450.00"),
        sgst_amount=Decimal("450.00"),
        category="Food & Staff Welfare",
        notes="Invoice INV-FOOD-001",
        status="approved"
    )
    db_session.add(exp_food)
    await db_session.commit()

    gstr2b_payload = {
        "gstin": tenant.gstin,
        "fp": "052026",
        "data": {
            "b2b": [
                {
                    "ctin": "29FOODS1234F1Z3",
                    "cfs": "Y",
                    "inv": [
                        {
                            "inum": "INV-FOOD-001",
                            "idt": "18-05-2026",
                            "val": 5900.00,
                            "pos": "29",
                            "itcavl": "Y",
                            "items": [
                                {
                                    "txval": 5000.00,
                                    "camt": 450.00,
                                    "samt": 450.00,
                                    "iamt": 0.00
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }

    parsed = GSTR2BReconciler.parse_gstr2b_json(gstr2b_payload)
    report = await GSTR2BReconciler.reconcile_against_books(db_session, tenant, parsed)

    # Even though it appears in 2B, Section 17(5) blocks food and beverages
    assert len(report["blocked_credit"]) == 1
    assert "Section 17(5)" in report["blocked_credit"][0]["reason"]


# ============================================================================
# 2. MCA SECRETARIAL STANDARDS FOR LIMITED LIABILITY PARTNERSHIPS (LLPs)
# ============================================================================

@pytest.mark.asyncio
async def test_llp_entity_detection_and_partners_roster(db_session, phase7_test_tenant):
    tenant, _ = phase7_test_tenant

    assert LLPSecretarialService.is_llp_entity(tenant) is True

    partners = await LLPSecretarialService.get_designated_partners(db_session, tenant)
    assert len(partners) >= 2
    assert any(p["dpin"] == "09876543" for p in partners)
    assert any(p["is_designated"] for p in partners)


@pytest.mark.asyncio
async def test_llp_form11_annual_return_packet(db_session, phase7_test_tenant):
    tenant, _ = phase7_test_tenant

    packet = await LLPSecretarialService.generate_form11_packet(db_session, tenant, fy="2025-26")
    assert packet["form_name"] == "Form 11 (Annual Return of Limited Liability Partnership)"
    assert packet["statutory_due_date"] == "2026-05-30"
    assert packet["fine_per_day_inr"] == Decimal("100.00")
    # Small LLP turnover does not trigger CS certification
    assert packet["requires_cs_certification"] is False
    assert "Exempt from PCS Certification" in packet["certification_trigger_reason"]
    assert len(packet["partners_summary"]["partners_roster"]) >= 2


@pytest.mark.asyncio
async def test_llp_form8_statement_of_account_and_solvency(db_session, phase7_test_tenant):
    tenant, _ = phase7_test_tenant

    packet = await LLPSecretarialService.generate_form8_packet(db_session, tenant, fy="2025-26")
    assert packet["form_name"] == "Form 8 (Statement of Account & Solvency)"
    assert packet["statutory_due_date"] == "2026-10-30"
    assert packet["fine_per_day_inr"] == Decimal("100.00")
    assert packet["audit_required"] is False
    assert "Exempt from Statutory Audit" in packet["audit_reason"]

    # Verify Solvency Statement & Statement of Account
    solvency = packet["solvency_statement"]
    assert solvency["solvency_confirmed"] is True
    assert "able to pay its debts" in solvency["statutory_declaration"]

    account = packet["statement_of_account"]
    assert "statement_of_assets_and_liabilities" in account
    assert "statement_of_income_and_expenditure" in account


@pytest.mark.asyncio
async def test_llp_partners_meeting_resolution_draft(phase7_test_tenant):
    tenant, _ = phase7_test_tenant

    res = LLPSecretarialService.generate_partners_resolution_draft(
        tenant=tenant,
        resolution_type="approval_of_accounts",
        fy="2025-26",
        designated_partners=[{"name": "Adithya Khamithkar"}]
    )
    assert "Approval of Statement of Account & Solvency (Form 8)" in res["subject"]
    assert "Adithya Khamithkar" in res["resolution_text"]
    assert res["resolution_id"].startswith("RES-LLP-")


@pytest.mark.asyncio
async def test_llp_compliance_calendar_and_cadence_watchdog(db_session, phase7_test_tenant):
    tenant, _ = phase7_test_tenant

    # Test seed milestones generates Form 11 and Form 8 for LLP
    events = await ComplianceWatchdogService.seed_initial_statutory_milestones(
        session=db_session,
        tenant_id=tenant.id,
        entity_type="llp"
    )
    categories = [e.category for e in events]
    assert "llp_form_11" in categories
    assert "llp_form_8" in categories
    assert "partner_meeting" in categories
    # INC-20A should not be generated for LLP
    assert "inc_20a" not in categories

    # Test evaluate_board_meeting_cadence recognizes LLP governance
    cadence = ComplianceWatchdogService.evaluate_board_meeting_cadence(
        entity_type="llp"
    )
    assert cadence["status"] == "llp_partner_governance"
    assert cadence["entity_type"] == "llp"
    assert cadence["is_violation"] is False


# ============================================================================
# 3. REAL-TIME SECTION 40A(3) WATCHDOG & FORM 3CD TAX AUDIT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_sec40a3_single_payment_limit(db_session, phase7_test_tenant):
    tenant, _ = phase7_test_tenant
    test_date = date(2026, 6, 1)

    # 1. Payment under ₹10,000 passes
    res_ok = await ComplianceWatchdogService.check_sec40a3_daily_cash_limit_async(
        db=db_session,
        tenant_id=tenant.id,
        expense_date=test_date,
        payee_name="Quick Office Stationery",
        new_cash_amount=Decimal("8500.00")
    )
    assert res_ok["is_disallowed"] is False
    assert res_ok["disallowed_amount"] == Decimal("0.00")

    # 2. Payment over ₹10,000 fails
    res_viol = await ComplianceWatchdogService.check_sec40a3_daily_cash_limit_async(
        db=db_session,
        tenant_id=tenant.id,
        expense_date=test_date,
        payee_name="Quick Office Stationery",
        new_cash_amount=Decimal("12500.00")
    )
    assert res_viol["is_disallowed"] is True
    assert res_viol["disallowed_amount"] == Decimal("12500.00")
    assert "STATUTORY DISALLOWANCE WARNING [Sec 40A(3)]" in res_viol["message"]


@pytest.mark.asyncio
async def test_sec40a3_aggregate_split_payments_in_day(db_session, phase7_test_tenant):
    tenant, user = phase7_test_tenant
    test_date = date(2026, 6, 5)

    # First voucher: ₹6,000 cash paid to Vendor Alpha
    v1 = Expense(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=user.id,
        merchant_name="Vendor Alpha",
        expense_date=test_date,
        total_amount=Decimal("6000.00"),
        payment_mode="cash",
        category="[4050] Rent & Office Utilities",
        status="approved"
    )
    db_session.add(v1)
    await db_session.commit()

    # Second voucher on same date to same vendor for ₹5,000 cash:
    # 6000 + 5000 = 11000 (> 10000 threshold!)
    res = await ComplianceWatchdogService.check_sec40a3_daily_cash_limit_async(
        db=db_session,
        tenant_id=tenant.id,
        expense_date=test_date,
        payee_name="Vendor Alpha",
        new_cash_amount=Decimal("5000.00")
    )
    assert res["is_disallowed"] is True
    assert res["aggregate_cash_in_day"] == Decimal("11000.00")
    assert res["disallowed_amount"] == Decimal("11000.00")


@pytest.mark.asyncio
async def test_sec40a3_goods_carriage_and_rule_6dd(db_session, phase7_test_tenant):
    tenant, _ = phase7_test_tenant
    test_date = date(2026, 6, 10)

    # 1. Goods carriage threshold is ₹35,000
    res_transport = await ComplianceWatchdogService.check_sec40a3_daily_cash_limit_async(
        db=db_session,
        tenant_id=tenant.id,
        expense_date=test_date,
        payee_name="National Transport Fleet",
        new_cash_amount=Decimal("25000.00"),
        is_goods_carriage=True
    )
    assert res_transport["is_disallowed"] is False
    assert res_transport["threshold_limit"] == Decimal("35000.00")

    # 2. Rule 6DD Exemption (e.g. Government Tax Challan)
    res_exempt = await ComplianceWatchdogService.check_sec40a3_daily_cash_limit_async(
        db=db_session,
        tenant_id=tenant.id,
        expense_date=test_date,
        payee_name="Income Tax Department Challan",
        new_cash_amount=Decimal("45000.00"),
        rule_6dd_exemption="government_tax_challan"
    )
    assert res_exempt["is_disallowed"] is False
    assert res_exempt["rule_6dd_exempt"] is True


@pytest.mark.asyncio
async def test_sec40a3_fiscal_year_audit_form_3cd(db_session, phase7_test_tenant):
    tenant, user = phase7_test_tenant

    # Seed one violating cash voucher in FY 2025-26
    v_viol = Expense(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        employee_id=user.id,
        merchant_name="Mega Cash Supplies",
        expense_date=date(2025, 8, 20),
        total_amount=Decimal("18500.00"),
        payment_mode="cash",
        category="[4060] Office Equipment",
        status="approved"
    )
    db_session.add(v_viol)
    await db_session.commit()

    report = await ComplianceWatchdogService.audit_sec40a3_fiscal_year(
        db=db_session,
        tenant_id=tenant.id,
        fy="2025-26"
    )

    assert report["financial_year"] == "2025-26"
    assert report["statutory_form"] == "Form 3CD Clause 21(d) Tax Audit Report"
    assert report["total_violations_count"] >= 1
    assert report["total_disallowed_amount_inr"] >= Decimal("18500.00")
    viol = next(item for item in report["disallowed_items"] if item["payee_name"] == "Mega Cash Supplies")
    assert viol["aggregate_cash_amount"] == Decimal("18500.00")
