import pytest
import uuid
import hashlib
from datetime import date
from decimal import Decimal
from app.core.fiscal_year import calculate_indian_fy_ay, parse_indian_date, get_or_create_fiscal_year
from app.services.expense_categorizer import auto_classify_expense
from app.services.bank_parser import compute_line_fingerprint
from app.models.tenant import Tenant, User
from app.models.ledger import FiscalYear
from app.models.bank import BankStatement, BankStatementLine
from app.models.expense import Expense
from app.core.database import AsyncSessionLocal
from sqlalchemy import select, and_


@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()



def test_dynamic_indian_fy_ay():
    # Pre-2026 Historical
    res_1 = calculate_indian_fy_ay(date(2025, 9, 15))
    assert res_1["fy_label"] == "2025-2026"
    assert res_1["ay_label"] == "2026-2027"

    res_2 = calculate_indian_fy_ay(date(2025, 10, 26))
    assert res_2["fy_label"] == "2025-2026"
    assert res_2["ay_label"] == "2026-2027"

    # Current / Future Dates
    res_3 = calculate_indian_fy_ay(date(2026, 10, 1))
    assert res_3["fy_label"] == "2026-2027"
    assert res_3["ay_label"] == "2027-2028"

    # March Boundary Test (Q4 of FY)
    res_4 = calculate_indian_fy_ay(date(2027, 3, 31))
    assert res_4["fy_label"] == "2026-2027"
    assert res_4["ay_label"] == "2027-2028"

    # April Boundary Test (Q1 of next FY)
    res_5 = calculate_indian_fy_ay(date(2027, 4, 1))
    assert res_5["fy_label"] == "2027-2028"
    assert res_5["ay_label"] == "2028-2029"


def test_expense_auto_categorization():
    assert auto_classify_expense("Amazon Seller Services Private Limited")["account_code"] == "5040"
    assert auto_classify_expense("MINISTRY OF CORPORATE AFFAIRS")["account_code"] == "5030"
    assert auto_classify_expense("Apple India Private Limited")["account_code"] == "1020"
    assert auto_classify_expense("WeWork India Management Pvt Ltd")["account_code"] == "5070"
    assert auto_classify_expense("Razorpay Software Private Limited")["account_code"] == "5020"
    assert auto_classify_expense("BESCOM Electricity")["account_code"] == "5080"


def test_strict_indian_date_parsing():
    d = parse_indian_date("01/10/2026")
    assert d == date(2026, 10, 1)
    assert d.month == 10
    assert d.day == 1

    d2 = parse_indian_date("15/09/2025")
    assert d2 == date(2025, 9, 15)


def test_bank_statement_line_deterministic_fingerprint():
    fp1 = compute_line_fingerprint("50200099998888", "2025-11-01", "413.00", "99693.00", "CHQ-123456")
    fp2 = compute_line_fingerprint("50200099998888", "2025-11-01", "413.00", "99693.00", "chq123456")
    # Sanitized ref should produce identical deterministic fingerprints
    assert fp1 == fp2

    fp3 = compute_line_fingerprint("50200099998888", "2025-11-01", "414.00", "99693.00", "CHQ-123456")
    assert fp1 != fp3


@pytest.mark.asyncio
async def test_get_or_create_fiscal_year_provisioning(db_session):
    tenant = Tenant(
        id=uuid.uuid4(),
        legal_name="FY PROVISION TEST PVT LTD",
        pan=f"ABCDE{uuid.uuid4().hex[:4].upper()}Z",
        state_code="29",
        registered_office="Bengaluru",
        currency="INR"
    )
    db_session.add(tenant)
    await db_session.flush()

    fy_oct = await get_or_create_fiscal_year(db_session, tenant.id, date(2025, 10, 26))
    assert fy_oct.label == "2025-2026"
    assert fy_oct.assessment_year == "2026-2027"

    # Calling again should resolve the existing record idempotently
    fy_again = await get_or_create_fiscal_year(db_session, tenant.id, date(2025, 9, 15))
    assert fy_again.id == fy_oct.id
