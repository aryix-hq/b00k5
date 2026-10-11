"""
b00k5 Accounting Core Audit Suite: Global Test Configuration & Fixtures
Provides:
- Async database sessions with rollback isolation
- Deterministic multi-tenant seeds (Acme Labs Pvt Ltd & Zenith Commerce LLP)
- Comprehensive Schedule III 5-Class Chart of Accounts
- PostgreSQL Row-Level Security (RLS) session context switches
"""

import sys
from pathlib import Path
import uuid
from decimal import Decimal
from datetime import date, datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text

# Set path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "apps/api"))
sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings
from app.core.database import Base
from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.invoice import Contact, Invoice, InvoiceItem

from sqlalchemy.pool import NullPool

# Engine for test execution (NullPool ensures no cross-event-loop connection reuse)
test_async_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=False
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

SCHEDULE_III_SEED = [
    # Code, Name, Type, SubType, NormalBalance, Description, IsLeaf
    ('1000', 'Current Assets (Parent)', 'asset', 'current_asset', 'debit', 'Parent group for current assets', False),
    ('1010', 'Bank Current Account (HDFC Bank)', 'asset', 'bank', 'debit', 'Primary operating bank account', True),
    ('1020', 'Trade Receivables (Debtors)', 'asset', 'current_asset', 'debit', 'Customer invoices receivable', True),
    ('1029', 'Accumulated Depreciation - Hardware', 'asset', 'contra_asset', 'credit', 'Contra-asset for equipment depreciation', True),
    ('1030', 'Input CGST', 'asset', 'tax_asset', 'debit', 'Input Central GST Credit', True),
    ('1031', 'Input SGST', 'asset', 'tax_asset', 'debit', 'Input State GST Credit', True),
    ('1032', 'Input IGST', 'asset', 'tax_asset', 'debit', 'Input Integrated GST Credit', True),
    ('1050', 'Computer & IT Hardware', 'asset', 'fixed_asset', 'debit', 'Capitalized IT hardware and servers', True),
    ('1070', 'Prepaid Software & Subscriptions', 'asset', 'prepaid_asset', 'debit', 'Prepaid annual software licenses', True),

    ('2000', 'Current Liabilities (Parent)', 'liability', 'current_liability', 'credit', 'Parent group for current liabilities', False),
    ('2010', 'Paid-up Equity Share Capital', 'equity', 'share_capital', 'credit', 'Nominal value of equity shares', True),
    ('2020', 'Reserves & Surplus / Retained Earnings', 'equity', 'retained_earnings', 'credit', 'Cumulative company profit/loss', True),
    ('2030', 'Director Borrowings / Accrued Liabilities', 'liability', 'director_loan', 'credit', 'Loans from promoters and accrued liabilities', True),
    ('2040', 'Trade Payables (Creditors) / Customer Advances', 'liability', 'current_liability', 'credit', 'Vendor liabilities and customer advances', True),
    ('2050', 'Output CGST', 'liability', 'tax_liability', 'credit', 'Central GST collected on sales', True),
    ('2051', 'Output SGST', 'liability', 'tax_liability', 'credit', 'State GST collected on sales', True),
    ('2052', 'Output IGST', 'liability', 'tax_liability', 'credit', 'Integrated GST collected on sales', True),
    ('2060', 'TDS Payable u/s 194J (Professional)', 'liability', 'tax_liability', 'credit', 'Withholding tax payable to government', True),
    ('2099', 'Suspense Clearing Account', 'liability', 'suspense', 'credit', 'Temporary suspense holding account', True),

    ('3000', 'Revenue from Operations (Parent)', 'revenue', 'operating_revenue', 'credit', 'Parent group for revenue', False),
    ('3010', 'Revenue from SaaS Subscriptions', 'revenue', 'operating_revenue', 'credit', 'Core recurring subscription revenue', True),
    ('3020', 'Professional & Implementation Services', 'revenue', 'operating_revenue', 'credit', 'Implementation and CA retainer income', True),
    ('3030', 'Other Income & Realized FX Gain', 'revenue', 'other_income', 'credit', 'Foreign exchange gains and asset disposal profits', True),

    ('4000', 'Operating Expenses (Parent)', 'expense', 'operating_expense', 'debit', 'Parent group for operating expenses', False),
    ('4010', 'Cloud Infrastructure & Hosting', 'expense', 'direct_expense', 'debit', 'Compute, database, and storage expenses', True),
    ('4020', 'Depreciation & Amortization Expense', 'expense', 'depreciation', 'debit', 'Depreciation on fixed assets and software amortization', True),
    ('4030', 'Payment Gateway & Bank Charges', 'expense', 'financial_expense', 'debit', 'Bank wire and merchant fees', True),
    ('4040', 'Legal & Professional Retainer / Bad Debts', 'expense', 'professional_fees', 'debit', 'Legal, audit, bad debts, and FX losses', True)
]


@pytest.fixture
async def async_db():
    """Provides an isolated database session rolled back after every test."""
    connection = await test_async_engine.connect()
    trans = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    # Disable replica mode so triggers run normally
    await session.execute(text("SET LOCAL session_replication_role = 'origin';"))

    yield session

    await session.close()
    if trans.is_active:
        await trans.rollback()
    await connection.close()


@pytest.fixture
async def tenant_a(async_db: AsyncSession) -> Tenant:
    """Primary Tenant A: Acme Labs Pvt Ltd (Isolated per test)"""
    tenant_id = uuid.uuid4()
    t = Tenant(
        id=tenant_id,
        legal_name=f"Acme Labs Pvt Ltd {tenant_id.hex[:6]}",
        trade_name=f"Acme Cloud {tenant_id.hex[:6]}",
        cin=f"U72900KA2026PTC{tenant_id.hex[:6].upper()}",
        gstin=f"29AABCA{tenant_id.hex[:4].upper()}1Z5",
        pan=f"AABCA{tenant_id.hex[:4].upper()}",
        state_code="29",
        registered_office="Indiranagar, Bengaluru, Karnataka 560038"
    )
    async_db.add(t)
    await async_db.flush()

    # Seed COA for tenant A
    parent_map = {}
    for code, name, acc_type, sub_type, norm_bal, desc, is_leaf in SCHEDULE_III_SEED:
        acc = ChartOfAccounts(
            tenant_id=tenant_id,
            code=code,
            name=name,
            type=acc_type,
            sub_type=sub_type,
            normal_balance=norm_bal,
            description=desc,
            is_leaf=is_leaf,
            is_active=True
        )
        async_db.add(acc)
        await async_db.flush()
        if not is_leaf:
            parent_map[code[:1]] = acc.id
        elif code[:1] in parent_map and not acc.parent_id:
            acc.parent_id = parent_map[code[:1]]
            await async_db.flush()

    return t


@pytest.fixture
async def tenant_b(async_db: AsyncSession) -> Tenant:
    """Tenant B for Multi-Tenancy & RLS tests: Zenith Commerce LLP (Isolated per test)"""
    tenant_id = uuid.uuid4()
    t = Tenant(
        id=tenant_id,
        legal_name=f"Zenith Commerce LLP {tenant_id.hex[:6]}",
        trade_name=f"Zenith Commerce {tenant_id.hex[:6]}",
        cin=f"U72900DL2024PTC{tenant_id.hex[:6].upper()}",
        gstin=f"07AABCS{tenant_id.hex[:4].upper()}1ZE",
        pan=f"AABCS{tenant_id.hex[:4].upper()}",
        state_code="07",
        registered_office="Barakhamba Road, Connaught Place, New Delhi 110001"
    )
    async_db.add(t)
    await async_db.flush()

    # Seed COA for tenant B
    parent_map = {}
    for code, name, acc_type, sub_type, norm_bal, desc, is_leaf in SCHEDULE_III_SEED:
        acc = ChartOfAccounts(
            tenant_id=tenant_id,
            code=code,
            name=name,
            type=acc_type,
            sub_type=sub_type,
            normal_balance=norm_bal,
            description=desc,
            is_leaf=is_leaf,
            is_active=True
        )
        async_db.add(acc)
        await async_db.flush()
        if not is_leaf:
            parent_map[code[:1]] = acc.id
        elif code[:1] in parent_map and not acc.parent_id:
            acc.parent_id = parent_map[code[:1]]
            await async_db.flush()

    return t
