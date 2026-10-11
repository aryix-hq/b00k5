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

async def get_current_tenant(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    token: Optional[str] = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    Validates tenant access and applies PostgreSQL Row-Level Security (RLS) context.
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
    if not res.scalars().first():
        raise HTTPException(status_code=403, detail="Access denied to requested tenant")

    # Set PostgreSQL RLS context
    await set_tenant_context(db, tenant_uuid)

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
    return tenant
