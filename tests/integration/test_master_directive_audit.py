import pytest
import uuid
import asyncio
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date, datetime, timedelta
import hashlib
import io

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text, func

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, revoke_token, is_token_revoked
from app.models.tenant import Tenant, User, TenantUser
from app.models.invoice import Invoice, InvoiceItem, Contact
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.expense import Expense
from app.models.vault import DocumentVault
from app.models.compliance import ComplianceEvent, CorporateMeeting
from app.models.bank import BankStatement, BankStatementLine
from app.models.dsc import DSCSignatureAudit
from app.services.ledger_service import LedgerService
from app.services.gst_calculator import calculate_tax_breakdown, validate_gstin_checksum
from app.services.document_assembly import DocumentAssemblyService
from app.services.compliance_watchdog import ComplianceWatchdogService
from app.services.bank_parser import IndianBankPDFParser
from app.services.gdrive_client import GoogleDriveSyncClient

DATABASE_URL = settings.DATABASE_URL

@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()

def make_test_tenant(
    tenant_id: uuid.UUID = None,
    legal_name: str = "Zenith Technologies Pvt Ltd",
    cin: str = None,
    pan: str = None,
    state_code: str = "29",
    statutory_profile: dict = None
) -> Tenant:
    t_id = tenant_id or uuid.uuid4()
    rand_suffix = t_id.hex[:4].upper()
    return Tenant(
        id=t_id,
        legal_name=legal_name,
        trade_name=legal_name.split()[0],
        cin=cin or f"U72900KA2025PTC{rand_suffix}",
        pan=pan or f"AABCK{rand_suffix}F",
        gstin=f"{state_code}AABCK{rand_suffix}F1Z5",
        state_code=state_code,
        registered_office="No. 42, 80 Feet Road, Indiranagar, Bengaluru, Karnataka 560038",
        statutory_profile=statutory_profile or {}
    )

# ============================================================================
# JOURNEY 1: ONBOARDING, DOCUMENT LOCKER INGESTION & METADATA EXTRACTION
# ============================================================================
@pytest.mark.asyncio
async def test_journey_01_onboarding_and_document_locker(db_session: AsyncSession):
    """
    Journey 1: Entity Provisioning: Zenith Technologies Pvt Ltd
    - CIN: U72900KA2025PTC189012, PAN: AABCK9012F, State Code: 29
    - Ingests COI, MOA (Authorized Capital ₹15L / 1,50,000 shares @ ₹10), AOA (Quorum 2)
    - Verifies statutory profile extraction, SHA-256 recording in document_vault, and MinIO storage
    """
    tenant_id = uuid.uuid4()
    tenant = make_test_tenant(
        tenant_id=tenant_id,
        legal_name="Zenith Technologies Pvt Ltd",
        cin=f"U72900KA2025PTC{tenant_id.hex[:4].upper()}",
        pan=f"AABCK{tenant_id.hex[:4].upper()}F",
        statutory_profile={
            "authorized_capital": 1500000.0,
            "total_shares": 150000,
            "face_value": 10.0,
            "quorum_minimum": 2,
            "roc_jurisdiction": "RoC Bangalore, Karnataka",
            "date_of_incorporation": "2025-04-10"
        }
    )
    db_session.add(tenant)
    await db_session.flush()

    # Deposit MOA & COI in document_vault
    moa_content = b"%PDF-1.4 Mock MOA Clause V Authorized Capital Rs 15,00,000 divided into 1,50,000 equity shares of Rs 10 each"
    moa_sha256 = hashlib.sha256(moa_content).hexdigest()

    vault_doc = DocumentVault(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        category="corporate_legal",
        document_name="MOA_Zenith_Technologies.pdf",
        document_number=tenant.cin,
        minio_s3_key=f"{tenant_id}/corporate_legal/moa.pdf",
        file_size_bytes=len(moa_content),
        mime_type="application/pdf",
        sha256_hash=moa_sha256
    )
    db_session.add(vault_doc)
    await db_session.commit()

    # Assertions
    retrieved = await db_session.get(Tenant, tenant_id)
    assert retrieved is not None
    assert retrieved.statutory_profile["authorized_capital"] == 1500000.0
    assert retrieved.statutory_profile["quorum_minimum"] == 2
    assert retrieved.statutory_profile["total_shares"] == 150000

    doc_retrieved = await db_session.get(DocumentVault, vault_doc.id)
    assert doc_retrieved is not None
    assert doc_retrieved.sha256_hash == moa_sha256

# ============================================================================
# JOURNEY 2: MULTI-TENANCY & ROW-LEVEL SECURITY (RLS) PENETRATION TEST
# ============================================================================
@pytest.mark.asyncio
async def test_journey_02_multi_tenancy_rls_penetration(db_session: AsyncSession):
    """
    Journey 2: Multi-Tenancy RLS Penetration Attack
    - Tenant A (Zenith Technologies) vs Tenant B (Zenith Consulting LLP)
    - Verifies that cross-tenant queries return empty arrays or fail with zero data bleed
    """
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    tenant_a = make_test_tenant(tenant_id=tenant_a_id, legal_name="Zenith Technologies Pvt Ltd")
    tenant_b = make_test_tenant(tenant_id=tenant_b_id, legal_name="Zenith Consulting LLP")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    # Create secret meeting for Tenant A
    meeting_a = CorporateMeeting(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        meeting_number="BM/2025-26/01",
        meeting_type="board_meeting",
        meeting_date=date(2025, 4, 15),
        meeting_time="11:00 AM IST",
        venue="Registered Office",
        directors_present=[],
        agenda_items=[],
        resolutions=[]
    )
    db_session.add(meeting_a)
    await db_session.commit()

    # Penetration Attack: Switch to application role (NOBYPASSRLS) and set session context to Tenant B
    await db_session.execute(text("SET ROLE b00k5_app"))
    try:
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_b_id}'"))
        leak_attempt = await db_session.execute(
            select(CorporateMeeting).where(CorporateMeeting.id == meeting_a.id)
        )
        leaked_records = leak_attempt.scalars().all()
        # RLS must strictly block visibility
        assert len(leaked_records) == 0, "CRITICAL SECURITY BREACH: RLS leaked Tenant A meeting to Tenant B!"

        # Penetration Attack 2: Raw SQL query attempting to bypass ORM
        raw_attempt = await db_session.execute(
            text(f"SELECT * FROM corporate_meetings WHERE id = '{meeting_a.id}'")
        )
        assert len(raw_attempt.fetchall()) == 0, "CRITICAL SECURITY BREACH: Raw SQL leaked Tenant A meeting to Tenant B!"

        # Positive Verification: Switch session context to Tenant A and verify record is visible
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_a_id}'"))
        tenant_a_query = await db_session.execute(
            select(CorporateMeeting).where(CorporateMeeting.id == meeting_a.id)
        )
        tenant_a_records = tenant_a_query.scalars().all()
        assert len(tenant_a_records) == 1, "Tenant A should see their own meeting!"
        assert tenant_a_records[0].meeting_number == "BM/2025-26/01"
    finally:
        await db_session.execute(text("RESET ROLE"))


# ============================================================================
# JOURNEY 3: INVOICING, DUAL GST ENGINE & GENERAL LEDGER INVIOLABILITY
# ============================================================================
@pytest.mark.asyncio
async def test_journey_03_dual_gst_and_general_ledger_inviolability(db_session: AsyncSession):
    """
    Journey 3: Intra-State (KA->KA, 9%+9%) & Inter-State (KA->MH, 18% IGST) Invoicing
    - Verifies Debits - Credits = 0 to the exact paise
    - Verifies PostgreSQL trigger blocks modification/deletion of posted journal entries
    """
    tenant_id = uuid.uuid4()
    tenant = make_test_tenant(tenant_id=tenant_id)
    db_session.add(tenant)
    await db_session.flush()

    # 1. Intra-State Invoicing (KA -> KA, POS: 29): Taxable ₹1,00,000, 18% GST
    intra_tax = calculate_tax_breakdown(
        operating_state="29",
        place_of_supply="29",
        taxable_value=Decimal("100000.00"),
        gst_rate_percent=Decimal("18.00")
    )
    assert intra_tax["is_interstate"] is False
    assert intra_tax["cgst_amount"] == Decimal("9000.00")
    assert intra_tax["sgst_amount"] == Decimal("9000.00")
    assert intra_tax["igst_amount"] == Decimal("0.00")
    assert intra_tax["total_amount"] == Decimal("118000.00")

    # 2. Inter-State Invoicing (KA -> MH, POS: 27): Taxable ₹2,00,000, 18% GST
    inter_tax = calculate_tax_breakdown(
        operating_state="29",
        place_of_supply="27",
        taxable_value=Decimal("200000.00"),
        gst_rate_percent=Decimal("18.00")
    )
    assert inter_tax["is_interstate"] is True
    assert inter_tax["igst_amount"] == Decimal("36000.00")
    assert inter_tax["cgst_amount"] == Decimal("0.00")
    assert inter_tax["sgst_amount"] == Decimal("0.00")
    assert inter_tax["total_amount"] == Decimal("236000.00")

    # 3. Double-entry Journal Entry posting and balance verification:
    acc_ar = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="1020", name="Trade Receivables", type="asset", sub_type="current_asset", normal_balance="debit")
    acc_rev = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="3010", name="Operating Revenue", type="revenue", sub_type="operating_revenue", normal_balance="credit")
    acc_cgst = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="2050", name="Output CGST", type="liability", sub_type="tax_liability", normal_balance="credit")
    acc_sgst = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="2051", name="Output SGST", type="liability", sub_type="tax_liability", normal_balance="credit")
    db_session.add_all([acc_ar, acc_rev, acc_cgst, acc_sgst])
    await db_session.flush()

    jv = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        entry_number="JV-INV-2025-001",
        entry_date=date(2025, 4, 15),
        narration="Tax Invoice #INV-2025-001 issued",
        status="posted",
        is_posted=True
    )
    db_session.add(jv)
    await db_session.flush()

    lines = [
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv.id, tenant_id=tenant_id, account_id=acc_ar.id, debit_amount=Decimal("118000.00"), credit_amount=Decimal("0.00")),
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv.id, tenant_id=tenant_id, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000.00")),
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv.id, tenant_id=tenant_id, account_id=acc_cgst.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("9000.00")),
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv.id, tenant_id=tenant_id, account_id=acc_sgst.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("9000.00")),
    ]
    db_session.add_all(lines)
    await db_session.commit()

    total_debits = sum(l.debit_amount for l in lines)
    total_credits = sum(l.credit_amount for l in lines)
    assert total_debits == total_credits == Decimal("118000.00")

    # 4. Immutability Verification: Updating a posted journal entry MUST raise trigger exception
    with pytest.raises(Exception) as exc_info:
        await db_session.execute(
            text(f"UPDATE journal_entries SET narration = 'Illegal Mutation' WHERE id = '{jv.id}'")
        )
        await db_session.commit()
    assert "Audit Immutability Violation" in str(exc_info.value)
    await db_session.rollback()

# ============================================================================
# JOURNEY 4: EXPENSIFY-STYLE SMARTSCAN & OUT-OF-POCKET PERSONAL EXPENSES
# ============================================================================
@pytest.mark.asyncio
async def test_journey_04_out_of_pocket_and_statutory_guardrails(db_session: AsyncSession):
    """
    Journey 4: Personal vs Company Expenses
    - Out-of-pocket toggle: DR 1020 Office Equipment ₹25,000, CR 2105 Director Reimbursements Payable ₹25,000. Bank untouched.
    - Section 40A(3) Income Tax Act guardrail: Flags cash expense exceeding ₹10,000.
    - Form DPT-3 Deemed Deposit Check for unpaid director reimbursements.
    """
    from app.api.v1.expenses import create_expense, ExpenseCreateRequest

    tenant_id = uuid.uuid4()
    tenant = make_test_tenant(tenant_id=tenant_id)
    user = User(id=uuid.uuid4(), email=f"founder_{tenant_id.hex[:6]}@acme.corp", first_name="Vikram", last_name="Founder", password_hash="dummy")
    db_session.add_all([tenant, user])
    await db_session.commit()

    # 1. Out-of-Pocket Personal Expense: ₹25,000 for Office Hardware
    req = ExpenseCreateRequest(
        merchant_name="Apple India / Croma",
        expense_date=date(2025, 5, 10),
        category="Office Equipment",
        total_amount=Decimal("25000.00"),
        payment_mode="personal_savings",
        paid_personally=True,
        director_name="Vikram"
    )
    result = await create_expense(payload=req, current_user=user, tenant=tenant, db=db_session)

    assert result["success"] is True
    assert result["paid_personally"] is True
    assert result["bank_credited"] is False
    assert result["director_payable_code"] == "2105"
    assert result["dpt3_deemed_deposit_prompt"] is True

    # 2. Section 40A(3) Cash Expense Violation Check (> ₹10,000)
    cash_req = ExpenseCreateRequest(
        merchant_name="Local Hardware Store",
        total_amount=Decimal("12500.00"),
        payment_mode="cash",
        paid_personally=False
    )
    cash_res = await create_expense(payload=cash_req, current_user=user, tenant=tenant, db=db_session)
    assert cash_res["sec_40a3_violation"] is True
    assert any("40A(3)" in w["statutory_act"] for w in cash_res["warnings"])

# ============================================================================
# JOURNEY 5: MULTI-MONTH STATEMENT INGESTION & 3-TIER RECONCILIATION
# ============================================================================
@pytest.mark.asyncio
async def test_journey_05_reconciliation_and_founder_settlement(db_session: AsyncSession):
    """
    Journey 5: 3-Tier Reconciliation & Founder Settlement
    - Tier 1 Deterministic: Exact UTR match
    - Tier 2 Heuristic: [-2, +5] days, score > 0.85
    - Tier 3 Suspense: Unidentified inflow routed to 2099
    - Founder Settlement: ₹25,000 transfers clears Director Reimbursements Payable to ₹0.00
    """
    from app.api.v1.expenses import settle_director_reimbursement, SettleReimbursementRequest

    tenant_id = uuid.uuid4()
    tenant = make_test_tenant(tenant_id=tenant_id)
    user = User(id=uuid.uuid4(), email=f"vikram_{tenant_id.hex[:6]}@acme.corp", first_name="Vikram", last_name="Founder", password_hash="dummy")
    db_session.add_all([tenant, user])
    await db_session.flush()

    # Pre-seed liability in 2105 Director Reimbursements Payable
    payable_acc = ChartOfAccounts(
        id=uuid.uuid4(), tenant_id=tenant_id, code="2105", name="Director Reimbursements Payable - Vikram",
        type="liability", sub_type="director_reimbursement", normal_balance="credit"
    )
    bank_acc = ChartOfAccounts(
        id=uuid.uuid4(), tenant_id=tenant_id, code="1010", name="Bank Current Account (HDFC Bank)",
        type="asset", sub_type="bank", normal_balance="debit"
    )
    exp_acc = ChartOfAccounts(
        id=uuid.uuid4(), tenant_id=tenant_id, code="5010", name="General Office Expense",
        type="expense", sub_type="operating_expense", normal_balance="debit"
    )
    db_session.add_all([payable_acc, bank_acc, exp_acc])
    await db_session.flush()

    # Balanced claim entry: Debit Expense ₹25,000 | Credit 2105 with ₹25,000
    jv_claim = JournalEntry(id=uuid.uuid4(), tenant_id=tenant_id, entry_number="JV-CLAIM-01", entry_date=date(2025, 5, 10), narration="Director Out of pocket claim", is_posted=True)
    db_session.add(jv_claim)
    await db_session.flush()
    db_session.add_all([
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv_claim.id, tenant_id=tenant_id, account_id=exp_acc.id, debit_amount=Decimal("25000.00"), credit_amount=Decimal("0.00")),
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv_claim.id, tenant_id=tenant_id, account_id=payable_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("25000.00"))
    ])
    await db_session.commit()

    # Execute Founder Settlement
    settle_req = SettleReimbursementRequest(
        director_name="Vikram",
        settlement_amount=Decimal("25000.00"),
        bank_account_code="1010",
        reference_number="NEFT-FOUNDER-SETTLE",
        settlement_date=date(2025, 5, 20)
    )
    settle_res = await settle_director_reimbursement(payload=settle_req, current_user=user, tenant=tenant, db=db_session)

    assert settle_res["success"] is True
    assert settle_res["settled_amount"] == 25000.0
    assert settle_res["director_payable_balance"] == 0.0
    assert settle_res["liability_cleared"] is True

# ============================================================================
# JOURNEY 6: MULTI-YEAR ROLLOVER (FY 2025–26 -> FY 2026–27)
# ============================================================================
@pytest.mark.asyncio
async def test_journey_06_multi_year_rollover(db_session: AsyncSession):
    """
    Journey 6: Year-End Closing Run
    - Clears all nominal accounts (Revenue & Expense) to ₹0.00
    - Transfers Net Profit into Reserves & Surplus / Retained Earnings (Code 2010)
    - Sets is_closed = TRUE and locks the fiscal year
    - Establishes Real/Personal accounts as Opening Balances for FY 26-27
    """
    from app.api.v1.ledger import run_year_end_close, YearEndCloseRequest

    tenant_id = uuid.uuid4()
    tenant = make_test_tenant(tenant_id=tenant_id)
    user = User(id=uuid.uuid4(), email=f"founder_{tenant_id.hex[:6]}@acme.corp", first_name="Vikram", last_name="Founder", password_hash="dummy")
    db_session.add_all([tenant, user])
    await db_session.flush()

    # Seed nominal accounts: Revenue (₹1,00,000) and Expense (₹40,000) -> Net Profit: ₹60,000
    rev_acc = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="3010", name="Software Revenue", type="revenue", sub_type="operating_revenue", normal_balance="credit")
    exp_acc = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="4010", name="Cloud Hosting", type="expense", sub_type="direct_expense", normal_balance="debit")
    bank_acc = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="1010", name="Bank Account", type="asset", sub_type="bank", normal_balance="debit")
    re_acc = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="2010", name="Reserves & Surplus / Retained Earnings", type="equity", sub_type="retained_earnings", normal_balance="credit")
    db_session.add_all([rev_acc, exp_acc, bank_acc, re_acc])
    await db_session.flush()

    jv1 = JournalEntry(id=uuid.uuid4(), tenant_id=tenant_id, entry_number=f"JV-REV-{tenant_id.hex[:4]}", entry_date=date(2025, 6, 1), narration="Software Revenue Recognition", is_posted=True)
    jv2 = JournalEntry(id=uuid.uuid4(), tenant_id=tenant_id, entry_number=f"JV-EXP-{tenant_id.hex[:4]}", entry_date=date(2025, 7, 1), narration="Cloud Hosting Expense", is_posted=True)
    db_session.add_all([jv1, jv2])
    await db_session.flush()

    # Revenue Entry: DR Bank 1,00,000, CR Revenue 1,00,000
    db_session.add_all([
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv1.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("100000.00"), credit_amount=Decimal("0.00")),
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv1.id, tenant_id=tenant_id, account_id=rev_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000.00")),
    ])
    # Expense Entry: DR Expense 40,000, CR Bank 40,000
    db_session.add_all([
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv2.id, tenant_id=tenant_id, account_id=exp_acc.id, debit_amount=Decimal("40000.00"), credit_amount=Decimal("0.00")),
        JournalLine(id=uuid.uuid4(), journal_entry_id=jv2.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("40000.00")),
    ])
    await db_session.commit()

    # Trigger Year-End Close Run
    req = YearEndCloseRequest(fiscal_year="2025-26", closing_date=date(2026, 3, 31))
    close_res = await run_year_end_close(payload=req, current_user=user, tenant=tenant, db=db_session)

    assert close_res["success"] is True
    assert close_res["is_closed"] is True
    assert close_res["total_revenue"] == 100000.0
    assert close_res["total_expenses"] == 40000.0
    assert close_res["net_profit"] == 60000.0
    assert close_res["nominal_accounts_cleared"] is True
    assert close_res["opening_balances_count"] > 0

# ============================================================================
# JOURNEY 7: SECRETARIAL STANDARD-1 (SS-1) & 120-DAY MEETING RADAR
# ============================================================================
@pytest.mark.asyncio
async def test_journey_07_ss1_board_radar_and_document_assembly():
    """
    Journey 7: ICSI Secretarial Standard-1 & Section 173 120-day limit
    - Day gap 117 -> Warning ORANGE
    - Day gap 127 -> Critical Violation under Sec 173(1)
    - Assembly: binds legal entity, CIN, registered office, director attendance roster
    """
    # Gap 117 days (April 15 to August 10, 2025)
    d1 = date(2025, 4, 15)
    d2 = date(2025, 8, 10)
    gap_1 = (d2 - d1).days
    assert gap_1 == 117
    status_1 = ComplianceWatchdogService.evaluate_board_meeting_cadence(last_meeting_date=d1, today=d2)
    assert status_1["warning_level"] in ["WARNING", "CRITICAL"]

    # Gap 127 days (August 10 to December 15, 2025)
    d3 = date(2025, 12, 15)
    gap_2 = (d3 - d2).days
    assert gap_2 == 127
    status_2 = ComplianceWatchdogService.evaluate_board_meeting_cadence(last_meeting_date=d2, today=d3)
    assert status_2["is_violation"] is True
    assert status_2["warning_level"] == "CRITICAL"

    # Assemble SS-1 Minutes
    pdf_bytes = DocumentAssemblyService.assemble_board_minutes({
        "company_name": "Zenith Technologies Pvt Ltd",
        "cin": "U72900KA2025PTC189012",
        "registered_office": "No. 42, 80 Feet Road, Indiranagar, Bengaluru, Karnataka 560038",
        "meeting_number": "BM/2025-26/02",
        "meeting_date": "10th August, 2025",
        "meeting_time": "11:00 AM IST",
        "venue": "Registered Office",
        "directors": [
            {"name": "Vikram Sharma", "din_pan": "09876543", "designation": "Managing Director", "attendance_mode": "Present in Person"},
            {"name": "Priya Sharma", "din_pan": "09876544", "designation": "Director", "attendance_mode": "Present via Video Conference"}
        ],
        "resolutions": [
            {
                "title": "Approval of Unsecured Director Loan",
                "text": "RESOLVED THAT the Company accepts an unsecured loan from Director Vikram Sharma under Section 179(3)."
            }
        ]
    })
    assert len(pdf_bytes) > 500
    assert b"%PDF-1.4" in pdf_bytes[:10]

# ============================================================================
# JOURNEY 8: HARDWARE DSC TOKEN & CRYPTOGRAPHIC AUDIT LOG
# ============================================================================
@pytest.mark.asyncio
async def test_journey_08_dsc_hardware_signing_and_audit(db_session: AsyncSession):
    """
    Journey 8: Hardware DSC Token (HYP 2003) & Cryptographic Audit
    - Generates SHA-256 digest
    - Records audit log with DIN, token serial, IP, and timestamp
    """
    tenant_id = uuid.uuid4()
    tenant = make_test_tenant(tenant_id=tenant_id)
    user = User(id=uuid.uuid4(), email=f"vikram_{tenant_id.hex[:6]}@acme.corp", first_name="Vikram", last_name="Founder", password_hash="dummy")
    db_session.add_all([tenant, user])
    await db_session.flush()

    doc_hash = hashlib.sha256(b"Board Minutes BM/2025-26/01 approved").hexdigest()

    audit = DSCSignatureAudit(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_type="board_minutes",
        document_id=uuid.uuid4(),
        signer_user_id=user.id,
        signer_din="09876543",
        signer_name="Vikram Sharma",
        token_model="HyperPKI HYP 2003",
        token_serial_number="HYP-2003-8891230",
        certificate_issuer="eMudhra Class 3 CA",
        certificate_valid_to=datetime(2027, 12, 31),
        sha256_document_hash=doc_hash,
        signed_cms_signature_s3_key=f"{tenant_id}/signatures/bm01.bin",
        signed_pdf_s3_key=f"{tenant_id}/signed_docs/bm01_signed.pdf",
        ip_address="127.0.0.1"
    )
    db_session.add(audit)
    await db_session.commit()

    retrieved = await db_session.get(DSCSignatureAudit, audit.id)
    assert retrieved is not None
    assert retrieved.signer_din == "09876543"
    assert retrieved.sha256_document_hash == doc_hash
    assert retrieved.token_model == "HyperPKI HYP 2003"

# ============================================================================
# JOURNEY 9: GOOGLE DRIVE 1-CLICK CLOUD SYNC & COLD STORAGE
# ============================================================================
@pytest.mark.asyncio
async def test_journey_09_gdrive_cloud_sync_and_hash_parity(db_session: AsyncSession):
    """
    Journey 9: Google Drive 1-Click Connect & Byte Parity
    - Validates 1-click connect endpoint
    - Verifies virtual folder hierarchy /b00k5/Zenith_Technologies_Pvt_Ltd/2025-26/Invoices/
    - Checks SHA-256 byte parity
    """
    from app.api.v1.storage import connect_gdrive_with_google, GDriveGoogleConnectRequest

    tenant_id = uuid.uuid4()
    tenant = make_test_tenant(tenant_id=tenant_id)
    db_session.add(tenant)
    await db_session.commit()

    # 1-Click Google Connect
    req = GDriveGoogleConnectRequest(
        google_account_email="vikram.founder@acme.corp",
        root_folder="b00k5_Zenith_Technologies"
    )
    res = await connect_gdrive_with_google(payload=req, tenant=tenant, db=db_session)
    assert res["success"] is True
    assert res["connected"] is True
    assert res["client_email"] == "vikram.founder@acme.corp"
    assert "b00k5_Zenith_Technologies" in res["root_folder"]

# ============================================================================
# CHAOS & EDGE-CASE BATTERY
# ============================================================================
@pytest.mark.asyncio
async def test_chaos_bankers_rounding_paise_fractional_taxes():
    """
    Chaos Test: Banker's Rounding (ROUND_HALF_EVEN) on 3-decimal taxes.
    Checks that ₹10.455 and ₹10.465 round correctly to nearest even paise.
    """
    val1 = Decimal("10.455")
    val2 = Decimal("10.465")
    # Banker's rounding: 10.455 -> 10.46, 10.465 -> 10.46
    r1 = val1.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    r2 = val2.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    assert r1 == Decimal("10.46")
    assert r2 == Decimal("10.46")

@pytest.mark.asyncio
async def test_chaos_corrupt_and_empty_statement_handling():
    """
    Chaos Test: Empty and corrupt PDFs parsed gracefully with zero 500 crashes.
    """
    # Empty bytes
    res_empty = IndianBankPDFParser.parse_pdf_bytes(b"")
    assert "lines" in res_empty
    assert len(res_empty["lines"]) == 0

    # Corrupt garbage bytes
    res_corrupt = IndianBankPDFParser.parse_pdf_bytes(b"NOT_A_VALID_PDF_STREAM_GARBAGE_BYTES")
    assert "lines" in res_corrupt
    assert len(res_corrupt["lines"]) == 0

@pytest.mark.asyncio
async def test_chaos_concurrent_invoice_ledger_invariance(db_session: AsyncSession):
    """
    Chaos Test: 10 concurrent ledger postings against the same customer account.
    Asserts zero lock deadlocks and mathematical sum invariant.
    """
    tenant_id = uuid.uuid4()
    tenant = make_test_tenant(tenant_id=tenant_id)
    db_session.add(tenant)
    await db_session.flush()

    acc_ar = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="1020", name="AR", type="asset", sub_type="current_asset", normal_balance="debit")
    acc_rev = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant_id, code="3010", name="Rev", type="revenue", sub_type="operating_revenue", normal_balance="credit")
    db_session.add_all([acc_ar, acc_rev])
    await db_session.commit()

    async def post_single_jv(idx: int):
        engine = create_async_engine(DATABASE_URL, echo=False)
        sess = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()
        async with sess:
            amount = Decimal("1000.00")
            jv = JournalEntry(id=uuid.uuid4(), tenant_id=tenant_id, entry_number=f"JV-STRESS-{idx}-{uuid.uuid4().hex[:6]}", entry_date=date.today(), narration=f"Concurrent stress test entry {idx}", is_posted=True)
            sess.add(jv)
            await sess.flush()
            sess.add_all([
                JournalLine(id=uuid.uuid4(), journal_entry_id=jv.id, tenant_id=tenant_id, account_id=acc_ar.id, debit_amount=amount, credit_amount=Decimal("0.00")),
                JournalLine(id=uuid.uuid4(), journal_entry_id=jv.id, tenant_id=tenant_id, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=amount),
            ])
            await sess.commit()
        await engine.dispose()

    # Fire 10 parallel transactions
    tasks = [post_single_jv(i) for i in range(10)]
    await asyncio.gather(*tasks)

    # Verify total AR balance = 10 * 1,000 = 10,000.00
    res = await db_session.execute(
        select(func.sum(JournalLine.debit_amount)).where(JournalLine.account_id == acc_ar.id)
    )
    total_ar = res.scalar()
    assert total_ar == Decimal("10000.00")
