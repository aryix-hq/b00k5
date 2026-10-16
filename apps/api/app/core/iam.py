"""
b00k5 Multi-Tenant Identity & Access Management (IAM) Engine
Implements fine-grained role-based access control (RBAC), multi-company session context,
PostgreSQL Row-Level Security (RLS) injection, and immutable auditor safeguards.

Role Hierarchy:
1. Global Super Admin: Platform host operations, global tenant provisioning, db backup/restore.
2. Company Owner (Founder/Director): Full entity control, invitations, ledger posting, DSC hardware signing.
3. CA / CS (Auditor): Cross-tenant accounting audit access, read-all GL/reports, audit adjustments, dossier exports.
4. Employee: Self-service out-of-pocket receipts upload and own claims tracking. Zero access to GL/Invoices/Banking/Vault.
"""

import uuid
from typing import List, Optional, Set
from fastapi import Request, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.api.deps import get_db, get_current_user, oauth2_scheme
from app.core.security import decode_access_token
from app.models.tenant import User, Tenant, TenantUser


ROLE_ALIASES = {
    "company_owner": {"company_owner", "owner"},
    "owner": {"company_owner", "owner"},
    "ca_auditor": {"ca_auditor", "auditor_ca"},
    "auditor_ca": {"ca_auditor", "auditor_ca"},
    "finance_manager": {"finance_manager"},
    "employee": {"employee"}
}


class IAMContext:
    def __init__(
        self,
        user: User,
        tenant: Optional[Tenant] = None,
        role: str = "employee",
        membership: Optional[TenantUser] = None,
        is_super_admin: bool = False
    ):
        self.user = user
        self.tenant = tenant
        self.role = role
        self.membership = membership
        self.is_super_admin = is_super_admin

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def tenant_id(self) -> Optional[uuid.UUID]:
        return self.tenant.id if self.tenant else None


async def set_postgres_session_context(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str
) -> None:
    """
    Injects transaction-scoped PostgreSQL session variables for RLS enforcement.
    Assumes role b00k5_app (NOBYPASSRLS) and populates:
      app.current_tenant
      app.current_user_id
      app.current_user_role
    """
    t_str = str(tenant_id)
    u_str = str(user_id)
    r_str = str(role).lower().replace("'", "")
    
    # Validate UUID formats to prevent SQL injection
    uuid.UUID(t_str)
    uuid.UUID(u_str)

    await session.execute(text("SET LOCAL ROLE b00k5_app;"))
    await session.execute(text(f"SET LOCAL app.current_tenant = '{t_str}';"))
    await session.execute(text(f"SET LOCAL app.current_user_id = '{u_str}';"))
    await session.execute(text(f"SET LOCAL app.current_user_role = '{r_str}';"))


class RequireRole:
    """
    FastAPI Dependency that resolves the active Tenant and enforces RBAC roles.
    """
    def __init__(self, allowed_roles: Optional[List[str]] = None, allow_super_admin: bool = True):
        self.allowed_roles = allowed_roles
        self.allow_super_admin = allow_super_admin

    async def __call__(
        self,
        request: Request,
        x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
        token: Optional[str] = Depends(oauth2_scheme),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> IAMContext:
        is_super = bool(getattr(current_user, "is_super_admin", False))

        # 1. Resolve Effective Tenant ID
        effective_token = token
        if not effective_token:
            effective_token = request.query_params.get("token") or request.cookies.get("b00k5_token")

        req_tenant_str = x_tenant_id or request.query_params.get("tenant_id")
        target_tenant_id: Optional[uuid.UUID] = None

        if req_tenant_str:
            try:
                target_tenant_id = uuid.UUID(req_tenant_str.strip())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid X-Tenant-ID UUID format: '{req_tenant_str}'"
                )
        elif effective_token:
            tok_payload = decode_access_token(effective_token)
            if tok_payload and tok_payload.get("tenant_id"):
                try:
                    target_tenant_id = uuid.UUID(str(tok_payload.get("tenant_id")))
                except ValueError:
                    pass

        # 2. Super Admin Global Bypass (Platform Operations)
        if is_super and self.allow_super_admin and not target_tenant_id:
            # If endpoint does not strictly require a company context
            if not self.allowed_roles or "super_admin" in self.allowed_roles:
                return IAMContext(user=current_user, tenant=None, role="super_admin", is_super_admin=True)

        # If tenant not specified by header or token, pick the user's primary/first tenant
        if not target_tenant_id:
            first_tu = (await db.execute(
                select(TenantUser).where(TenantUser.user_id == current_user.id, TenantUser.is_active == True)
                .order_by(TenantUser.is_primary.desc(), TenantUser.created_at.desc())
            )).scalars().first()
            if first_tu:
                target_tenant_id = first_tu.tenant_id
            elif is_super:
                first_t = (await db.execute(select(Tenant).order_by(Tenant.created_at.asc()))).scalars().first()
                if first_t:
                    target_tenant_id = first_t.id

        if not target_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No organization selected and user has no active company memberships."
            )

        # 3. Fetch Tenant Record
        tenant = (await db.execute(select(Tenant).where(Tenant.id == target_tenant_id))).scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company entity '{target_tenant_id}' not found."
            )

        # 4. Verify Membership & Role
        membership: Optional[TenantUser] = None
        user_role = "employee"

        if is_super and self.allow_super_admin:
            user_role = "company_owner"
        else:
            tu_stmt = select(TenantUser).where(
                TenantUser.tenant_id == target_tenant_id,
                TenantUser.user_id == current_user.id,
                TenantUser.is_active == True
            )
            membership = (await db.execute(tu_stmt)).scalar_one_or_none()
            if not membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access Denied: You are not an authorized member of company '{tenant.legal_name}'."
                )
            user_role = str(membership.role).lower()

        # 5. Check Role Against Allowed Roles List
        if self.allowed_roles:
            expanded_allowed: Set[str] = set()
            for r in self.allowed_roles:
                expanded_allowed.update(ROLE_ALIASES.get(r.lower(), {r.lower()}))
            
            # Super admin can satisfy company_owner and below
            if is_super and self.allow_super_admin:
                expanded_allowed.add("company_owner")
                expanded_allowed.add("owner")

            if user_role not in expanded_allowed and not (is_super and self.allow_super_admin):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {', '.join(self.allowed_roles)}; your role: '{user_role}'."
                )

        # 6. Inject PostgreSQL RLS Transaction Context
        await set_postgres_session_context(
            session=db,
            tenant_id=tenant.id,
            user_id=current_user.id,
            role=user_role
        )

        # 7. Immutable read-only transaction guard for CAs executing non-adjustment requests
        if user_role in ("ca_auditor", "auditor_ca"):
            is_audit_adj = request.url.path.endswith("/audit-adjustment") and request.method == "POST"
            if not is_audit_adj and request.method in ("GET", "HEAD", "OPTIONS"):
                try:
                    await db.execute(text("SET LOCAL transaction_read_only = on;"))
                except Exception:
                    pass

        return IAMContext(
            user=current_user,
            tenant=tenant,
            role=user_role,
            membership=membership,
            is_super_admin=is_super
        )


# ============================================================================
# Reusable Route Guards
# ============================================================================

async def require_super_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Restricts endpoint execution strictly to platform Super Administrators."""
    if not getattr(current_user, "is_super_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Platform Super Administrator privilege required."
        )
    return current_user


async def require_super_admin_or_owner(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Permits platform Super Administrators, organization owners, directors, or admins."""
    if getattr(current_user, "is_super_admin", False):
        return current_user

    res = await db.execute(
        select(TenantUser).where(
            TenantUser.user_id == current_user.id,
            TenantUser.role.in_(["owner", "company_owner", "finance_manager"])
        )
    )
    if res.scalars().first():
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: Platform Super Administrator or Organization Owner privilege required."
    )


# Guard for Company Owner / Director
require_owner = RequireRole(
    allowed_roles=["company_owner", "owner"],
    allow_super_admin=True
)

# Guard for Company Owner, Director, or Chartered Accountant (Auditor)
require_ca_or_owner = RequireRole(
    allowed_roles=["company_owner", "owner", "ca_auditor", "auditor_ca", "finance_manager"],
    allow_super_admin=True
)

# Guard for All Authorized Company Members (including Employees)
require_any_employee = RequireRole(
    allowed_roles=["company_owner", "owner", "ca_auditor", "auditor_ca", "finance_manager", "employee"],
    allow_super_admin=True
)

