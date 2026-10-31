import pytest
import uuid
import random
import string
from decimal import Decimal
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import select, text

from app.main import app
from app.core.config import settings
from app.api.deps import get_db
from app.models.tenant import Tenant, User, TenantUser
from app.models.payroll import Contractor, ContractorPayment
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.bank import BankStatement, BankStatementLine
from app.schemas.payroll import QuickContractorPaymentRequest
from app.services.payroll_service import PayrollService
from app.services.reconciliation_engine import ReconciliationEngine


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
async def test_tenant(db_session: AsyncSession):
    """Provisions an isolated Private Limited company tenant with seeded COA."""
    uid = uuid.uuid4().hex[:6]
    rand_alpha = ''.join(random.choices(string.ascii_uppercase, k=4))
    pan = f"A{rand_alpha}{random.randint(1000, 9999)}{random.choice(string.ascii_uppercase)}"
    gstin = f"29{pan}1Z5"
    cin = f"U72200KA2026PTC{random.randint(100000, 999999)}"

    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name=f"QuickPay Sovereign Corp {uid}",
        trade_name="QuickPayCorp",
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
        email=f"founder_{uid}@quickpay.in",
        first_name="Arjun",
        last_name="Mehta",
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
async def test_quick_pay_freelancer_gross_mode(test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies 1-Click Quick-Pay under Gross Mode (Section 194J(1) Tech 2%):
    - Auto-provisions freelancer record
    - Computes TDS: ₹50,000 * 2% = ₹1,000; Net Payable = ₹49,000
    - Generates balanced Leg 1 Accrual JV (DR 4040, CR 2060, CR 2040)
    - Generates balanced Leg 2 Disbursement JV (DR 2040, CR 1010)
    """
    tenant = test_tenant
    req = QuickContractorPaymentRequest(
        freelancer_name="Priya Sharma Frontend",
        amount=Decimal("50000.00"),
        amount_type="gross",
        service_type="194J_TECH",
        description="Frontend React UI Engineering Sprint",
        disburse_immediately=True,
        bank_reference_or_utr="UTR-FRONTEND-2026"
    )

    payment = await PayrollService.quick_pay_contractor(
        session=db_session,
        tenant_id=tenant.id,
        data=req,
        user_id=tenant._test_user.id
    )

    assert payment.id is not None
    assert payment.gross_amount == Decimal("50000.00")
    assert payment.tds_rate == Decimal("2.00")
    assert payment.tds_amount == Decimal("1000.00")
    assert payment.net_payable == Decimal("49000.00")
    assert payment.status == "disbursed"
    assert payment.payout_utr == "UTR-FRONTEND-2026"
    assert payment.accrual_journal_id is not None
    assert payment.disbursement_journal_id is not None

    # Verify Accrual Journal Balance
    accrual_je = await db_session.get(JournalEntry, payment.accrual_journal_id)
    assert accrual_je is not None
    assert accrual_je.is_posted is True
    lines = (await db_session.execute(
        select(JournalLine).where(JournalLine.journal_entry_id == accrual_je.id)
    )).scalars().all()
    assert sum(l.debit_amount for l in lines) == sum(l.credit_amount for l in lines) == Decimal("50000.00")

    # Verify Disbursement Journal Balance
    disb_je = await db_session.get(JournalEntry, payment.disbursement_journal_id)
    assert disb_je is not None
    disb_lines = (await db_session.execute(
        select(JournalLine).where(JournalLine.journal_entry_id == disb_je.id)
    )).scalars().all()
    assert sum(l.debit_amount for l in disb_lines) == sum(l.credit_amount for l in disb_lines) == Decimal("49000.00")


@pytest.mark.asyncio
async def test_quick_pay_freelancer_net_mode(test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies 1-Click Quick-Pay under Net Mode (Section 194J(1) Prof 10%):
    - Net in-hand target: ₹45,000
    - Gross amount reverse calculated: 45,000 / (1 - 0.10) = ₹50,000
    - Statutory TDS withheld: ₹5,000
    """
    tenant = test_tenant
    req = QuickContractorPaymentRequest(
        freelancer_name="Advocate Karan Legal",
        amount=Decimal("45000.00"),
        amount_type="net",
        service_type="194J_PROF",
        description="MCA Corporate Secretarial Advisory",
        disburse_immediately=True
    )

    payment = await PayrollService.quick_pay_contractor(
        session=db_session,
        tenant_id=tenant.id,
        data=req,
        user_id=tenant._test_user.id
    )

    assert payment.net_payable == Decimal("45000.00")
    assert payment.gross_amount == Decimal("50000.00")
    assert payment.tds_amount == Decimal("5000.00")
    assert payment.tds_rate == Decimal("10.00")
    assert payment.status == "disbursed"


@pytest.mark.asyncio
async def test_quick_pay_no_tds_threshold(test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies Quick-Pay under NO_TDS (0%):
    - Gross = ₹15,000, TDS = ₹0, Net = ₹15,000
    """
    tenant = test_tenant
    req = QuickContractorPaymentRequest(
        freelancer_name="Ravi Graphics Designer",
        amount=Decimal("15000.00"),
        amount_type="gross",
        service_type="NO_TDS",
        description="Logo and Brand Style Guide Assets",
        disburse_immediately=True
    )

    payment = await PayrollService.quick_pay_contractor(
        session=db_session,
        tenant_id=tenant.id,
        data=req,
        user_id=tenant._test_user.id
    )

    assert payment.gross_amount == Decimal("15000.00")
    assert payment.tds_amount == Decimal("0.00")
    assert payment.net_payable == Decimal("15000.00")
    assert payment.status == "disbursed"


@pytest.mark.asyncio
async def test_yearbook_compensation_summary_aggregation(test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies that PayrollService.get_yearbook_compensation_summary aggregates
    freelancer fees and employee salaries accurately for the Year Book.
    """
    tenant = test_tenant

    # Create 2 quick payments
    req1 = QuickContractorPaymentRequest(
        freelancer_name="Contractor A",
        amount=Decimal("40000.00"),
        amount_type="gross",
        service_type="194J_TECH",
        payment_date=date(2026, 6, 1),
        disburse_immediately=True
    )
    req2 = QuickContractorPaymentRequest(
        freelancer_name="Contractor B",
        amount=Decimal("20000.00"),
        amount_type="gross",
        service_type="194J_PROF",
        payment_date=date(2026, 7, 1),
        disburse_immediately=True
    )
    await PayrollService.quick_pay_contractor(db_session, tenant.id, req1, tenant._test_user.id)
    await PayrollService.quick_pay_contractor(db_session, tenant.id, req2, tenant._test_user.id)

    summary = await PayrollService.get_yearbook_compensation_summary(
        session=db_session,
        tenant_id=tenant.id,
        fiscal_year="2026-27"
    )

    assert summary["fiscal_year"] == "2026-27"
    assert summary["summary"]["contractor_payments_count"] >= 2
    assert summary["summary"]["total_freelancer_gross_note19"] == 60000.00
    # TDS: (40000 * 2%) + (20000 * 10%) = 800 + 2000 = 2800
    assert summary["summary"]["total_freelancer_tds"] == 2800.00
    # Net: 60000 - 2800 = 57200
    assert summary["summary"]["total_freelancer_net"] == 57200.00
    assert summary["summary"]["grand_total_net_outflow"] >= 57200.00


@pytest.mark.asyncio
async def test_withdrawal_reconciliation_contractor_payment(test_tenant: Tenant, db_session: AsyncSession):
    """
    Verifies Bank Statement Withdrawal Reconciliation against Contractor Payouts:
    - Creates an approved contractor payment with Net Payable ₹29,400 (Gross ₹30,000 - 2% TDS)
    - Creates a bank statement withdrawal line of ₹29,400 with matching payment number
    - Executes ReconciliationEngine.reconcile_statement
    - Asserts Tier 1 Exact Match, 100% confidence, and auto-disbursement of contractor payment
    """
    tenant = test_tenant

    # Create contractor payment in approved status (not yet disbursed)
    req = QuickContractorPaymentRequest(
        freelancer_name="Meera Data Analyst",
        amount=Decimal("30000.00"),
        amount_type="gross",
        service_type="194J_TECH",
        disburse_immediately=False  # Awaiting bank clearance
    )
    payment = await PayrollService.quick_pay_contractor(
        session=db_session,
        tenant_id=tenant.id,
        data=req,
        user_id=tenant._test_user.id
    )
    assert payment.status == "approved"
    assert payment.net_payable == Decimal("29400.00")

    # Create Bank Statement with Withdrawal line matching this payout
    stmt = BankStatement(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        bank_name="HDFC",
        account_number="50200012345678",
        statement_from=date(2026, 4, 1),
        statement_to=date(2026, 4, 30),
        opening_balance=Decimal("500000.00"),
        closing_balance=Decimal("470600.00"),
        total_withdrawals=Decimal("29400.00"),
        total_deposits=Decimal("0.00"),
        file_name="hdfc_statement_apr2026.pdf",
        file_sha256="mock_sha256_hash_123456",
        s3_key="vault/bank/hdfc_statement_apr2026.pdf",
        status="unreconciled"
    )
    db_session.add(stmt)
    await db_session.flush()

    line = BankStatementLine(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        statement_id=stmt.id,
        line_number=1,
        transaction_date=date(2026, 4, 15),
        description=f"NEFT OUT TO MEERA DATA ANALYST {payment.payment_number}",
        reference_number=f"NEFT-{payment.payment_number}",
        counterparty_name="Meera Data Analyst",
        payment_channel="NEFT",
        withdrawal_amount=Decimal("29400.00"),
        deposit_amount=Decimal("0.00"),
        running_balance=Decimal("470600.00"),
        reconciliation_tier="unreconciled",
        reconciliation_status="pending"
    )
    db_session.add(line)
    await db_session.commit()

    # Run Reconciliation Engine sweep
    result = await ReconciliationEngine.reconcile_statement(
        session=db_session,
        tenant_id=tenant.id,
        statement_id=stmt.id,
        user_id=tenant._test_user.id
    )

    await db_session.refresh(line)
    await db_session.refresh(payment)

    assert line.reconciliation_status == "reconciled"
    assert line.reconciliation_tier == "tier1_exact"
    assert line.confidence_score == Decimal("100.00")
    assert "Meera Data Analyst" in line.notes
    assert payment.status == "disbursed"
    assert payment.disbursement_journal_id is not None
    assert line.matched_journal_entry_id == payment.disbursement_journal_id
