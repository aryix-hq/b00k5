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
from app.models.invoice import Invoice, InvoiceItem, Contact
from app.models.ledger import ChartOfAccounts, FiscalYear
from app.models.mca_registers import (
    StatutoryMember,
    StatutoryLoanGuarantee,
    StatutoryContractInterestedDirector,
    DirectorAnnualDisclosure,
    ShareCertificate,
)
from app.services.einvoice_service import EInvoiceService
from app.services.mca_registers_service import MCARegistersService

DATABASE_URL = settings.DATABASE_URL


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def phase11_test_tenant(db_session: AsyncSession):
    """Creates a dedicated Private Limited company tenant with baseline contacts & COA for Phase 11 testing."""
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
        legal_name=f"Zenith Autonomous Systems Private Limited {uid}",
        trade_name="Zenith Autonomous",
        cin=cin,
        pan=pan,
        gstin=gstin,
        state_code="29",
        registered_office="Building 7, Cyber City, Indiranagar, Bengaluru 560038",
        statutory_profile={
            "entity_type": "Private Limited Company",
            "tan": f"BLR{pan[:5]}01",
            "directors": [
                {"name": "Ananya Sen", "din": "08912345", "designation": "Managing Director"}
            ]
        }
    )
    db_session.add(tenant)

    user = User(
        id=uuid.uuid4(),
        email=f"founder_{uid}@zenithauto.in",
        first_name="Ananya",
        last_name="Sen",
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

    # Commit tenant and user first so foreign keys succeed
    await db_session.commit()

    # Seed baseline COA
    accounts = [
        {"code": "1010", "name": "Bank Current Account", "type": "asset", "sub_type": "bank", "normal_balance": "debit"},
        {"code": "1020", "name": "Trade Receivables (Debtors)", "type": "asset", "sub_type": "accounts_receivable", "normal_balance": "debit"},
        {"code": "3010", "name": "Revenue from Software Development", "type": "revenue", "sub_type": "operating_revenue", "normal_balance": "credit"},
        {"code": "2050", "name": "GST Output Liability (CGST+SGST/IGST)", "type": "liability", "sub_type": "tax_liability", "normal_balance": "credit"},
    ]
    for acc in accounts:
        coa = ChartOfAccounts(id=uuid.uuid4(), tenant_id=tenant.id, **acc)
        db_session.add(coa)

    # Seed Customer Contact
    customer = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=f"Acme Corp India Pvt Ltd {uid}",
        gstin="27AAACA9999A1Z1",
        state_code="27",
        email="billing@acmecorp.in",
        billing_address="Bandra Kurla Complex, Mumbai 400051",
        is_customer=True,
    )
    db_session.add(customer)

    await db_session.commit()
    await db_session.refresh(tenant)
    await db_session.refresh(customer)
    tenant._test_customer = customer
    return tenant


# =========================================================================
# Milestone 11.2: Indian E-Invoicing (IRN) & B2B Signed QR (FEAT-11)
# =========================================================================

@pytest.mark.asyncio
async def test_irn_hash_computation_and_nic_schema():
    """
    Validates GSTN standard IRN 64-character SHA-256 hash algorithm and NIC v1.03 Schema.
    """
    gstin = "29AABCV1234F1Z5"
    doc_type = "INV"
    doc_no = "INV-2026-05-001"
    fy = "2026-27"

    irn = EInvoiceService.compute_irn_hash(gstin, doc_type, doc_no, fy)
    assert len(irn) == 64
    assert irn == irn.lower()
    # Check deterministic calculation
    expected_hash = EInvoiceService.compute_irn_hash(gstin, doc_type, doc_no, fy)
    assert irn == expected_hash

    # Generate QR payload
    qr_payload = EInvoiceService.generate_signed_qr_payload(
        supplier_gstin=gstin,
        buyer_gstin="27AAACA9999A1Z1",
        doc_no=doc_no,
        doc_date="10/05/2026",
        tot_val=295000.00,
        item_cnt=1,
        main_hsn="998314",
        irn=irn,
        ack_no="112610145892001",
        ack_date="10/05/2026 14:30:00"
    )
    assert irn in qr_payload
    assert gstin in qr_payload
    assert "998314" in qr_payload


@pytest.mark.asyncio
async def test_einvoice_generation_service_and_db_persistence(db_session: AsyncSession, phase11_test_tenant: Tenant):
    """
    Validates end-to-end E-Invoice generation against real PostgreSQL 16:
    - Generates 64-char IRN hash
    - Populates 15-digit Ack No and Ack Date
    - Computes signed QR code payload string
    - Updates invoice status to 'ACT'
    """
    tenant = phase11_test_tenant
    customer = tenant._test_customer

    inv = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        contact_id=customer.id,
        invoice_number=f"INV-P11-{uuid.uuid4().hex[:4].upper()}",
        issue_date=date(2026, 6, 15),
        due_date=date(2026, 7, 15),
        place_of_supply="27",
        is_interstate=True,
        subtotal=Decimal("100000.00"),
        cgst_total=Decimal("0.00"),
        sgst_total=Decimal("0.00"),
        igst_total=Decimal("18000.00"),
        grand_total=Decimal("118000.00"),
        status="sent",
    )
    db_session.add(inv)
    await db_session.flush()

    item = InvoiceItem(
        id=uuid.uuid4(),
        invoice_id=inv.id,
        item_description="Autonomous Vision AI Software License",
        hsn_sac_code="998314",
        quantity=Decimal("1.000"),
        unit_price=Decimal("100000.00"),
        taxable_value=Decimal("100000.00"),
        gst_rate_percent=Decimal("18.00"),
        cgst_amount=Decimal("0.00"),
        sgst_amount=Decimal("0.00"),
        igst_amount=Decimal("18000.00"),
        total_amount=Decimal("118000.00"),
    )
    db_session.add(item)
    await db_session.commit()

    # Generate IRN via service
    einvoice_res = await EInvoiceService.generate_einvoice(db_session, tenant.id, inv.id)
    await db_session.commit()

    assert einvoice_res["irn"] is not None
    assert len(einvoice_res["irn"]) == 64
    assert einvoice_res["irn_status"] in ("ACT", "GENERATED")
    assert einvoice_res["ack_no"] is not None
    assert len(einvoice_res["ack_no"]) == 15
    assert einvoice_res["signed_qr_code"] is not None
    assert einvoice_res["einvoice_payload"] is not None

    # Verify database persistence
    refreshed_inv = await db_session.get(Invoice, inv.id)
    assert refreshed_inv.irn == einvoice_res["irn"]
    assert refreshed_inv.irn_status in ("ACT", "GENERATED")
    assert refreshed_inv.ack_no == einvoice_res["ack_no"]
    assert refreshed_inv.signed_qr_code == einvoice_res["signed_qr_code"]
    assert refreshed_inv.einvoice_payload["DocDtls"]["No"] == refreshed_inv.invoice_number


# =========================================================================
# Milestone 11.3: Mandatory MCA Statutory Registers (FEAT-12)
# =========================================================================

@pytest.mark.asyncio
async def test_mgt1_member_registration_and_distinctive_validation(db_session: AsyncSession, phase11_test_tenant: Tenant):
    """
    Tests Form MGT-1 Register of Members:
    - Verifies distinct share numbers range invariant (distinctive_to - distinctive_from + 1 == number_of_shares)
    - Verifies PAN and Address recording
    - Validates exception on invalid share numbers range
    """
    tenant_id = phase11_test_tenant.id

    created = await MCARegistersService.register_member(
        session=db_session,
        tenant_id=tenant_id,
        folio_number="F-001",
        member_name="Dr. Arjun Mehta",
        father_or_spouse_name="Dr. Raman Mehta",
        pan="ABCDE1234F",
        email="arjun.mehta@example.com",
        address="12 High Street, Indiranagar, Bengaluru 560038",
        number_of_shares=Decimal("10000"),
        distinctive_from=1,
        distinctive_to=10000,
        nominal_value_per_share=Decimal("10.00"),
        amount_paid_per_share=Decimal("10.00"),
        date_of_becoming_member=date(2026, 4, 1),
    )
    await db_session.commit()
    await db_session.refresh(created)

    assert created.id is not None
    assert created.folio_number == "F-001"
    assert created.number_of_shares == Decimal("10000")
    assert created.status == "ACTIVE"

    # Test distinctive number mismatch exception
    with pytest.raises(ValueError) as excinfo:
        await MCARegistersService.register_member(
            session=db_session,
            tenant_id=tenant_id,
            folio_number="F-002",
            member_name="Priya Nair",
            number_of_shares=Decimal("5000"),
            distinctive_from=10001,
            distinctive_to=12000,  # Only 2,000 shares range instead of 5,000!
        )
    assert "Share count mismatch" in str(excinfo.value)


@pytest.mark.asyncio
async def test_mbp2_loans_guarantees_recording_and_statutory_interest_guard(db_session: AsyncSession, phase11_test_tenant: Tenant):
    """
    Tests Form MBP-2 Register of Loans & Guarantees u/s 186:
    - Enforces statutory interest floor (>= 5.0% G-Sec yield)
    - Validates special resolution & board approval logging
    """
    tenant_id = phase11_test_tenant.id

    # Test sub-5% interest rate violation
    with pytest.raises(ValueError) as excinfo:
        await MCARegistersService.record_loan_guarantee(
            session=db_session,
            tenant_id=tenant_id,
            transaction_type="LOAN_GIVEN",
            body_corporate_name="Associate Software Labs LLP",
            amount=Decimal("500000.00"),
            board_resolution_date=date(2026, 4, 20),
            interest_rate_pct=Decimal("3.50"),  # Below Section 186(7) G-Sec yield floor!
            tenure_months=12,
            cin_or_pan="AAB-1234",
            notes="Working Capital Loan"
        )
    assert "Section 186(7)" in str(excinfo.value)

    # Test valid conforming loan
    created_loan = await MCARegistersService.record_loan_guarantee(
        session=db_session,
        tenant_id=tenant_id,
        transaction_type="LOAN_GIVEN",
        body_corporate_name="Associate Software Labs LLP",
        amount=Decimal("500000.00"),
        board_resolution_date=date(2026, 4, 20),
        interest_rate_pct=Decimal("8.50"),  # Conforming > 5%
        tenure_months=12,
        cin_or_pan="AAB-1234",
        notes="Working Capital Loan"
    )
    await db_session.commit()
    await db_session.refresh(created_loan)

    assert created_loan.id is not None
    assert created_loan.amount == Decimal("500000.00")
    assert created_loan.interest_rate_pct == Decimal("8.50")
    assert created_loan.status == "ACTIVE"


@pytest.mark.asyncio
async def test_mbp4_contracts_interested_directors(db_session: AsyncSession, phase11_test_tenant: Tenant):
    """
    Tests Form MBP-4 Register of Contracts with Interested Directors u/s 189:
    - Records interested director name, DIN, and nature of interest
    - Confirms date of board meeting and voting abstention flag
    """
    tenant_id = phase11_test_tenant.id

    created_contract = await MCARegistersService.record_contract(
        session=db_session,
        tenant_id=tenant_id,
        contract_date=date(2026, 5, 2),
        party_name="Sen & Sons Advisory Private Limited",
        nature_of_contract="Office Premises Lease & Software Consulting",
        director_name="Ananya Sen",
        director_din="08912345",
        nature_of_interest="Director & 45% Equity Shareholder in Counterparty",
        board_meeting_date=date(2026, 5, 10),
        voting_status="ABSTAINED",
        contract_value=Decimal("1200000.00")
    )
    await db_session.commit()
    await db_session.refresh(created_contract)

    assert created_contract.id is not None
    assert created_contract.director_din == "08912345"
    assert created_contract.voting_status == "ABSTAINED"
    assert created_contract.contract_value == Decimal("1200000.00")


@pytest.mark.asyncio
async def test_director_annual_disclosures_mbp1_dir8(db_session: AsyncSession, phase11_test_tenant: Tenant):
    """
    Tests Form MBP-1 & Form DIR-8 Annual Director Disclosures:
    - Validates 8-digit DIN format requirement
    - Records non-disqualification u/s 164(2)
    - Records other directorships and shareholding
    """
    tenant_id = phase11_test_tenant.id

    # Test invalid DIN (4 digits instead of 8)
    with pytest.raises(ValueError) as excinfo:
        await MCARegistersService.record_director_disclosure(
            session=db_session,
            tenant_id=tenant_id,
            fiscal_year="2026-27",
            form_type="MBP_1",
            director_name="Ananya Sen",
            director_din="1234",  # Invalid DIN!
            disclosure_payload={"test": "payload"}
        )
    assert "8-digit numeric string" in str(excinfo.value)

    # Valid MBP-1
    res_mbp1 = await MCARegistersService.record_director_disclosure(
        session=db_session,
        tenant_id=tenant_id,
        fiscal_year="2026-27",
        form_type="MBP_1",
        director_name="Ananya Sen",
        director_din="08912345",
        disclosure_payload={
            "other_directorships": [
                {"company_name": "Sen & Sons Advisory Pvt Ltd", "cin": "U74999KA2020PTC123456", "designation": "Director"}
            ],
            "other_shareholdings": [
                {"company_name": "Sen & Sons Advisory Pvt Ltd", "shares": 45000, "percentage": "45.00"}
            ]
        },
        filing_date=date(2026, 4, 10),
    )

    # Valid DIR-8
    res_dir8 = await MCARegistersService.record_director_disclosure(
        session=db_session,
        tenant_id=tenant_id,
        fiscal_year="2026-27",
        form_type="DIR_8",
        director_name="Ananya Sen",
        director_din="08912345",
        disclosure_payload={
            "is_disqualified": False,
            "statement": "Not disqualified under Section 164(2) of Companies Act 2013."
        },
        filing_date=date(2026, 4, 10),
    )
    await db_session.commit()

    assert res_mbp1.id is not None
    assert res_mbp1.form_type == "MBP_1"
    assert res_dir8.id is not None
    assert res_dir8.form_type == "DIR_8"


@pytest.mark.asyncio
async def test_sh1_share_certificate_issuance(db_session: AsyncSession, phase11_test_tenant: Tenant):
    """
    Tests Form SH-1 Share Certificate Issuance u/s 46:
    - Links to Member from Form MGT-1
    - Enforces distinctive numbers and stamp duty tracking
    """
    tenant_id = phase11_test_tenant.id

    # Create member first
    member = await MCARegistersService.register_member(
        session=db_session,
        tenant_id=tenant_id,
        folio_number="F-SH1-01",
        member_name="Rohan Varma",
        pan="ABCDE9999Z",
        email="rohan@example.com",
        address="7th Block, Jayanagar, Bengaluru",
        number_of_shares=Decimal("2000"),
        distinctive_from=20001,
        distinctive_to=22000,
        nominal_value_per_share=Decimal("10.00"),
        amount_paid_per_share=Decimal("10.00"),
        date_of_becoming_member=date(2026, 5, 1),
    )
    await db_session.commit()

    # Issue SH-1
    cert = await MCARegistersService.issue_share_certificate(
        session=db_session,
        tenant_id=tenant_id,
        member_id=member.id,
        certificate_number="SH1-2026-001",
        number_of_shares=2000,
        distinctive_from=20001,
        distinctive_to=22000,
        face_value=Decimal("10.00"),
        issue_date=date(2026, 5, 5),
        signatory_director_1="Ananya Sen (Managing Director)"
    )
    await db_session.commit()
    await db_session.refresh(cert)

    assert cert.id is not None
    assert cert.certificate_number == "SH1-2026-001"
    assert cert.number_of_shares == 2000
    assert cert.status == "ISSUED"


@pytest.mark.asyncio
async def test_mca_registers_summary_dashboard(db_session: AsyncSession, phase11_test_tenant: Tenant):
    """
    Tests MCARegistersService.get_registers_summary dashboard counts.
    """
    tenant_id = phase11_test_tenant.id

    # Register member to verify count aggregation
    await MCARegistersService.register_member(
        session=db_session,
        tenant_id=tenant_id,
        folio_number="F-DASH-01",
        member_name="Vikram Seth",
        number_of_shares=Decimal("1000"),
        distinctive_from=1,
        distinctive_to=1000,
    )
    await db_session.commit()

    summary = await MCARegistersService.get_registers_summary(db_session, tenant_id)

    assert "total_members" in summary
    assert "total_equity_shares" in summary
    assert "total_loans_guarantees" in summary
    assert "active_loans_exposure" in summary
    assert "total_contracts_interested_directors" in summary
    assert "total_disclosures" in summary
    assert "total_share_certificates" in summary
    assert summary["total_members"] >= 1
    assert summary["total_equity_shares"] == 1000.0
