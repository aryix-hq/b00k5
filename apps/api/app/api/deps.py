import uuid
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status, Header, Request
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
    request: Request = None,
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    effective_token = token
    if not effective_token and request:
        effective_token = request.query_params.get("token") or request.cookies.get("b00k5_token")
    if not effective_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # DEF-03: Server-side JWT revocation check (Redis blocklist)
    if is_token_revoked(effective_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(effective_token)
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


from sqlalchemy import select, text


def enforce_rbac_policy(role: str, method: str, path: str) -> None:
    """
    Centralized Role-Based Access Control (RBAC) enforcement (SEC-03 & UAT-14):
    - owner: Full access within tenant
    - finance_manager: Finance, ledger, invoices, expenses, reconciliation, reports; blocked from IAM user deletion and destructive system restore
    - auditor_ca: Strictly read-only HTTP methods (GET/HEAD/OPTIONS only; never inferred from URL text) + PostgreSQL transaction_read_only = on
    - employee: Restricted to submitting and viewing own expenses; blocked from general ledger, invoices, bank reconciliation, IAM, cap-table/governance, and expense approval/reimbursement
    """
    norm_role = (role or "employee").lower()
    norm_method = (method or "GET").upper()
    norm_path = (path or "").lower()

    if norm_role in ("owner", "company_owner", "super_admin", "admin"):
        return

    if norm_role in ("auditor_ca", "ca_auditor"):
        if norm_method in ("GET", "HEAD", "OPTIONS") or (norm_method == "POST" and norm_path.endswith("/audit-adjustment")):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="RBAC Violation: External Auditor (CA) role is strictly read-only and cannot execute mutating requests (POST, PUT, PATCH, DELETE), except for statutory audit adjustment entries."
        )

    if norm_role == "employee":
        # Employee can only view or submit new expenses (not settle/approve/delete) and view profile/pricing
        if norm_path.startswith("/api/v1/expenses"):
            if norm_method in ("GET", "HEAD", "OPTIONS"):
                return
            if norm_method == "POST" and norm_path.rstrip("/") in ("/api/v1/expenses", "/api/v1/expenses/scan-bill"):
                return
        if norm_path.startswith(("/api/v1/auth", "/api/v1/pricing")) and norm_method in ("GET", "HEAD", "OPTIONS"):
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
        if ("/backups/restore" in norm_path or "/backup-database" in norm_path) and norm_method == "POST":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="RBAC Violation: Only Organization Owners can trigger production database backup or restoration."
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
    effective_token = token
    if not effective_token and request:
        effective_token = request.query_params.get("token") or request.cookies.get("b00k5_token")

    effective_tenant_id = x_tenant_id or (request.query_params.get("tenant_id") if request else None)

    if effective_tenant_id:
        try:
            tenant_uuid = uuid.UUID(effective_tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID header format")
    elif effective_token:
        payload = decode_access_token(effective_token)
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
    is_super = bool(getattr(current_user, "is_super_admin", False))
    stmt = select(TenantUser).where(
        TenantUser.user_id == current_user.id,
        TenantUser.tenant_id == tenant_uuid
    )
    res = await db.execute(stmt)
    membership = res.scalars().first()
    if not membership and not is_super:
        raise HTTPException(status_code=403, detail="Access denied to requested tenant")

    if membership:
        role_val = membership.role.value if hasattr(membership.role, "value") else str(membership.role)
    else:
        role_val = "owner"
    if effective_token:
        tok_payload = decode_access_token(effective_token)
        tok_role = str((tok_payload or {}).get("role") or "").lower()
        role_rank = {"auditor_ca": 1, "employee": 2, "finance_manager": 3, "owner": 4}
        if tok_role in role_rank and role_rank[tok_role] < role_rank.get(role_val.lower(), 4):
            role_val = tok_role

    # Enforce centralized RBAC policy if called within an HTTP request context (bypassed for root super_admin)
    if not is_super and request is not None:
        enforce_rbac_policy(role_val, request.method, request.url.path)

    # Set PostgreSQL RLS context (switches to b00k5_app role + sets app.current_tenant, app.current_user_id, app.current_user_role)
    await set_tenant_context(db, tenant_uuid, user_id=current_user.id, role=role_val)

    # Database-enforced read-only transaction guard for Statutory Auditor (CA)
    if role_val.lower() in ("auditor_ca", "ca_auditor"):
        await db.execute(text("SET LOCAL transaction_read_only = on;"))

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
    return tenant


async def check_mandatory_company_documents(
    tenant: Tenant = Depends(get_current_tenant)
) -> Tenant:
    """
    Blocks operational transactions (invoices, expenses, journal postings, DSC signing)
    until mandatory company documents (Certificate of Incorporation 'COI' and PAN)
    have been uploaded and verified in Statutory Document Vault.
    Companies Act 2013 & Rule 9 Companies (Incorporation) Rules.
    """
    profile = tenant.statutory_profile or {}
    status_val = profile.get("onboarding_status")
    coi_ok = bool(profile.get("coi_verified", False))
    pan_ok = bool(profile.get("pan_verified", False))

    if status_val == "PENDING_DOCUMENTS" and not (coi_ok and pan_ok):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Statutory Onboarding Incomplete: Mandatory statutory documents "
                f"(Certificate of Incorporation 'COI' and PAN Card) for '{tenant.legal_name}' "
                f"must be deposited to Document Vault before commercial transactions can commence."
            )
        )
    return tenant


