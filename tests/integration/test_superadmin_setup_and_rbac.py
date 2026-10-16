import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash, create_access_token
from app.models.tenant import User, Tenant, TenantUser


@pytest.mark.asyncio
async def test_setup_wizard_provisions_super_admin():
    """
    Verifies that POST /api/v1/setup/wizard:
    1. Creates the organization founder user with is_super_admin = True.
    2. Issues an access token with is_super_admin = True claims.
    3. Returns is_super_admin = True in response payload.
    """
    transport = ASGITransport(app=app)
    unique_id = uuid.uuid4().hex[:6]
    admin_email = f"superadmin_{unique_id}@testorg.com"
    org_pan = f"AAAC{unique_id[:2].upper()}123{unique_id[2:3].upper()}"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/setup/wizard",
            json={
                "admin_email": admin_email,
                "admin_password": "SuperSecretPass123!",
                "admin_first_name": "Adithya",
                "admin_last_name": "Khamithkar",
                "admin_din": "09876543",
                "legal_name": f"Test SuperAdmin Corp {unique_id}",
                "cin": f"U72900KA2026PTC{unique_id[:6].upper()}",
                "pan": org_pan,
                "state_code": "29",
                "registered_office": "Bengaluru, Karnataka",
                "incorporation_date": "2026-01-15"
            }
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["is_super_admin"] is True
        assert data["role"] == "owner"
        assert "access_token" in data
        tenant_id = data["tenant_id"]

        # Check DB user record directly
        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).where(User.email == admin_email))
            user = user_res.scalar_one_or_none()
            assert user is not None
            assert user.is_super_admin is True

            # Test login endpoint returns is_super_admin
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": admin_email, "password": "SuperSecretPass123!"}
            )
            assert login_res.status_code == 200, login_res.text
            login_data = login_res.json()
            assert login_data["is_super_admin"] is True

            # Test /me endpoint returns is_super_admin
            token = login_data["access_token"]
            me_res = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert me_res.status_code == 200, me_res.text
            me_data = me_res.json()
            assert me_data["is_super_admin"] is True

            # Clean up
            await session.execute(text(f"DELETE FROM tenant_users WHERE user_id = '{user.id}';"))
            await session.execute(text(f"DELETE FROM tenants WHERE id = '{tenant_id}';"))
            await session.execute(text(f"DELETE FROM users WHERE id = '{user.id}';"))
            await session.commit()

