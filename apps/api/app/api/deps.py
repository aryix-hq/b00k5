import uuid
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, set_tenant_context
from app.core.security import decode_access_token, is_token_revoked
from app.models.tenant import User, Tenant, TenantUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # DEF-03: Server-side JWT revocation check (Redis blocklist)
    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user_uuid = uuid.UUID(user_id_str)
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user

from fastapi import Request


def enforce_rbac_policy(role: str, method: str, path: str) -> None:
    """
    Centralized Role-Based Access Control (RBAC) enforcement (SEC-03 & UAT-14):
    - owner: Full access within tenant
    - finance_manager: Finance, ledger, invoices, expenses, reconciliation, reports; blocked from IAM user deletion and destructive system restore
    - auditor_ca: Strictly read-only access (GET/HEAD/OPTIONS + non-mutating verification/export endpoints); blocked from all mutations and IAM modification
    - employee: Restricted to submitting and viewing own expenses; blocked from general ledger, invoices, bank reconciliation, IAM, cap-table/governance, and expense approval/reimbursement
    """
    norm_role = (role or "employee").lower()
    norm_method = (method or "GET").upper()
    norm_path = (path or "").lower()

    if norm_role == "owner":
        return

    if norm_role == "auditor_ca":
        if norm_method in ("GET", "HEAD", "OPTIONS"):
            return
        if any(ro in norm_path for ro in ("/verify", "/calculate", "/export")):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="RBAC Violation: External Auditor (CA) role is read-only and cannot create, modify, or delete records."
        )

    if norm_role == "employee":
        # Employee can only view or submit new expenses (not settle/approve/delete) and view profile/pricing
        if norm_path.startswith("/api/v1/expenses"):
            if norm_method == "GET":
                return
            if norm_method == "POST" and not any(restricted in norm_path for restricted in ("/settle", "/reimburse", "/approve", "/strike")):
                return
        if norm_path.startswith(("/api/v1/auth", "/api/v1/pricing")):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="RBAC Violation: Employee role cannot access restricted finance, ledger, IAM, governance, or cap-table resources."
        )

    if norm_role == "finance_manager":
        if norm_path.startswith("/api/v1/iam") and norm_method in ("POST", "PUT", "PATCH", "DELETE"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="RBAC Violation: Only Organization Owners can modify IAM roles or user memberships."
            )
        if "/backups/restore" in norm_path and norm_method == "POST":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="RBAC Violation: Only Organization Owners can trigger production database restoration."
            )


async def get_current_tenant(
    request: Request = None,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    token: Optional[str] = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    Validates tenant access, enforces RBAC permissions, and applies PostgreSQL Row-Level Security (RLS) context.
    """
    tenant_uuid: Optional[uuid.UUID] = None

    if x_tenant_id:
        try:
            tenant_uuid = uuid.UUID(x_tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID header format")
    elif token:
        payload = decode_access_token(token)
        if payload and payload.get("tenant_id"):
            try:
                tenant_uuid = uuid.UUID(payload.get("tenant_id"))
            except ValueError:
                pass

    if not tenant_uuid:
        # Fall back to user's newest tenant membership
        stmt = select(TenantUser).where(TenantUser.user_id == current_user.id).order_by(TenantUser.created_at.desc())
        res = await db.execute(stmt)
        tu = res.scalars().first()
        if not tu:
            raise HTTPException(status_code=400, detail="User is not associated with any organization")
        tenant_uuid = tu.tenant_id

    # Verify user has access to this tenant
    stmt = select(TenantUser).where(
        TenantUser.user_id == current_user.id,
        TenantUser.tenant_id == tenant_uuid
    )
    res = await db.execute(stmt)
    membership = res.scalars().first()
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied to requested tenant")

    # Enforce centralized RBAC policy if called within an HTTP request context
    if request is not None:
        role_val = membership.role.value if hasattr(membership.role, "value") else str(membership.role)
        enforce_rbac_policy(role_val, request.method, request.url.path)

    # Set PostgreSQL RLS context (switches to b00k5_app role + sets app.current_tenant)
    await set_tenant_context(db, tenant_uuid)

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
    return tenant

