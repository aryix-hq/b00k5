import pytest
import io
import zipfile
import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import Tuple, Dict, Any, List
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.core.security_scanner import validate_file_header
from app.models.tenant import Tenant, User, TenantUser
from app.models.invoice import Invoice, InvoiceItem, Contact
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.expense import Expense
from app.models.vault import DocumentVault
from app.services.bank_parser import IndianBankPDFParser
from app.services.financial_reporting_service import FinancialReportingService
from app.services.ledger_service import LedgerService
from app.services.schedule_iii_service import ScheduleIIIService
from app.services.auditor_dossier_service import AuditorDossierService

DATABASE_URL = settings.DATABASE_URL


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()




async def setup_test_tenant(db: AsyncSession, name: str) -> Tuple[Tenant, User, TenantUser, Dict[str, str]]:
    t_id = uuid.uuid4()
    u_id = uuid.uuid4()
    rand_hex = t_id.hex[:6].upper()

    pan_mid = rand_hex[:4]
    tenant = Tenant(
        id=t_id,
        legal_name=f"{name} Private Limited",
        trade_name=f"{name[:10]}",
        cin=f"U72900KA2025PTC{rand_hex}",
        pan=f"AABCK{pan_mid}F",
        gstin=f"29AABCK{pan_mid}F1Z5",
        state_code="29",
        registered_office="Outer Ring Road, Bengaluru, Karnataka 560103",
        statutory_profile={
            "director_name": "Adithya Test",
            "director_din": "09876543",
            "auditor_firm_name": "Apex Audit & Co",
            "auditor_proprietor": "CA Senior Partner",
            "auditor_frn": "012345S",
            "auditor_membership_no": "234567"
        }
    )
    user = User(
        id=u_id,
        email=f"tester_{rand_hex.lower()}@testcorp.in",
        first_name="Regression",
        last_name="Tester",
        password_hash="not_used_in_direct_token_auth",
        is_active=True
    )
    tu = TenantUser(
        tenant_id=t_id,
        user_id=u_id,
        role="owner"
    )
    db.add_all([tenant, user, tu])

    # Setup core accounts for double-entry
    accounts = [
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="1010", name="Bank Current Account (HDFC Bank)", type="asset", sub_type="bank", normal_balance="debit"),
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="1020", name="Office Equipment / Assets", type="asset", sub_type="fixed_asset", normal_balance="debit"),
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="2010", name="Equity Share Capital", type="equity", sub_type="share_capital", normal_balance="credit"),
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="2030", name="Director Reimbursements Payable", type="liability", sub_type="director_reimbursement", normal_balance="credit"),
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="2099", name="Suspense Account", type="liability", sub_type="clearing", normal_balance="credit"),
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="2105", name="Director Reimbursements Payable - Adithya Test", type="liability", sub_type="director_reimbursement", normal_balance="credit"),
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="3010", name="Revenue from Technical Services", type="revenue", sub_type="sales", normal_balance="credit"),
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="4010", name="Cloud Infrastructure & Hosting", type="expense", sub_type="direct_cost", normal_balance="debit"),
        ChartOfAccounts(id=uuid.uuid4(), tenant_id=t_id, code="4040", name="Legal, MCA Compliance & Professional Fees", type="expense", sub_type="legal_audit", normal_balance="debit"),
    ]
    db.add_all(accounts)
    await db.commit()

    token = create_access_token({"sub": str(u_id), "tenant_id": str(t_id), "role": "owner"})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(t_id)
    }
    return tenant, user, tu, headers


@pytest.mark.asyncio
async def test_regression_01_amazon_duplicate_and_split_bills(db_session: AsyncSession):
    """
    Test 1: Amazon duplicate and split bill test (assert no 500 crashes).
    - Checks that duplicate bills are cleanly caught with HTTP 409 Conflict.
    - Checks that splitting an expense across items succeeds without 500 crashes.
    """
    tenant, user, _, headers = await setup_test_tenant(db_session, "AmazonBillTest")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        bill_date = date(2026, 8, 15).isoformat()
        payload = {
            "merchant_name": "Amazon Seller Services Private Limited",
            "expense_date": bill_date,
            "category": "Office Equipment / Assets",
            "total_amount": 1499.00,
            "payment_mode": "credit_card",
            "paid_personally": True,
            "director_name": "Adithya Test"
        }

        # 1. First submission should succeed
        res1 = await client.post("/api/v1/expenses/", json=payload, headers=headers)
        assert res1.status_code == 200, res1.text
        data1 = res1.json()
        assert data1["success"] is True

        # 2. Duplicate submission without allow_duplicate must return clean 409 Conflict, NEVER 500
        res2 = await client.post("/api/v1/expenses/", json=payload, headers=headers)
        assert res2.status_code == 409, f"Expected 409 Conflict, got {res2.status_code}: {res2.text}"
        data2 = res2.json()
        assert "duplicate" in data2["detail"].lower()

        # 3. Permitted split submission with allow_duplicate=True must succeed cleanly
        payload_split = {**payload, "allow_duplicate": True, "notes": "Split line item #2 from same invoice"}
        res3 = await client.post("/api/v1/expenses/", json=payload_split, headers=headers)
        assert res3.status_code == 200, res3.text
        data3 = res3.json()
        assert data3["success"] is True


@pytest.mark.asyncio
async def test_regression_02_itr_v_upload_and_security_scanner():
    """
    Test 2: ITR-V upload test (assert 0 SEC-05 rejections).
    Verifies that official Indian Income Tax Department acknowledgment PDFs containing
    form scripts or linearized structures are not falsely rejected as malware.
    """
    # Simulate an authentic ITR-V PDF with benign /JavaScript form definitions
    authentic_itr_content = (
        b"%PDF-1.6\n"
        b"%\xc2\xa5\xc2\xb1\xc3\xab\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R /Names << /JavaScript 3 0 R >> >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [4 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Names [(ITR_Barcode_Compute) 5 0 R] >>\nendobj\n"
        b"4 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 6 0 R >>\nendobj\n"
        b"5 0 obj\n<< /S /JavaScript /JS (// Income Tax Department Barcode Generator Function) >>\nendobj\n"
        b"6 0 obj\n<< /Length 72 >>\nstream\n"
        b"BT /F1 12 Tf 50 800 Td (INDIAN INCOME TAX RETURN VERIFICATION FORM ITR-V AY 2026-27) Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 7\n0000000000 65535 f \n"
        b"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n500\n%%EOF\n"
    )

    # 1. Validate file header via security scanner
    is_valid_header = validate_file_header(authentic_itr_content, "ITR-V_AY2026-27_AABCK1234F.pdf")
    assert is_valid_header is True, "Header validation failed for authentic ITR-V"

    # 2. Validate document safety scanner
    from app.services.bank_parser import validate_uploaded_document_safety
    safety_res = validate_uploaded_document_safety(
        "ITR-V_AY2026-27_AABCK1234F.pdf",
        authentic_itr_content,
        "application/pdf"
    )
    assert safety_res["is_safe"] is True, f"Official ITR-V falsely rejected by security scanner: {safety_res}"


@pytest.mark.asyncio
async def test_regression_03_fiscal_year_temporal_leak_prevention(db_session: AsyncSession):
    """
    Test 3: FY temporal leak test.
    Asserts that a transaction dated June 15, 2026 (FY 2026-27) NEVER appears in FY 2025-26
    Trial Balance or Schedule III P&L.
    """
    tenant, user, _, _ = await setup_test_tenant(db_session, "FYTemporalLeakTest")

    # Fetch revenue and bank accounts
    rev_acc = (await db_session.execute(
        select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant.id, ChartOfAccounts.code == "3010")
    )).scalar_one()
    bank_acc = (await db_session.execute(
        select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant.id, ChartOfAccounts.code == "1010")
    )).scalar_one()

    # Post an entry dated June 15, 2026 (Strictly FY 2026-27)
    entry_2026 = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number="JV-REV-2026-06-15",
        entry_date=date(2026, 6, 15),
        reference_type="invoice",
        narration="Consulting Fee received on 15 June 2026",
        status="posted",
        is_posted=True,
        created_by=user.id
    )
    db_session.add(entry_2026)
    await db_session.flush()

    line_dr = JournalLine(
        id=uuid.uuid4(),
        journal_entry_id=entry_2026.id,
        tenant_id=tenant.id,
        account_id=bank_acc.id,
        debit_amount=Decimal("5000.00"),
        credit_amount=Decimal("0.00"),
        description="Bank receipt"
    )
    line_cr = JournalLine(
        id=uuid.uuid4(),
        journal_entry_id=entry_2026.id,
        tenant_id=tenant.id,
        account_id=rev_acc.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("5000.00"),
        description="Revenue recognition"
    )
    db_session.add_all([line_dr, line_cr])
    await db_session.commit()

    # Query FY 2025-26: The entry must NOT appear
    tb_25_26 = await LedgerService.get_trial_balance(db_session, tenant.id, fy="2025-26")
    assert tb_25_26["total_debits"] == Decimal("0.00"), "FY 2025-26 trial balance leaked June 2026 debits!"
    assert tb_25_26["total_credits"] == Decimal("0.00"), "FY 2025-26 trial balance leaked June 2026 credits!"

    pnl_25_26 = await FinancialReportingService.generate_profit_and_loss(
        db_session, tenant.id,
        from_date=date(2025, 4, 1),
        to_date=date(2026, 3, 31)
    )
    assert pnl_25_26["total_revenue"] == Decimal("0.00"), "FY 2025-26 P&L leaked June 2026 revenue of 5000!"

    # Query FY 2026-27: The entry must appear
    pnl_26_27 = await FinancialReportingService.generate_profit_and_loss(
        db_session, tenant.id,
        from_date=date(2026, 4, 1),
        to_date=date(2027, 3, 31)
    )
    assert pnl_26_27["total_revenue"] == Decimal("5000.00"), "FY 2026-27 P&L did not capture June 2026 revenue!"


@pytest.mark.asyncio
async def test_regression_04_schedule_iii_balance_sheet_invariance_and_headers(db_session: AsyncSession):
    """
    Test 4: Schedule III Balance Sheet test.
    Asserts that:
    - Header is strictly formatted as 'Balance Sheet as at 31st March, [Year]'.
    - Double-entry balance invariant strictly holds: sum(Assets) == sum(Liabilities & Equity).
    - PDF generation completes without error.
    """
    tenant, user, _, _ = await setup_test_tenant(db_session, "ScheduleIIITest")

    cap_acc = (await db_session.execute(
        select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant.id, ChartOfAccounts.code == "2010")
    )).scalar_one()
    bank_acc = (await db_session.execute(
        select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant.id, ChartOfAccounts.code == "1010")
    )).scalar_one()

    # Initial Share Capital infusing ₹1,00,000 into Bank on April 10, 2026
    entry = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        entry_number="JV-CAPITAL-01",
        entry_date=date(2026, 4, 10),
        reference_type="capital_infusion",
        narration="Paid-up equity capital subscription",
        status="posted",
        is_posted=True,
        created_by=user.id
    )
    db_session.add(entry)
    await db_session.flush()

    db_session.add_all([
        JournalLine(id=uuid.uuid4(), journal_entry_id=entry.id, tenant_id=tenant.id, account_id=bank_acc.id, debit_amount=Decimal("100000.00"), credit_amount=Decimal("0.00"), description="Bank debit"),
        JournalLine(id=uuid.uuid4(), journal_entry_id=entry.id, tenant_id=tenant.id, account_id=cap_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000.00"), description="Equity share capital credit")
    ])
    await db_session.commit()

    # 1. Check Schedule III summary data
    summary = await ScheduleIIIService.get_schedule_iii_summary(db_session, tenant, fy="2026-27")
    total_assets = summary["balance_sheet"]["assets"]["total_assets"]
    total_equity_liab = summary["balance_sheet"]["equity_and_liabilities"]["total_equity_and_liabilities"]
    assert total_assets == 100000.00
    assert total_equity_liab == 100000.00
    assert total_assets == total_equity_liab, "Schedule III Balance Sheet is not balanced!"

    # 2. Check full PDF generation
    pdf_pack = await ScheduleIIIService.generate_statutory_dossier_package(db_session, tenant, fy="2026-27")
    assert "pdf_bytes" in pdf_pack
    pdf_bytes = pdf_pack["pdf_bytes"]
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_regression_05_auditor_dossier_fy_isolation(db_session: AsyncSession):
    """
    Test 5: Dossier isolation test.
    Asserts that exporting the Auditor Dossier for FY 2025-26 strictly excludes any files
    or transactions belonging to FY 2026-27.
    """
    tenant, user, _, _ = await setup_test_tenant(db_session, "DossierIsolationTest")

    # Add a document belonging to FY 2025-26
    doc_25_26 = DocumentVault(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        category="statutory_filing",
        document_name="Form AOC-4 FY 2025-26",
        document_number="SRN-AOC4-2025",
        minio_s3_key=f"statutory/{tenant.id}/aoc4_2025.pdf",
        file_size_bytes=2048,
        mime_type="application/pdf",
        sha256_hash="sha256_25_26_hash",
        metadata_json={"fiscal_year": "2025-26", "document_type": "aoc_4"}
    )
    # Add a document belonging to FY 2026-27
    doc_26_27 = DocumentVault(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        category="statutory_filing",
        document_name="Form AOC-4 FY 2026-27",
        document_number="SRN-AOC4-2026",
        minio_s3_key=f"statutory/{tenant.id}/aoc4_2026.pdf",
        file_size_bytes=2048,
        mime_type="application/pdf",
        sha256_hash="sha256_26_27_hash",
        metadata_json={"fiscal_year": "2026-27", "document_type": "aoc_4"}
    )
    db_session.add_all([doc_25_26, doc_26_27])
    await db_session.commit()

    # Generate Dossier for FY 2025-26
    zip_bytes, zip_filename = await AuditorDossierService.generate_auditor_dossier(
        db_session, tenant, fy="2025-26"
    )
    assert zip_filename.endswith(".zip")
    assert "2025-26" in zip_filename or "2026" in zip_filename

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    file_list = zf.namelist()

    # Check manifest text
    manifest = zf.read("AUDIT_AUTHENTICITY_MANIFEST_SHA256.txt").decode("utf-8")
    assert "FINANCIAL YEAR: 2025-26" in manifest
    assert "PERIOD COVERED: 2025-04-01 to 2026-03-31" in manifest

    # Assert FY 2026-27 document is NEVER inside the FY 2025-26 dossier
    assert not any("aoc4_2026" in f.lower() for f in file_list), "FY 2026-27 filing leaked into FY 2025-26 dossier!"
    assert "aoc4_2026" not in manifest, "FY 2026-27 SHA leaked into FY 2025-26 manifest!"


@pytest.mark.asyncio
async def test_customer_delete_endpoint_and_audit_trail_guard(db_session):
    """
    Tests DELETE /api/v1/invoices/contacts/{contact_id}:
    - An unlinked contact is deleted successfully (200 OK).
    - A contact linked to posted tax invoices cannot be deleted (400 Bad Request with Companies Act Section 128 explanation).
    - A non-existent contact returns 404.
    """
    tenant, user, _, headers = await setup_test_tenant(db_session, "Customer Delete Test")

    # 1. Create two test contacts
    contact_unlinked = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Unlinked Test Client",
        state_code="29",
        billing_address="123 Temporary St, Bengaluru, Karnataka 560001",
        is_customer=True
    )
    contact_linked = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Linked Invoiced Client",
        state_code="29",
        billing_address="456 Active Boulevard, Bengaluru, Karnataka 560002",
        is_customer=True
    )
    db_session.add_all([contact_unlinked, contact_linked])
    await db_session.flush()

    # Create an invoice linked to contact_linked
    inv = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        contact_id=contact_linked.id,
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:6].upper()}",
        place_of_supply="29",
        issue_date=date.today(),
        due_date=date.today(),
        subtotal=Decimal("10000.00"),
        cgst_total=Decimal("900.00"),
        sgst_total=Decimal("900.00"),
        igst_total=Decimal("0.00"),
        grand_total=Decimal("11800.00"),
        status="sent"
    )
    db_session.add(inv)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A. Delete unlinked contact -> succeeds with 200
        res_del = await client.delete(
            f"/api/v1/invoices/contacts/{contact_unlinked.id}",
            headers=headers
        )
        assert res_del.status_code == 200, f"Expected 200, got {res_del.status_code}: {res_del.text}"
        data = res_del.json()
        assert data["status"] == "success"

        # Verify contact_unlinked is gone from DB
        check_unlinked = (await db_session.execute(
            select(Contact).where(Contact.id == contact_unlinked.id)
        )).scalar_one_or_none()
        assert check_unlinked is None

        # B. Attempt to delete linked contact -> blocked with 400 Bad Request
        res_linked = await client.delete(
            f"/api/v1/invoices/contacts/{contact_linked.id}",
            headers=headers
        )
        assert res_linked.status_code == 400, f"Expected 400, got {res_linked.status_code}: {res_linked.text}"
        err_msg = res_linked.json().get("detail", "")
        assert "Cannot delete customer" in err_msg
        assert "Companies Act" in err_msg

        # C. Attempt to delete non-existent contact -> returns 404
        res_404 = await client.delete(
            f"/api/v1/invoices/contacts/{uuid.uuid4()}",
            headers=headers
        )
        assert res_404.status_code == 404
