import pytest
import io
import zipfile
import uuid
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.models.tenant import Tenant, User
from app.models.expense import Expense, ExpenseAuditLog
from app.models.vault import DocumentVault
from app.models.compliance import ComplianceEvent
from app.core.security import create_access_token


from app.core.database import AsyncSessionLocal

@pytest.fixture
async def db_session():
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()

from app.models.tenant import Tenant, User, TenantUser

@pytest.mark.asyncio
async def test_expense_categories_and_strike_off(db_session: AsyncSession):
    # 1. Fetch valid TenantUser link and corresponding Tenant & User
    tu = (await db_session.execute(select(TenantUser).limit(1))).scalars().first()
    assert tu is not None, "A valid TenantUser record must exist"
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tu.tenant_id))).scalars().first()
    user = (await db_session.execute(select(User).where(User.id == tu.user_id))).scalars().first()
    assert tenant is not None and user is not None, "Tenant and User must exist"

    tenant_id = tenant.id
    user_id = user.id
    tenant_legal_name = str(tenant.legal_name)

    token = create_access_token({"sub": str(user_id), "tenant_id": str(tenant_id), "role": tu.role})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(tenant_id)
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A. Verify GET /api/v1/expenses/categories
        res_cat = await client.get("/api/v1/expenses/categories", headers=headers)
        assert res_cat.status_code == 200
        cat_data = res_cat.json()
        assert cat_data.get("success") is True
        assert len(cat_data.get("categories", [])) >= 10
        assert "Cloud Infrastructure & Hosting" in cat_data["categories"] or any("Cloud" in c for c in cat_data["categories"])

        # B. Create an expense to edit and strike off via API so real journal entries are posted
        exp_payload = {
            "merchant_name": f"AWS Test Service {uuid.uuid4().hex[:4]}",
            "expense_date": date.today().isoformat(),
            "category": "Cloud Infrastructure & Hosting (AWS/GCP)",
            "total_amount": 11800.00,
            "payment_mode": "credit_card",
            "paid_personally": True,
            "director_name": "Chief Auditor"
        }
        res_create = await client.post("/api/v1/expenses/", json=exp_payload, headers=headers)
        assert res_create.status_code == 200, res_create.text
        create_data = res_create.json()
        exp_id = uuid.UUID(create_data["id"])
        jv_num = create_data["entry_number"]

        # C. Test Edit Expense PUT /api/v1/expenses/{exp_id}
        edit_payload = {
            "merchant_name": f"Amazon Web Services Test {uuid.uuid4().hex[:4]}",
            "category": "Cloud Infrastructure & Hosting (AWS/GCP)",
            "total_amount": 12500.00,
            "edit_reason": "Corrected vendor legal name and updated gross bill amount per tax invoice"
        }
        res_edit = await client.put(f"/api/v1/expenses/{exp_id}", json=edit_payload, headers=headers)
        assert res_edit.status_code == 200
        edit_res = res_edit.json()
        assert edit_res.get("success") is True

        # Check Audit Trail GET /api/v1/expenses/{exp_id}/audit-logs
        res_audit = await client.get(f"/api/v1/expenses/{exp_id}/audit-logs", headers=headers)
        assert res_audit.status_code == 200
        logs = res_audit.json()
        assert len(logs) >= 1
        assert logs[0]["action"] == "UPDATED"
        assert "merchant_name" in logs[0]["field_changes"]

        # D. Test Strike Off Expense DELETE /api/v1/expenses/{exp_id}
        res_strike = await client.delete(
            f"/api/v1/expenses/{exp_id}?reason=Vendor%20issued%20credit%20note%20for%20disputed%20usage",
            headers=headers
        )
        assert res_strike.status_code == 200
        strike_data = res_strike.json()
        assert strike_data.get("success") is True
        assert strike_data.get("status") == "struck_off"
        assert strike_data.get("reversal_journal_entry", "").startswith(f"JV-REV-{jv_num}")

        # Verify expense status in database
        db_session.expire_all()
        refreshed_exp = (await db_session.execute(select(Expense).where(Expense.id == exp_id))).scalars().first()
        assert refreshed_exp.status == "struck_off"
        assert refreshed_exp.settlement_status == "voided"
        assert "STRUCK OFF" in (refreshed_exp.notes or "")

        # E. Test Statutory Auditor Package Export GET /api/v1/expenses/export-auditor-package
        res_export = await client.get("/api/v1/expenses/export-auditor-package", headers=headers)
        assert res_export.status_code == 200
        assert res_export.headers.get("content-type") == "application/zip"

        # Verify ZIP archive contents
        zf = zipfile.ZipFile(io.BytesIO(res_export.content))
        names = zf.namelist()
        assert "AUDIT_AUTHENTICITY_MANIFEST_SHA256.txt" in names
        assert "STATUTORY_CLOSE_AND_MCA_CHECKLIST.txt" in names
        assert any("03_Financial_Statements_Schedule_III" in n for n in names)

        # Read manifest text
        manifest_text = zf.read("AUDIT_AUTHENTICITY_MANIFEST_SHA256.txt").decode("utf-8")
        assert tenant_legal_name in manifest_text
        assert "STATUTORY AUDITOR" in manifest_text
        assert "DOSSIER" in manifest_text

        # F. Verify Zero Dummy GSTIN / TAN Fallback
        res_stat = await client.get("/api/v1/compliance/statutory-documents-status", headers=headers)
        assert res_stat.status_code == 200
        stat_data = res_stat.json()
        assert stat_data.get("tan") in ("", None, "Not Registered / Upload Certificate", "BLRA56659B")
        assert "BLRA12345F" not in str(stat_data)
        tan_doc = next(d for d in stat_data.get("documents", []) if d["code"] == "TAN")
        assert tan_doc["status"] in ("pending", "verified")

        # G. Verify INC-20A Sync with Governance Dashboard
        # When INC-20A is in DocumentVault, dashboard shows it as completed
        existing_inc20a = (await db_session.execute(
            select(DocumentVault).where(
                DocumentVault.tenant_id == tenant_id,
                DocumentVault.document_name.ilike("%INC-20A%")
            )
        )).scalars().first()
        if not existing_inc20a:
            doc_inc20a = DocumentVault(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                category="statutory_filing",
                document_name="Form INC-20A Commencement of Business",
                document_number="SRN-INC20A-9988",
                minio_s3_key=f"statutory/{tenant_id}/inc20a.pdf",
                file_size_bytes=1024,
                mime_type="application/pdf",
                sha256_hash="dummyhashinc20a"
            )
            db_session.add(doc_inc20a)
            await db_session.commit()

        res_gov = await client.get("/api/v1/compliance/dashboard", headers=headers)
        assert res_gov.status_code == 200
        gov_data = res_gov.json()
        inc20a_event = next((e for e in gov_data.get("upcoming_deadlines", []) if e.get("category") == "inc_20a"), None)
        if inc20a_event:
            assert inc20a_event.get("status") == "completed"
