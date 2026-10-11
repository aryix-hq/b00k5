import pytest
from datetime import date
from decimal import Decimal
import uuid
from app.services.bill_analyzer import StatutoryBillAnalyzer, STANDARD_EXPENSE_CATEGORIES
from app.services.bill_invoice_parser import BillInvoiceParser
from app.core.fiscal_year import get_financial_year, is_date_in_fy

@pytest.fixture
async def db_session():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from app.core.config import settings
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()

def test_statutory_date_extraction_and_fy_scoping():
    """
    Verifies that statutory bills extract exact dates and never default to the upload year:
    - Amazon Seller Services: 26/10/2025 -> 2025-10-26 -> FY 2025-26
    - Ministry of Corporate Affairs: 15/9/2025 -> 2025-09-15 -> FY 2025-26
    - Apple India: 1/10/2025 or October 1, 2025 -> 2025-10-01 -> FY 2025-26 (NOT FY 2026-27!)
    - 2-digit year format: 26.10.25 -> 2025-10-26 -> FY 2025-26
    """
    # 1. Amazon Seller Services
    amazon_sample = """
    Regd Office: Amazon Seller Services Private Limited
    Tax Invoice Date: 26/10/2025
    Invoice Number: IN-BLR-2025-001
    Total Amount: INR 0.36
    """
    d_amazon = StatutoryBillAnalyzer._extract_date(amazon_sample)
    assert d_amazon == date(2025, 10, 26)
    assert get_financial_year(d_amazon) == "2025-26"
    assert is_date_in_fy(d_amazon, "2025-26") is True
    assert is_date_in_fy(d_amazon, "2026-27") is False

    # 2. Ministry of Corporate Affairs
    mca_sample = """
    GOVERNMENT OF INDIA
    MINISTRY OF CORPORATE AFFAIRS
    Payment Challan
    Date of Payment: 15/9/2025
    Amount: Rs. 300.00
    """
    d_mca = StatutoryBillAnalyzer._extract_date(mca_sample)
    assert d_mca == date(2025, 9, 15)
    assert get_financial_year(d_mca) == "2025-26"
    assert is_date_in_fy(d_mca, "2025-26") is True
    assert is_date_in_fy(d_mca, "2026-27") is False

    # 3. Apple India (Day first, month first, and slash/dot variations)
    apple_sample_slash = """
    Apple India Private Limited
    19th Floor, Concorde Tower C, UB City
    Invoice Date: 1/10/2025
    Invoice # 9210048123
    Total Payable: INR 1,84,900.00
    """
    d_apple1 = StatutoryBillAnalyzer._extract_date(apple_sample_slash)
    assert d_apple1 == date(2025, 10, 1)
    assert get_financial_year(d_apple1) == "2025-26"

    apple_sample_text_month = """
    Apple India Private Limited
    Date of Invoice: October 1, 2025
    Invoice Number: 9210048124
    Grand Total: 184900.00
    """
    d_apple2 = StatutoryBillAnalyzer._extract_date(apple_sample_text_month)
    assert d_apple2 == date(2025, 10, 1)
    assert get_financial_year(d_apple2) == "2025-26"

    # 4. Two-digit year
    two_digit_sample = """
    Supplier: Quick Host Tech
    Date: 26.10.25
    Total: 500.00
    """
    d_two_digit = StatutoryBillAnalyzer._extract_date(two_digit_sample)
    assert d_two_digit == date(2025, 10, 26)
    assert get_financial_year(d_two_digit) == "2025-26"


def test_expense_category_auto_detection():
    """
    Verifies statutory auto-classification into Indian Schedule III nominal accounts:
    - Amazon Seller Services -> [4160] Marketplace, E-Commerce & Platform Fees
    - MCA -> [4040] Legal, MCA Compliance & Professional Fees
    - Apple India -> [4060] Office Equipment, Computers & IT Hardware
    - AWS -> [4010] Cloud Infrastructure & Hosting (AWS/GCP)
    - Razorpay -> [4030] Payment Gateway & Bank Wire Charges
    """
    # 1. Amazon Seller Services
    cat_amazon = StatutoryBillAnalyzer._classify_category(
        text="Regd Office: Amazon Seller Services Private Limited, Seller Fee Invoice",
        merchant_name="Amazon Seller Services Private Limited"
    )
    assert cat_amazon["code"] == "4160"
    assert "Marketplace" in cat_amazon["name"]

    # 2. MCA
    cat_mca = StatutoryBillAnalyzer._classify_category(
        text="MINISTRY OF CORPORATE AFFAIRS - ROC Challan Payment for Form AOC-4",
        merchant_name="MINISTRY OF CORPORATE AFFAIRS"
    )
    assert cat_mca["code"] == "4040"
    assert "Legal, MCA" in cat_mca["name"]

    # 3. Apple India
    cat_apple = StatutoryBillAnalyzer._classify_category(
        text="Apple India Private Limited - MacBook Pro 16 M3 Max, Serial # C02G9012",
        merchant_name="Apple India Private Limited"
    )
    assert cat_apple["code"] == "4060"
    assert "Office Equipment, Computers & IT Hardware" in cat_apple["name"]

    # 4. AWS
    cat_aws = StatutoryBillAnalyzer._classify_category(
        text="Amazon Web Services India Pvt Ltd - Monthly Cloud Compute and S3 Storage",
        merchant_name="Amazon Web Services"
    )
    assert cat_aws["code"] == "4010"
    assert "Cloud Infrastructure" in cat_aws["name"]

    # 5. Razorpay
    cat_razorpay = StatutoryBillAnalyzer._classify_category(
        text="Razorpay Software Private Limited - Payment Gateway Merchant Processing Fee",
        merchant_name="Razorpay"
    )
    assert cat_razorpay["code"] == "4030"
    assert "Payment Gateway" in cat_razorpay["name"]


@pytest.mark.asyncio
async def test_expense_deduplication_engine(db_session):
    """
    Asserts zero duplicates allowed for expenses/bills:
    Attempts to insert the same merchant + amount + date must be blocked.
    """
    from app.models.tenant import Tenant, User
    from app.models.expense import Expense

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        legal_name="DEDUP TEST PRIVATE LIMITED",
        pan=f"ABCDE{uuid.uuid4().hex[:4].upper()}Z",
        state_code="29",
        registered_office="Bengaluru, Karnataka",
        currency="INR"
    )
    db_session.add(tenant)

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"tester-{uuid.uuid4().hex[:6]}@example.com",
        password_hash="dummy_hash",
        first_name="Audit",
        last_name="Tester"
    )
    db_session.add(user)
    await db_session.flush()

    # Create initial active expense
    e1 = Expense(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        employee_id=user_id,
        merchant_name="Regd Office: Amazon Seller Services Private Limited",
        total_amount=Decimal("0.36"),
        expense_date=date(2025, 10, 26),
        category="[4160] Marketplace, E-Commerce & Platform Fees",
        status="submitted",
        settlement_status="pending"
    )
    db_session.add(e1)
    await db_session.flush()

    # 1. Exact duplicate check
    is_dup, reason = await BillInvoiceParser.check_expense_duplicate(
        session=db_session,
        tenant_id=tenant_id,
        merchant_name="Regd Office: Amazon Seller Services Private Limited",
        total_amount=Decimal("0.36"),
        expense_date=date(2025, 10, 26)
    )
    assert is_dup is True
    assert "Duplicate bill detected" in reason

    # 2. Normalized vendor name duplicate check (without 'Regd Office:')
    is_dup2, reason2 = await BillInvoiceParser.check_expense_duplicate(
        session=db_session,
        tenant_id=tenant_id,
        merchant_name="Amazon Seller Services Private Limited",
        total_amount=Decimal("0.36"),
        expense_date=date(2025, 10, 26)
    )
    assert is_dup2 is True

    # 3. Different date -> Not duplicate
    is_dup3, _ = await BillInvoiceParser.check_expense_duplicate(
        session=db_session,
        tenant_id=tenant_id,
        merchant_name="Amazon Seller Services Private Limited",
        total_amount=Decimal("0.36"),
        expense_date=date(2025, 11, 26)
    )
    assert is_dup3 is False


@pytest.mark.asyncio
async def test_bank_statement_deduplication_engine(db_session):
    """
    Asserts zero duplicates allowed for bank statements:
    Checks statement period and account number.
    """
    from app.models.tenant import Tenant
    from app.models.bank import BankStatement
    from sqlalchemy import select, and_

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        legal_name="BANK DEDUP TEST PRIVATE LIMITED",
        pan=f"ABCDE{uuid.uuid4().hex[:4].upper()}Z",
        state_code="29",
        registered_office="Bengaluru, Karnataka",
        currency="INR"
    )
    db_session.add(tenant)
    await db_session.flush()

    acc_num = "50200099998888"
    stmt_from = date(2025, 11, 1)
    stmt_to = date(2025, 11, 30)

    # Insert existing statement
    existing_stmt = BankStatement(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        bank_name="HDFC",
        account_number=acc_num,
        statement_from=stmt_from,
        statement_to=stmt_to,
        opening_balance=Decimal("0.00"),
        closing_balance=Decimal("99693.00"),
        total_withdrawals=Decimal("413.00"),
        total_deposits=Decimal("100106.00"),
        file_name="Acme_Labs_Private_Limited_November_2025.pdf",
        s3_key=f"{tenant_id}/statements/November_2025.pdf",
        status="parsed"
    )
    db_session.add(existing_stmt)
    await db_session.flush()

    # Query for potential duplicate
    dup_q = select(BankStatement).where(
        and_(
            BankStatement.tenant_id == tenant_id,
            BankStatement.account_number == acc_num,
            BankStatement.statement_from == stmt_from,
            BankStatement.statement_to == stmt_to
        )
    )
    found = (await db_session.execute(dup_q)).scalars().first()
    assert found is not None
    assert found.file_name == "Acme_Labs_Private_Limited_November_2025.pdf"
