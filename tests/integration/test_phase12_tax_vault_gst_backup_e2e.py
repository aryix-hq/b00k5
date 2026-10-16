import pytest
import io
import uuid
import gzip
from decimal import Decimal
from datetime import date, datetime
from typing import Tuple, Dict, Any
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant, User, TenantUser
from app.models.invoice import Invoice, InvoiceItem, Contact
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.vault import DocumentVault
from app.services.advance_tax_service import AdvanceTaxService
from app.services.db_backup import DatabaseBackupManager, derive_aes_key, encrypt_bytes_aes256_gcm

DATABASE_URL = settings.DATABASE_URL


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


async def setup_test_tenant(db: AsyncSession, name: str, with_gstin: bool = True) -> Tuple[Tenant, User, TenantUser, Dict[str, str]]:
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
        gstin=f"29AABCK{pan_mid}F1Z5" if with_gstin else None,
        state_code="29",
        registered_office="Outer Ring Road, Bengaluru, Karnataka 560103",
        statutory_profile={
            "entity_type": "PVT_LTD",
            "director_name": "Adithya Test",
            "director_din": "09876543",
            "auditor_firm_name": "Apex Audit & Co",
            "auditor_frn": "012345S",
            "authorized_capital_inr": 1000000,
            "total_equity_shares": 100000,
            "face_value_inr": 10,
        }
    )
    user = User(
        id=u_id,
        email=f"user_{rand_hex.lower()}@aryix.test",
        first_name="Test",
        last_name="Operator",
        password_hash="hashed_test_password_not_real",
        is_active=True
    )
    tu = TenantUser(
        id=uuid.uuid4(),
        tenant_id=t_id,
        user_id=u_id,
        role="owner"
    )
    db.add_all([tenant, user, tu])
    await db.commit()

    token = create_access_token({"sub": str(u_id), "tenant_id": str(t_id), "role": "owner"})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(t_id)
    }
    return tenant, user, tu, headers


@pytest.mark.asyncio
async def test_gst_threshold_status_and_zero_tax_mandate(db_session: AsyncSession):
    """
    Validates Section 22 CGST Act Threshold Engine:
    1. If entity has no GSTIN, GET /api/v1/invoices/gst-threshold-status reports has_gstin=False.
    2. Any attempt to issue an invoice with GST > 0% is strictly blocked under Section 32 CGST Act.
    3. Issue of 0% Bill of Supply is permitted.
    """
    tenant, user, tu, headers = await setup_test_tenant(db_session, "NonGST Corp", with_gstin=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Fetch GST status
        status_res = await ac.get("/api/v1/invoices/gst-threshold-status", headers=headers)
        assert status_res.status_code == 200, status_res.text
        data = status_res.json()
        assert data["has_gstin"] is False
        assert data["is_registered"] is False
        assert data["threshold_limit"] == 2000000.0

        # 2. Create customer contact
        contact_res = await ac.post("/api/v1/invoices/contacts", json={
            "name": "Customer Pvt Ltd",
            "is_customer": True,
            "state_code": "29",
            "billing_address": "Bengaluru, Karnataka"
        }, headers=headers)
        assert contact_res.status_code in [200, 201], contact_res.text
        contact_id = contact_res.json()["id"]

        # 3. Attempt to issue 18% tax invoice on unregistered entity -> Must fail under Section 32
        fail_inv = await ac.post("/api/v1/invoices/", json={
            "contact_id": contact_id,
            "invoice_number": f"INV-{uuid.uuid4().hex[:6]}",
            "issue_date": "2026-05-10",
            "due_date": "2026-06-10",
            "place_of_supply": "29",
            "items": [{
                "item_description": "Software Architecture Consulting",
                "hsn_sac_code": "998314",
                "quantity": 1,
                "unit_price": 50000.00,
                "gst_rate_percent": 18.00
            }]
        }, headers=headers)
        assert fail_inv.status_code == 400, "Should block GST on unregistered entity"
        assert "Section 32" in fail_inv.json()["detail"] or "unregistered" in fail_inv.json()["detail"].lower()

        # 4. Issuing 0% Bill of Supply succeeds
        success_inv = await ac.post("/api/v1/invoices/", json={
            "contact_id": contact_id,
            "invoice_number": f"BOS-{uuid.uuid4().hex[:6]}",
            "issue_date": "2026-05-10",
            "due_date": "2026-06-10",
            "place_of_supply": "29",
            "items": [{
                "item_description": "Software Consulting (Bill of Supply)",
                "hsn_sac_code": "998314",
                "quantity": 1,
                "unit_price": 50000.00,
                "gst_rate_percent": 0.00
            }]
        }, headers=headers)
        assert success_inv.status_code in [200, 201], success_inv.text
        inv_data = success_inv.json()
        total_tax = float(inv_data["cgst_total"]) + float(inv_data["sgst_total"]) + float(inv_data["igst_total"])
        assert total_tax == 0.00
        assert float(inv_data["grand_total"]) == 50000.00


@pytest.mark.asyncio
async def test_dynamic_corporate_tax_calculation_engine(db_session: AsyncSession):
    """
    Validates Dynamic Income-tax Act Corporate Rate Engine:
    - Section 115BAA: 22% + 10% Surcharge + 4% HEC = 25.168% effective.
    - Old Regime <= 400 Cr turnover:
        - Profit <= 1 Cr: 25% base + 0% surcharge + 4% HEC = 26.00%
        - Profit 5 Cr: 25% base + 7% surcharge + 4% HEC = 27.82%
        - Profit 15 Cr: 25% base + 12% surcharge + 4% HEC = 29.12%
    - Old Regime > 400 Cr turnover: Base rate 30%.
    - LLP: Flat 30% base, 12% surcharge if > 1 Cr.
    """
    # 1. Section 115BAA
    res_115baa = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="PVT_LTD",
        projected_profit=Decimal("5000000.00"),
        annualized_turnover=Decimal("20000000.00"),
        selected_regime="sec_115baa"
    )
    assert res_115baa["base_rate_pct"] == 22.0
    assert res_115baa["surcharge_pct"] == 10.0
    assert res_115baa["cess_pct"] == 4.0
    assert res_115baa["effective_rate_pct"] == 25.168

    # 2. Old Regime <= 400 Cr, profit <= 1 Cr
    res_old_small = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="PVT_LTD",
        projected_profit=Decimal("8000000.00"), # 80 Lakhs (<= 1 Cr)
        annualized_turnover=Decimal("50000000.00"),
        selected_regime="old_regime"
    )
    assert res_old_small["base_rate_pct"] == 25.0
    assert res_old_small["surcharge_pct"] == 0.0
    assert res_old_small["effective_rate_pct"] == 26.0

    # 3. Old Regime <= 400 Cr, profit between 1 Cr and 10 Cr (7% surcharge)
    res_old_mid = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="PVT_LTD",
        projected_profit=Decimal("50000000.00"), # 5 Crores
        annualized_turnover=Decimal("150000000.00"),
        selected_regime="old_regime"
    )
    assert res_old_mid["base_rate_pct"] == 25.0
    assert res_old_mid["surcharge_pct"] == 7.0
    assert res_old_mid["effective_rate_pct"] == 27.82

    # 4. Old Regime <= 400 Cr, profit > 10 Cr (12% surcharge)
    res_old_large = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="PVT_LTD",
        projected_profit=Decimal("120000000.00"), # 12 Crores
        annualized_turnover=Decimal("250000000.00"),
        selected_regime="old_regime"
    )
    assert res_old_large["base_rate_pct"] == 25.0
    assert res_old_large["surcharge_pct"] == 12.0
    assert res_old_large["effective_rate_pct"] == 29.12

    # 5. Old Regime > 400 Cr turnover -> 30% base rate
    res_old_huge = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="PVT_LTD",
        projected_profit=Decimal("500000000.00"), # 50 Cr
        annualized_turnover=Decimal("5000000000.00"), # 500 Cr (> 400 Cr)
        selected_regime="old_regime"
    )
    assert res_old_huge["base_rate_pct"] == 30.0

    # 6. LLP with profit <= 1 Cr
    res_llp_small = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="LLP",
        projected_profit=Decimal("5000000.00"),
        annualized_turnover=Decimal("10000000.00")
    )
    assert res_llp_small["base_rate_pct"] == 30.0
    assert res_llp_small["surcharge_pct"] == 0.0
    assert res_llp_small["effective_rate_pct"] == 31.2

    # 7. LLP with profit > 1 Cr (12% surcharge)
    res_llp_large = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="LLP",
        projected_profit=Decimal("15000000.00"), # 1.5 Cr
        annualized_turnover=Decimal("30000000.00")
    )
    assert res_llp_large["base_rate_pct"] == 30.0
    assert res_llp_large["surcharge_pct"] == 12.0
    assert res_llp_large["effective_rate_pct"] == 34.944

    # 8. Test endpoint with regime query parameter
    tenant, user, tu, headers = await setup_test_tenant(db_session, "Tax Dynamic Corp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        fc_res = await ac.get("/api/v1/compliance/advance-tax/forecast?fy=2026-27&regime=old_regime&custom_projected_profit=5000000", headers=headers)
        assert fc_res.status_code == 200, fc_res.text
        fc_data = fc_res.json()
        assert "tax_breakdown" in fc_data
        assert fc_data["tax_breakdown"]["regime_code"] == "old_regime"
        assert fc_data["tax_breakdown"]["base_rate_pct"] == 25.0


@pytest.mark.asyncio
async def test_vault_fy_ay_query_filtering(db_session: AsyncSession):
    """
    Validates Document Vault organization by FY / AY:
    - Uploading FY 2025-26 document matches ?fy=2025-26.
    - Permanent documents match ?fy=permanent.
    """
    tenant, user, tu, headers = await setup_test_tenant(db_session, "Vault Filter Org")

    # Seed 2 documents in vault
    doc1 = DocumentVault(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        category="statutory_filing",
        document_name="MGT-7A_25-26.pdf",
        minio_s3_key=f"{tenant.id}/vault/statutory_filing/MGT-7A_25-26.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        metadata_json={"fiscal_year": "2025-26", "assessment_year": "2026-27"}
    )
    doc_perm = DocumentVault(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        category="corporate_legal",
        document_name="Certificate_of_Incorporation.pdf",
        minio_s3_key=f"{tenant.id}/vault/corporate_legal/Certificate_of_Incorporation.pdf",
        file_size_bytes=2048,
        mime_type="application/pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b856",
        metadata_json={"document_type": "COI"}
    )
    db_session.add_all([doc1, doc_perm])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Query FY 2025-26
        res_fy = await ac.get("/api/v1/vault/?fy=2025-26", headers=headers)
        assert res_fy.status_code == 200, res_fy.text
        docs_fy = res_fy.json()
        doc_names_fy = [d["document_name"] for d in docs_fy]
        assert "MGT-7A_25-26.pdf" in doc_names_fy
        assert "Certificate_of_Incorporation.pdf" not in doc_names_fy

        # Query Permanent
        res_perm = await ac.get("/api/v1/vault/?fy=permanent", headers=headers)
        assert res_perm.status_code == 200, res_perm.text
        docs_perm = res_perm.json()
        doc_names_perm = [d["document_name"] for d in docs_perm]
        assert "Certificate_of_Incorporation.pdf" in doc_names_perm


@pytest.mark.asyncio
async def test_minio_backup_checkpointing_and_snapshot_listing(db_session: AsyncSession):
    """
    Validates MinIO Backup Checkpoint & Restore Pipeline:
    - Uploads encrypted backup to MinIO bucket 'b00k5-backups'.
    - Lists snapshots via DatabaseBackupManager.list_minio_checkpoints().
    - Runs 7-Point Staging Integrity Gate on encrypted payload.
    """
    tenant, user, tu, headers = await setup_test_tenant(db_session, "Backup Checkpoint Org")

    # 1. Create simulated dump payload
    simulated_dump = b"PGDMP\x01\x02b00k5_test_database_backup_archive_sample_payload_2026"
    compressed = gzip.compress(simulated_dump)
    secret_key = settings.SECRET_KEY
    key = derive_aes_key(secret_key)
    encrypted_bytes = encrypt_bytes_aes256_gcm(compressed, key)
    filename = f"b00k5_test_checkpoint_{uuid.uuid4().hex[:6]}.sql.gz.enc"

    # 2. Upload to MinIO
    minio_res = DatabaseBackupManager.upload_to_minio(filename, encrypted_bytes)
    assert minio_res["storage_provider"] == "minio"
    assert minio_res["bucket"] == "b00k5-backups"
    assert minio_res["file_size"] == len(encrypted_bytes)

    # 3. List snapshots
    checkpoints = DatabaseBackupManager.list_minio_checkpoints()
    assert any(c["filename"] == filename for c in checkpoints), f"Checkpoint {filename} not listed in MinIO"

    # 4. Verify 7-Point Staging Gate
    gate_res = DatabaseBackupManager.verify_and_stage_restore(
        encrypted_bytes=encrypted_bytes,
        expected_sha256=minio_res["sha256"],
        decryption_secret=secret_key
    )
    assert gate_res["restore_approved"] is True
    assert gate_res["stage_status"] == "RESTORED_AND_VERIFIED"
    assert gate_res["sha256_verified"] == minio_res["sha256"]
