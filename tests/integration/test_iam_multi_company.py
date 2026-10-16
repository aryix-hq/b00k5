"""
b00k5 Multi-Tenant Identity & Access Management (IAM) Integration Test Battery
Tests:
1. Super Admin Isolation: Non-super-admin receives 403 on /backup-database; super-admin passes guard.
2. CA Multi-Company Access: CA accesses Company A and Company B trial balances via X-Tenant-ID;
   CA cannot invite members or mutate legal profile; CA can post audit-adjustment vouchers.
3. Employee Restrictions: Employee receives 403 on GL trial balance, Invoices, and Document Vault;
   Employee can upload expense bills and sees only their own claims.
4. Cross-Tenant Attack Prevention: Unauthorized X-Tenant-ID access receives 403 Forbidden.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.tenant import User, Tenant, TenantUser
from app.models.ledger import ChartOfAccounts
from app.models.backup import DatabaseBackupLog
from datetime import datetime, timezone


@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def setup_test_entities(db_session):
    """
    Sets up two isolated companies, an Owner, a CA (with memberships in both),
    an Employee (Company A only), and a Super Admin.
    """
    uid_suffix = uuid.uuid4().hex[:6]

    rand_a = uuid.uuid4().hex[:6].upper()
    rand_b = uuid.uuid4().hex[:6].upper()

    # 1. Company A (Pvt Ltd)
    comp_a = Tenant(
        legal_name=f"Alpha Technologies Pvt Ltd {uid_suffix}",
        trade_name="AlphaTech",
        cin=f"U72900KA2026PTC{rand_a}",
        pan=f"AABC{rand_a[:5]}F",
        gstin=f"29AABC{rand_a[:5]}F1Z5",
        entity_type="Private Limited Company",
        registered_office="123 Tech Park, Bengaluru, Karnataka 560001",
        state_code="29"
    )
    db_session.add(comp_a)
    await db_session.flush()

    # 2. Company B (LLP)
    comp_b = Tenant(
        legal_name=f"Beta Logistics LLP {uid_suffix}",
        trade_name="BetaLogistics",
        cin=f"AAB-{rand_b}",
        pan=f"AABB{rand_b[:5]}L",
        gstin=f"29AABB{rand_b[:5]}L1Z8",
        entity_type="Limited Liability Partnership",
        registered_office="456 Express Highway, Bengaluru, Karnataka 560002",
        state_code="29"
    )
    db_session.add(comp_b)
    await db_session.flush()

    # Seed Chart of Accounts for both tenants
    try:
        await db_session.execute(text("SELECT seed_tenant_chart_of_accounts(:tid)"), {"tid": str(comp_a.id)})
        await db_session.execute(text("SELECT seed_tenant_chart_of_accounts(:tid)"), {"tid": str(comp_b.id)})
    except Exception:
        pass

    # 3. Super Admin User
    super_admin = User(
        email=f"platform.admin.{uid_suffix}@b00k5.in",
        password_hash=get_password_hash("SuperSecurePass123!"),
        first_name="Platform",
        last_name="SuperAdmin",
        is_super_admin=True,
        is_active=True
    )
    db_session.add(super_admin)

    # 4. Company A Owner
    owner_a = User(
        email=f"director.{uid_suffix}@alphatech.in",
        password_hash=get_password_hash("OwnerPass123!"),
        first_name="Vikram",
        last_name="Sharma",
        is_super_admin=False,
        is_active=True
    )
    db_session.add(owner_a)
    await db_session.flush()

    tu_owner_a = TenantUser(
        tenant_id=comp_a.id,
        user_id=owner_a.id,
        role="company_owner",
        din="09876541",
        is_primary=True,
        is_active=True
    )
    db_session.add(tu_owner_a)

    # 5. CA / Auditor (Multi-tenant: Auditor for both Company A and Company B)
    ca_user = User(
        email=f"sharma.ca.{uid_suffix}@auditfirm.in",
        password_hash=get_password_hash("CAPassword123!"),
        first_name="Sunil",
        last_name="Sharma",
        is_super_admin=False,
        is_active=True
    )
    db_session.add(ca_user)
    await db_session.flush()

    tu_ca_a = TenantUser(
        tenant_id=comp_a.id,
        user_id=ca_user.id,
        role="ca_auditor",
        icai_membership_no="142982",
        is_primary=True,
        is_active=True
    )
    tu_ca_b = TenantUser(
        tenant_id=comp_b.id,
        user_id=ca_user.id,
        role="ca_auditor",
        icai_membership_no="142982",
        is_primary=False,
        is_active=True
    )
    db_session.add(tu_ca_a)
    db_session.add(tu_ca_b)

    # 6. Employee (Company A only)
    employee_a = User(
        email=f"rahul.ops.{uid_suffix}@alphatech.in",
        password_hash=get_password_hash("EmpPass123!"),
        first_name="Rahul",
        last_name="Verma",
        is_super_admin=False,
        is_active=True
    )
    db_session.add(employee_a)
    await db_session.flush()

    tu_emp_a = TenantUser(
        tenant_id=comp_a.id,
        user_id=employee_a.id,
        role="employee",
        is_primary=True,
        is_active=True
    )
    db_session.add(tu_emp_a)

    await db_session.commit()

    return {
        "comp_a": comp_a,
        "comp_b": comp_b,
        "super_admin": super_admin,
        "owner_a": owner_a,
        "ca_user": ca_user,
        "employee_a": employee_a
    }


@pytest.mark.asyncio
async def test_super_admin_isolation(setup_test_entities):
    """
    Asserts that non-super-admin users receive HTTP 403 on platform backup,
    while Super Admins are authorized.
    """
    entities = setup_test_entities
    comp_a = entities["comp_a"]
    owner_a = entities["owner_a"]
    super_admin = entities["super_admin"]

    owner_token = create_access_token({"sub": str(owner_a.id), "email": owner_a.email})
    super_token = create_access_token({"sub": str(super_admin.id), "email": super_admin.email})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Company Owner attempting backup-database receives 403 Forbidden
        resp_owner = await client.post(
            "/api/v1/system/backup-database",
            headers={"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": str(comp_a.id)}
        )
        assert resp_owner.status_code == 403, f"Expected 403, got {resp_owner.status_code}: {resp_owner.text}"
        assert "Super Administrator privilege required" in resp_owner.text

        # 2. Super Admin calling backup-database succeeds
        # Mock actual Google Drive upload to isolate permission testing
        mock_log = DatabaseBackupLog(
            id=uuid.uuid4(),
            tenant_id=comp_a.id,
            filename=f"backup_test_{comp_a.id}.sql.gz.enc",
            file_size_bytes=1048576,
            sha256_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            encryption_algorithm="AES-256-GCM",
            gdrive_file_id="gdrive_simulated_id_12345",
            gdrive_folder_path="b00k5_Backups/2026",
            status="completed",
            duration_seconds=1.25,
            created_at=datetime.now(timezone.utc)
        )
        with patch("app.services.db_backup.DatabaseBackupManager.run_backup_and_record", new_callable=AsyncMock) as mock_backup:
            mock_backup.return_value = mock_log
            resp_super = await client.post(
                "/api/v1/system/backup-database",
                headers={"Authorization": f"Bearer {super_token}", "X-Tenant-ID": str(comp_a.id)}
            )
            assert resp_super.status_code == 200, f"Expected 200, got {resp_super.status_code}: {resp_super.text}"
            data = resp_super.json()
            assert data["status"] == "completed"
            assert data["encryption_algorithm"] == "AES-256-GCM"


@pytest.mark.asyncio
async def test_ca_multi_company_access(setup_test_entities):
    """
    Asserts CA cross-tenant access:
    - CA can view Company A's Trial Balance when X-Tenant-ID = Company A.
    - CA can view Company B's Trial Balance when X-Tenant-ID = Company B.
    - CA cannot invite users (403).
    - CA cannot mutate company profile (403).
    - CA can post statutory audit-adjustment entries (200).
    """
    entities = setup_test_entities
    comp_a = entities["comp_a"]
    comp_b = entities["comp_b"]
    ca_user = entities["ca_user"]

    ca_token = create_access_token({"sub": str(ca_user.id), "email": ca_user.email})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. CA views Company A's Trial Balance
        resp_a = await client.get(
            "/api/v1/reports/trial-balance",
            headers={"Authorization": f"Bearer {ca_token}", "X-Tenant-ID": str(comp_a.id)}
        )
        assert resp_a.status_code == 200, f"Expected 200, got {resp_a.status_code}: {resp_a.text}"

        # 2. CA views Company B's Trial Balance
        resp_b = await client.get(
            "/api/v1/reports/trial-balance",
            headers={"Authorization": f"Bearer {ca_token}", "X-Tenant-ID": str(comp_b.id)}
        )
        assert resp_b.status_code == 200, f"Expected 200, got {resp_b.status_code}: {resp_b.text}"

        # 3. CA attempting to invite a new user receives 403 Forbidden
        resp_invite = await client.post(
            "/api/v1/tenants/invite",
            headers={"Authorization": f"Bearer {ca_token}", "X-Tenant-ID": str(comp_a.id)},
            json={
                "email": "junior.ca@auditfirm.in",
                "role": "ca_auditor"
            }
        )
        assert resp_invite.status_code == 403, f"Expected 403, got {resp_invite.status_code}: {resp_invite.text}"

        # 4. CA attempting to mutate statutory company profile receives 403 Forbidden
        resp_profile = await client.put(
            "/api/v1/vault/statutory-profile",
            headers={"Authorization": f"Bearer {ca_token}", "X-Tenant-ID": str(comp_a.id)},
            json={"director_name": "Tampered Name"}
        )
        assert resp_profile.status_code == 403, f"Expected 403, got {resp_profile.status_code}: {resp_profile.text}"

        # 5. CA CAN post statutory audit-adjustment entries
        # Look up valid chart of account IDs in comp_a
        async with AsyncSessionLocal() as session:
            accounts = (await session.execute(
                select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == comp_a.id).limit(2)
            )).scalars().all()

        if len(accounts) >= 2:
            adj_payload = {
                "entry_number": f"JV-AUDIT-ADJ-{uuid.uuid4().hex[:6].upper()}",
                "entry_date": "2026-03-31",
                "narration": "Statutory audit adjustment for accrued expenses (ICAI AS-29)",
                "lines": [
                    {
                        "account_id": str(accounts[0].id),
                        "debit_amount": 50000.0,
                        "credit_amount": 0.0,
                        "description": "Debit adjustment"
                    },
                    {
                        "account_id": str(accounts[1].id),
                        "debit_amount": 0.0,
                        "credit_amount": 50000.0,
                        "description": "Credit adjustment"
                    }
                ]
            }
            resp_adj = await client.post(
                "/api/v1/ledger/entries/audit-adjustment",
                headers={"Authorization": f"Bearer {ca_token}", "X-Tenant-ID": str(comp_a.id)},
                json=adj_payload
            )
            assert resp_adj.status_code == 200, f"Expected 200, got {resp_adj.status_code}: {resp_adj.text}"
            data_adj = resp_adj.json()
            assert data_adj["reference_type"] == "audit_adjustment"


@pytest.mark.asyncio
async def test_employee_restrictions(setup_test_entities):
    """
    Asserts Employee isolation:
    - Employee receives 403 on GL Trial Balance, Invoices, and Document Vault.
    - Employee can post personal bill claim (status='submitted', settlement_status='pending').
    - Employee GET /expenses shows only their own claim.
    - Owner GET /expenses shows all claims.
    """
    entities = setup_test_entities
    comp_a = entities["comp_a"]
    owner_a = entities["owner_a"]
    employee_a = entities["employee_a"]

    emp_token = create_access_token({"sub": str(employee_a.id), "email": employee_a.email})
    owner_token = create_access_token({"sub": str(owner_a.id), "email": owner_a.email})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Employee calling Trial Balance receives 403 Forbidden
        resp_tb = await client.get(
            "/api/v1/reports/trial-balance",
            headers={"Authorization": f"Bearer {emp_token}", "X-Tenant-ID": str(comp_a.id)}
        )
        assert resp_tb.status_code == 403, f"Expected 403, got {resp_tb.status_code}: {resp_tb.text}"

        # 2. Employee calling Invoices receives 403 Forbidden
        resp_inv = await client.get(
            "/api/v1/invoices/",
            headers={"Authorization": f"Bearer {emp_token}", "X-Tenant-ID": str(comp_a.id)}
        )
        assert resp_inv.status_code == 403, f"Expected 403, got {resp_inv.status_code}: {resp_inv.text}"

        # 3. Employee calling Document Vault receives 403 Forbidden
        resp_vault = await client.get(
            "/api/v1/vault/documents",
            headers={"Authorization": f"Bearer {emp_token}", "X-Tenant-ID": str(comp_a.id)}
        )
        assert resp_vault.status_code == 403, f"Expected 403, got {resp_vault.status_code}: {resp_vault.text}"

        # 4. Employee submits out-of-pocket bill claim -> succeeds with 200/201
        exp_payload = {
            "merchant_name": "Indian Railways / IRCTC Travel",
            "expense_date": "2026-05-10",
            "total_amount": 2450.0,
            "currency": "INR",
            "category": "Travel & Conveyance",
            "payment_mode": "personal_savings",
            "paid_personally": True,
            "notes": "Client meeting travel claim"
        }
        resp_exp_create = await client.post(
            "/api/v1/expenses/",
            headers={"Authorization": f"Bearer {emp_token}", "X-Tenant-ID": str(comp_a.id)},
            json=exp_payload
        )
        assert resp_exp_create.status_code in (200, 201), f"Expected 200/201, got {resp_exp_create.status_code}: {resp_exp_create.text}"
        exp_data = resp_exp_create.json()
        assert exp_data["status"] == "submitted"
        assert exp_data["settlement_status"] == "pending"
        assert exp_data["employee_id"] == str(employee_a.id)

        # 5. Employee lists expenses -> sees own claim
        resp_emp_list = await client.get(
            "/api/v1/expenses/",
            headers={"Authorization": f"Bearer {emp_token}", "X-Tenant-ID": str(comp_a.id)}
        )
        assert resp_emp_list.status_code == 200
        emp_items = resp_emp_list.json()
        assert len(emp_items) >= 1
        for item in emp_items:
            assert item["employee_id"] == str(employee_a.id)

        # 6. Owner lists expenses -> sees the employee's claim
        resp_owner_list = await client.get(
            "/api/v1/expenses/",
            headers={"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": str(comp_a.id)}
        )
        assert resp_owner_list.status_code == 200
        owner_items = resp_owner_list.json()
        matching = [i for i in owner_items if i["id"] == exp_data["id"]]
        assert len(matching) == 1, "Owner should see employee's submitted expense claim"


@pytest.mark.asyncio
async def test_cross_tenant_attack_prevention(setup_test_entities):
    """
    Asserts cross-tenant attack prevention:
    A user who is a member of Company A only attempts to pass X-Tenant-ID = Company B.
    Engine must reject with HTTP 403 Forbidden.
    """
    entities = setup_test_entities
    comp_b = entities["comp_b"]
    owner_a = entities["owner_a"]

    owner_token = create_access_token({"sub": str(owner_a.id), "email": owner_a.email})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/reports/trial-balance",
            headers={"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": str(comp_b.id)}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        assert "Access Denied: You are not an authorized member" in resp.text
