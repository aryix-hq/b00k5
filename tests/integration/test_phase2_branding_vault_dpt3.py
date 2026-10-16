import pytest
import uuid
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant, User, TenantUser
from app.models.vault import DocumentVault
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.services.document_assembly import DocumentAssemblyService
from app.services.pdf_service import PDFService
from app.core.s3 import storage_manager

DATABASE_URL = settings.DATABASE_URL


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_def15_zero_hallucination_logo(db_session: AsyncSession):
    """
    DEF-15 Verification:
    - PDFService must NOT load local file paths from disk.
    - If tenant has no logo_url / logo_s3_key, it must fallback to clean text branding without error.
    """
    invoice_data = {
        "invoice_number": "INV-2026-TEST",
        "seller_name": "Acme Technologies Pvt Ltd",
        "seller_cin": "U72900KA2026PTC123456",
        "seller_gstin": "29ABCDE1234F1Z5",
        "seller_pan": "ABCDE1234F",
        "seller_address": "Bengaluru, Karnataka",
        "issue_date": "2026-10-14",
        "due_date": "2026-10-24",
        "place_of_supply": "29",
        "customer_name": "Test Client Pvt Ltd",
        "subtotal": 10000.0,
        "cgst_total": 900.0,
        "sgst_total": 900.0,
        "igst_total": 0.0,
        "grand_total": 11800.0,
        "line_items": [
            {
                "description": "Enterprise Software Subscription",
                "hsn_sac": "998314",
                "qty": 1,
                "unit_price": 10000.0,
                "taxable_amount": 10000.0,
                "cgst_rate": 9.0,
                "sgst_rate": 9.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
                "total": 11800.0
            }
        ],
        "logo_url": "/tmp/unverified_hallucinated_logo.png"  # Local file path must be ignored
    }
    pdf_bytes = PDFService.generate_simple_invoice_pdf(invoice_data)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_def17_original_document_download(db_session: AsyncSession):
    """
    DEF-17 Verification:
    - When an authentic document is in MinIO, GET /download-document/{code} must stream the original file bytes.
    - Header X-Document-Type must indicate ORIGINAL_AUTHENTIC_RECORD.
    - When allow_extract=false and no document is uploaded, it must return 404 Not Found.
    """
    t_id = uuid.uuid4()
    u_id = uuid.uuid4()
    rand_sfx = uuid.uuid4().hex[:6].upper()

    tenant = Tenant(
        id=t_id,
        legal_name=f"Phase2 Vault Testing Ltd {rand_sfx}",
        trade_name=f"Vault Ltd {rand_sfx}",
        cin=f"U72900KA2026PTC{rand_sfx}",
        pan=f"PANTE{rand_sfx[:4]}T",
        gstin=f"29PANTE{rand_sfx[:4]}T1Z5",
        state_code="29",
        registered_office="456 Tech Park, Bengaluru, Karnataka 560001"
    )
    user = User(
        id=u_id,
        email=f"vault_tester_{rand_sfx.lower()}@phase2.in",
        first_name="Vault",
        last_name="Tester",
        password_hash="hashed_test_password"
    )
    membership = TenantUser(
        tenant_id=t_id,
        user_id=u_id,
        role="owner"
    )
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(membership)
    await db_session.flush()

    # Upload authentic original COI document to MinIO
    orig_content = b"%PDF-1.4\nAuthentic_Certificate_Of_Incorporation_Signed_By_MCA_Registrar\n%%EOF"
    s3_key = f"{t_id}/vault/corporate_legal/COI_Original_{rand_sfx}.pdf"
    storage_manager.upload_document_bytes(
        bucket_name=getattr(settings, "BUCKET_VAULT", "b00k5-vault"),
        object_name=s3_key,
        file_bytes=orig_content,
        content_type="application/pdf"
    )

    doc = DocumentVault(
        id=uuid.uuid4(),
        tenant_id=t_id,
        category="corporate_legal",
        document_name="Certificate of Incorporation",
        document_number=f"COI/{rand_sfx}",
        issue_date=date.today(),
        minio_s3_key=s3_key,
        file_size_bytes=len(orig_content),
        mime_type="application/pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        is_confidential=False,
        metadata_json={
            "document_type": "coi",
            "filename": f"Official_COI_{rand_sfx}.pdf"
        }
    )
    db_session.add(doc)
    await db_session.commit()

    token = create_access_token({"sub": str(u_id), "tenant_id": str(t_id), "role": "owner"})
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Download original document
        res = await ac.get(
            "/api/v1/compliance/download-document/COI?allow_extract=false",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(t_id)}
        )
        assert res.status_code == 200
        assert res.content == orig_content
        assert res.headers.get("X-Document-Type") == "ORIGINAL_AUTHENTIC_RECORD"
        assert f"Official_COI_{rand_sfx}.pdf" in res.headers.get("Content-Disposition", "")

        # 2. Missing document without allow_extract must 404
        res_missing = await ac.get(
            "/api/v1/compliance/download-document/NON_EXISTENT_DOC?allow_extract=false",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(t_id)}
        )
        assert res_missing.status_code == 404


@pytest.mark.asyncio
async def test_def06_dpt3_loan_declaration_and_conversion(db_session: AsyncSession):
    """
    DEF-06 Verification:
    - Generates statutory Rule 2(1)(c)(viii) Own-Funds Declaration PDF and vaults it.
    - When convert_to_loan is True, creates double-entry journal entry:
      DR 2105 == CR 2030, with zero ledger drift.
    """
    t_id = uuid.uuid4()
    u_id = uuid.uuid4()
    rand_sfx = uuid.uuid4().hex[:6].upper()

    tenant = Tenant(
        id=t_id,
        legal_name=f"Phase2 DPT3 Ltd {rand_sfx}",
        trade_name=f"DPT3 Ltd {rand_sfx}",
        cin=f"U72900KA2026PTC{rand_sfx}",
        pan=f"DPTE{rand_sfx[:4]}T",
        gstin=f"29DPTE{rand_sfx[:4]}T1Z5",
        state_code="29",
        registered_office="789 Indiranagar, Bengaluru, Karnataka 560038"
    )
    user = User(
        id=u_id,
        email=f"dpt3_tester_{rand_sfx.lower()}@phase2.in",
        first_name="Director",
        last_name="Adithya",
        password_hash="hashed_test_password"
    )
    membership = TenantUser(
        tenant_id=t_id,
        user_id=u_id,
        role="owner",
        din="09876543"
    )
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(membership)

    # Seed Accounts 2105 and 2030
    acc_2105 = ChartOfAccounts(
        id=uuid.uuid4(),
        tenant_id=t_id,
        code="2105",
        name="Director Reimbursements Payable",
        type="liability",
        sub_type="director_reimbursement",
        normal_balance="credit"
    )
    acc_2030 = ChartOfAccounts(
        id=uuid.uuid4(),
        tenant_id=t_id,
        code="2030",
        name="Long-Term & Director Borrowings",
        type="liability",
        sub_type="director_loan",
        normal_balance="credit"
    )
    db_session.add(acc_2105)
    db_session.add(acc_2030)
    await db_session.commit()

    token = create_access_token({"sub": str(u_id), "tenant_id": str(t_id), "role": "owner"})
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Generate Declaration without loan conversion
        res = await ac.post(
            "/api/v1/compliance/dpt3-declaration",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(t_id)},
            json={
                "director_name": "Adithya Khamithkar",
                "director_din": "09876543",
                "amount": 301554.06,
                "financial_year": "2025-26",
                "convert_to_loan": False
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["document_vault_id"] is not None
        assert data["journal_entry_id"] is None

        # Verify vaulted record
        vault_stmt = select(DocumentVault).where(DocumentVault.id == uuid.UUID(data["document_vault_id"]))
        doc = (await db_session.execute(vault_stmt)).scalar_one_or_none()
        assert doc is not None
        assert doc.category == "equity_governance"
        assert doc.metadata_json.get("document_type") == "dpt3_loan_declaration"

        # 2. Generate with convert_to_loan=True
        res_conv = await ac.post(
            "/api/v1/compliance/dpt3-declaration",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(t_id)},
            json={
                "director_name": "Adithya Khamithkar",
                "director_din": "09876543",
                "amount": 301554.06,
                "financial_year": "2025-26",
                "convert_to_loan": True
            }
        )
        assert res_conv.status_code == 200
        conv_data = res_conv.json()
        assert conv_data["journal_entry_id"] is not None

        # Verify Journal Entry balance
        je_id = uuid.UUID(conv_data["journal_entry_id"])
        jl_stmt = select(JournalLine).where(JournalLine.journal_entry_id == je_id)
        lines = (await db_session.execute(jl_stmt)).scalars().all()
        assert len(lines) == 2
        debits = sum(l.debit_amount for l in lines)
        credits = sum(l.credit_amount for l in lines)
        assert debits == Decimal("301554.06")
        assert credits == Decimal("301554.06")
        assert debits - credits == Decimal("0.00")  # Invariant 1: Ledger Balance strictly zero drift

