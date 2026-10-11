import io
import uuid
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete, text

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant, User, TenantUser
from app.models.vault import DocumentVault
from app.models.expense import Expense, ExpenseAuditLog
from app.models.invoice import Invoice
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.compliance import ComplianceEvent
from app.services.compliance_watchdog import ComplianceWatchdogService
from app.services.bill_analyzer import (
    StatutoryBillAnalyzer,
    SCHEDULE_III_EXPENSE_CATEGORIES,
    get_financial_year,
    get_assessment_year
)


@pytest.fixture
async def temp_org_fixture():
    """
    Provisions a completely isolated temporary organization, user, and compliance calendar.
    In teardown (finally), cleanly deletes all tenant rows and related entities to ensure zero database pollution.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = f"qa_temp_{tenant_id.hex[:8]}@audit.org"
    async with AsyncSessionLocal() as session:
        # Clean up any legacy test tenants
        await session.execute(text("SET LOCAL session_replication_role = 'replica';"))
        legacy_tenants = await session.execute(
            select(Tenant.id).where(Tenant.cin.like("U72900KA2025PTC%"))
        )
        for row in legacy_tenants.scalars().all():
            await session.execute(delete(JournalLine).where(JournalLine.tenant_id == row))
            await session.execute(delete(JournalEntry).where(JournalEntry.tenant_id == row))
            await session.execute(delete(ExpenseAuditLog).where(ExpenseAuditLog.tenant_id == row))
            await session.execute(delete(Expense).where(Expense.tenant_id == row))
            await session.execute(delete(Invoice).where(Invoice.tenant_id == row))
            await session.execute(delete(DocumentVault).where(DocumentVault.tenant_id == row))
            await session.execute(delete(ComplianceEvent).where(ComplianceEvent.tenant_id == row))
            await session.execute(delete(ChartOfAccounts).where(ChartOfAccounts.tenant_id == row))
            await session.execute(delete(TenantUser).where(TenantUser.tenant_id == row))
            await session.execute(delete(Tenant).where(Tenant.id == row))

        # 1. Create Temporary Organization with unique CIN and PAN
        dyn_cin = f"U72900KA2025PTC{tenant_id.hex[:6].upper()}"
        dyn_pan = f"AABCQ{tenant_id.hex[:4].upper()}P"
        temp_tenant = Tenant(
            id=tenant_id,
            legal_name="QA Temp Statutory Accounting Systems Private Limited",
            trade_name="QA Temp Systems",
            cin=dyn_cin,
            pan=dyn_pan,
            gstin=None,  # Zero garbage policy: unverified GSTIN must be None
            state_code="29",
            registered_office="100 Feet Road, Indiranagar, Bengaluru - 560038, Karnataka",
            statutory_profile={
                "directors": [
                    {"name": "Vikram Director", "din": "09876599", "designation": "Director"}
                ]
            }
        )
        session.add(temp_tenant)

        # 2. Create Temporary User & Role Membership
        temp_user = User(
            id=user_id,
            email=email,
            password_hash="temp_bcrypt_hash",
            first_name="QA",
            last_name="Auditor",
            phone="9876543210"
        )
        session.add(temp_user)

        membership = TenantUser(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            role="owner",
            din="09876599"
        )
        session.add(membership)

        # 3. Seed initial Indian statutory compliance milestones
        await ComplianceWatchdogService.seed_initial_statutory_milestones(
            session=session,
            tenant_id=tenant_id,
            incorporation_date=date.today() - timedelta(days=30)
        )

        await session.commit()

    # 4. Generate JWT token
    token = create_access_token({
        "sub": str(user_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "email": email,
        "role": "owner"
    })
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(tenant_id)
    }

    context = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "email": email,
        "token": token,
        "headers": headers
    }

    try:
        yield context
    finally:
        # Cascading teardown: permanently purge temporary organization from PostgreSQL
        async with AsyncSessionLocal() as cleanup_session:
            await cleanup_session.execute(text("SET LOCAL session_replication_role = 'replica';"))
            # Purge child records
            await cleanup_session.execute(delete(JournalLine).where(JournalLine.tenant_id == tenant_id))
            await cleanup_session.execute(delete(JournalEntry).where(JournalEntry.tenant_id == tenant_id))
            await cleanup_session.execute(delete(ExpenseAuditLog).where(ExpenseAuditLog.tenant_id == tenant_id))
            await cleanup_session.execute(delete(Expense).where(Expense.tenant_id == tenant_id))
            await cleanup_session.execute(delete(Invoice).where(Invoice.tenant_id == tenant_id))
            await cleanup_session.execute(delete(DocumentVault).where(DocumentVault.tenant_id == tenant_id))
            await cleanup_session.execute(delete(ComplianceEvent).where(ComplianceEvent.tenant_id == tenant_id))
            await cleanup_session.execute(delete(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant_id))
            await cleanup_session.execute(delete(TenantUser).where(TenantUser.tenant_id == tenant_id))
            await cleanup_session.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()


@pytest.mark.asyncio
async def test_zero_garbage_gst_and_tan_without_upload(temp_org_fixture):
    """
    Requirement 3: Zero Garbage Value Verification.
    When a company has not entered GSTIN or uploaded a GST / TAN certificate,
    the application must NEVER return dummy fallbacks like '29AABCK9012' or '29AABCA1234'.
    GSTIN and TAN must strictly be empty and unverified.
    """
    headers = temp_org_fixture["headers"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/compliance/statutory-documents-status", headers=headers)
        assert res.status_code == 200, f"Error: {res.text}"
        data = res.json()

        # Master company profile attributes
        assert data["gstin"] == "", f"Expected empty GSTIN without upload, got: {data['gstin']}"
        assert data["tan"] == "", f"Expected empty TAN without upload, got: {data['tan']}"

        # 14-document statutory register verification status
        docs = {d["code"]: d for d in data["documents"]}
        assert docs["GST_REG06"]["status"] == "pending"
        assert docs["GST_REG06"]["is_uploaded"] is False
        assert docs["GST_REG06"]["extracted_entities"].get("gstin") == "Not Registered / Upload Certificate"

        assert docs["TAN"]["status"] == "pending"
        assert docs["TAN"]["is_uploaded"] is False
        assert docs["TAN"]["extracted_entities"].get("tan") == "Not Registered / Upload Certificate"


@pytest.mark.asyncio
async def test_tan_upload_and_verification_pipeline(temp_org_fixture):
    """
    Requirement 5: TAN Upload and Statutory Vault Verification.
    Uploads a government TAN allotment letter (Form 49B) with TAN pattern BLRA98765C.
    Verifies that the engine recognizes it as 'tan_letter' (not confused with PAN),
    extracts the TAN, activates TDS compliance, and marks it verified.
    """
    headers = temp_org_fixture["headers"]
    tan_letter_content = b"""%PDF-1.4
    INCOME TAX DEPARTMENT - GOVERNMENT OF INDIA
    FORM NO. 49B - ALLOTMENT OF TAX DEDUCTION AND COLLECTION ACCOUNT NUMBER (TAN)
    To,
    QA Temp Statutory Accounting Systems Private Limited
    Indiranagar, Bengaluru - 560038

    Sir/Madam,
    This is with reference to your application for allotment of Tax Deduction and Collection Account Number (TAN).
    The following TAN has been allotted to you:
    TAN: BLRA98765C
    Category: Company
    Area Code: BLR, AO Type: W, Range: 50, AO No: 1
    Please quote this TAN in all TDS returns and challans.
    """

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ingest TAN letter via smart-ingest
        files = {
            "file": ("TAN_Allotment_Letter_BLRA98765C.pdf", tan_letter_content, "application/pdf")
        }
        data_payload = {
            "category": "tax_registration",
            "doc_type": "tan"
        }
        res = await client.post(
            "/api/v1/vault/smart-ingest",
            headers={"Authorization": headers["Authorization"], "X-Tenant-ID": headers["X-Tenant-ID"]},
            data=data_payload,
            files=files
        )
        assert res.status_code == 200, f"Upload error: {res.text}"
        res_data = res.json()
        assert res_data["success"] is True
        assert res_data["document_type"] == "tan_letter"
        assert res_data["extracted_fields"].get("tan") == "BLRA98765C"

        # Re-check statutory compliance documents status
        status_res = await client.get("/api/v1/compliance/statutory-documents-status", headers=headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["tan"] == "BLRA98765C"

        tan_doc = next((d for d in status_data["documents"] if d["code"] == "TAN"), None)
        assert tan_doc is not None
        assert tan_doc["status"] == "verified"
        assert tan_doc["is_uploaded"] is True
        assert tan_doc["extracted_entities"].get("tan") == "BLRA98765C"


@pytest.mark.asyncio
async def test_inc20a_commencement_governance_synchronization(temp_org_fixture):
    """
    Requirement 5 & Governance Sync:
    When Form INC-20A (Commencement of Business under Section 10A) is uploaded,
    the statutory milestone in the Governance Dashboard must transition to 'completed'.
    """
    headers = temp_org_fixture["headers"]
    inc20a_content = b"""%PDF-1.4
    GOVERNMENT OF INDIA - MINISTRY OF CORPORATE AFFAIRS
    FORM NO. INC-20A
    Declaration for Commencement of Business under Section 10A(1)(a) of the Companies Act, 2013
    Corporate Identity Number (CIN): U72900KA2025PTC889977
    Name of the Company: QA Temp Statutory Accounting Systems Private Limited
    Name of Bank: HDFC Bank Limited
    Account Number: 50200012345678
    Declaration: Every subscriber to the memorandum has paid the value of the shares agreed to be taken by him.
    """

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ingest Form INC-20A
        files = {
            "file": ("Form_INC_20A_Commencement.pdf", inc20a_content, "application/pdf")
        }
        data_payload = {
            "category": "statutory_filing",
            "doc_type": "form_inc_20a"
        }
        res = await client.post(
            "/api/v1/vault/smart-ingest",
            headers={"Authorization": headers["Authorization"], "X-Tenant-ID": headers["X-Tenant-ID"]},
            data=data_payload,
            files=files
        )
        assert res.status_code == 200, f"Upload error: {res.text}"
        res_data = res.json()
        assert res_data["document_type"] == "form_inc_20a"

        # Check Governance Dashboard
        dash_res = await client.get("/api/v1/compliance/dashboard", headers=headers)
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        inc20a_event = next((e for e in dash_data["upcoming_events"] if e["category"] == "inc_20a"), None)
        assert inc20a_event is not None
        assert inc20a_event["status"] == "completed", f"INC-20A expected 'completed', got: {inc20a_event['status']}"


@pytest.mark.asyncio
async def test_bill_analysis_model_date_validation_and_yearbook(temp_org_fixture):
    """
    Requirement 2 & Requirement 6: Intelligent Bill Analysis Model.
    Validates:
    - Accurate extraction of vendor name, date, invoice number, amounts, taxes
    - Financial Year calculation & Year Book routing (e.g. FY 2025-26)
    - Date boundaries validation (future dates rejected)
    - Closed FY warning under AS 5 / Ind AS 8
    """
    bill_content = b"""%PDF-1.4
    AMAZON WEB SERVICES INDIA PRIVATE LIMITED
    TAX INVOICE
    Invoice Number: INV-AWS-2025-8891
    Invoice Date: 15-Aug-2025
    GSTIN: 29AABCA9999F1ZX
    Recipient: QA Temp Statutory Accounting Systems Private Limited
    Description: Amazon Elastic Compute Cloud (EC2) and S3 Storage Services
    Taxable Amount: 10000.00
    IGST @ 18%: 1800.00
    Total Amount Due: 11800.00
    """

    # 1. FY 2025-26 Bill Analysis
    analysis = StatutoryBillAnalyzer.parse_bill_or_invoice(
        file_bytes=bill_content,
        filename="AWS_Invoice_Aug2025.pdf",
        company_gstin=None
    )
    assert analysis["success"] is True
    assert "Amazon" in analysis["merchant_name"] or "AWS" in analysis["merchant_name"]
    assert analysis["invoice_number"] == "INV-AWS-2025-8891"
    assert analysis["total_amount"] == 11800.0
    assert analysis["taxable_amount"] == 10000.0
    assert analysis["igst_amount"] == 1800.0

    # Date Validation
    d_val = analysis["date_validation"]
    assert d_val["financial_year"] == "2025-26"
    assert d_val["assessment_year"] == "2026-27"
    assert d_val["is_valid"] is True
    assert d_val["is_future_date"] is False

    # Year Book Routing
    y_book = analysis["year_book"]
    assert y_book["financial_year"] == "2025-26"
    assert y_book["tab"] == "bills"
    assert "/yearbook?fy=2025-26&tab=bills" in y_book["target_url"]

    # Statutory Schedule III Category
    assert analysis["category_code"] == "4010"
    assert "[4010]" in analysis["category"]
    assert "Cloud Infrastructure" in analysis["category"]

    # 2. Future-dated bill validation
    future_bill = bill_content.replace(b"15-Aug-2025", b"15-Aug-2035")
    future_analysis = StatutoryBillAnalyzer.parse_bill_or_invoice(
        file_bytes=future_bill,
        filename="Future_Bill.pdf"
    )
    assert future_analysis["date_validation"]["is_future_date"] is True
    assert future_analysis["date_validation"]["is_valid"] is False
    assert "future" in future_analysis["date_validation"]["warning"].lower()

    # 3. Closed FY validation (AS 5 / Ind AS 8)
    past_bill = bill_content.replace(b"15-Aug-2025", b"10-May-2023")
    closed_analysis = StatutoryBillAnalyzer.parse_bill_or_invoice(
        file_bytes=past_bill,
        filename="Closed_FY_Bill.pdf",
        closed_fiscal_years={"2023-24": {"is_closed": True}}
    )
    assert closed_analysis["date_validation"]["is_prior_period_closed"] is True
    assert "Prior Period Adjustments" in closed_analysis["date_validation"]["warning"]


@pytest.mark.asyncio
async def test_schedule_iii_categories_and_double_entry_booking(temp_org_fixture):
    """
    Requirement 1: Standard Categories with Codes as per Indian Accounting Standards.
    Validates:
    - /categories endpoint returns all Schedule III categories with 4-digit codes
    - Expense creation dynamically books to the correct nominal account code in ChartOfAccounts
    """
    headers = temp_org_fixture["headers"]
    tenant_id = temp_org_fixture["tenant_id"]
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch categories
        cat_res = await client.get("/api/v1/expenses/categories", headers=headers)
        assert cat_res.status_code == 200
        cat_data = cat_res.json()
        assert len(cat_data["categories"]) >= 16
        assert any("[4010]" in c for c in cat_data["categories"])
        assert any("[4020]" in c for c in cat_data["categories"])
        assert any("[4040]" in c for c in cat_data["categories"])

        # 2. Create expense under [4020] Software Licenses
        exp_payload_1 = {
            "merchant_name": "GitHub Inc",
            "category": "[4020] Software Licenses & SaaS Subscriptions",
            "total_amount": "2500.00",
            "expense_date": "2025-09-10",
            "payment_mode": "company_bank",
            "paid_personally": False
        }
        res_exp1 = await client.post("/api/v1/expenses", json=exp_payload_1, headers=headers)
        assert res_exp1.status_code == 200, f"Expense 1 failed: {res_exp1.text}"

        # 3. Create out-of-pocket personal expense under [4040] Legal & Professional Fees
        exp_payload_2 = {
            "merchant_name": "M/s Juris MCA Legal Associates",
            "category": "[4040] Legal, MCA Compliance & Professional Fees",
            "total_amount": "15000.00",
            "expense_date": "2025-09-12",
            "payment_mode": "personal_savings",
            "paid_personally": True,
            "director_name": "Vikram Director"
        }
        res_exp2 = await client.post("/api/v1/expenses", json=exp_payload_2, headers=headers)
        assert res_exp2.status_code == 200, f"Expense 2 failed: {res_exp2.text}"

    # 4. Verify Double-Entry Ledger Invariants in database
    async with AsyncSessionLocal() as session:
        # Verify Chart of Accounts created with codes 4020 and 4040
        acc_4020 = (await session.execute(
            select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant_id, ChartOfAccounts.code == "4020")
        )).scalar_one_or_none()
        assert acc_4020 is not None
        assert "Software" in acc_4020.name
        assert acc_4020.type == "expense"

        acc_4040 = (await session.execute(
            select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant_id, ChartOfAccounts.code == "4040")
        )).scalar_one_or_none()
        assert acc_4040 is not None
        assert "Legal" in acc_4040.name
        assert acc_4040.type == "expense"

        # Verify Director Reimbursements Payable account (2105) exists for out-of-pocket expense
        acc_2105 = (await session.execute(
            select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant_id, ChartOfAccounts.code == "2105")
        )).scalar_one_or_none()
        assert acc_2105 is not None
        assert acc_2105.type == "liability"

        # Verify Journal Entries balance (Debits == Credits)
        jv_stmt = select(JournalEntry).where(JournalEntry.tenant_id == tenant_id)
        jvs = (await session.execute(jv_stmt)).scalars().all()
        assert len(jvs) == 2
        for jv in jvs:
            lines = (await session.execute(
                select(JournalLine).where(JournalLine.journal_entry_id == jv.id)
            )).scalars().all()
            total_dr = sum(l.debit_amount for l in lines)
            total_cr = sum(l.credit_amount for l in lines)
            assert total_dr == total_cr, f"Journal Entry {jv.entry_number} unbalance: DR {total_dr} != CR {total_cr}"
