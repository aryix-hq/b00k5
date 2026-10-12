import uuid
from datetime import timedelta
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_user, oauth2_scheme
from app.core.security import verify_password, get_password_hash, create_access_token, revoke_token
from app.models.tenant import User, TenantUser, Tenant
from app.schemas.auth import LoginRequest, GoogleLoginRequest, Token, UserResponse

router = APIRouter()

@router.post("/google/login", response_model=Token)
async def google_login(payload: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Seamless 1-click Google OAuth / Gmail sign-in.
    Provisions new users dynamically or binds existing user accounts to their organization.
    """
    email_clean = payload.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Invalid Google account email address")

    # 1. Lookup user by email
    result = await db.execute(select(User).where(User.email == email_clean))
    user = result.scalar_one_or_none()

    if not user:
        name_parts = (payload.name or email_clean.split("@")[0].replace(".", " ")).split(maxsplit=1)
        first_name = name_parts[0].capitalize()
        last_name = name_parts[1].capitalize() if len(name_parts) > 1 else "User"

        user = User(
            email=email_clean,
            password_hash=get_password_hash(str(uuid.uuid4())),
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        db.add(user)
        await db.flush()

    # 2. Check existing tenant associations for this user
    all_memberships_res = await db.execute(
        select(TenantUser).where(TenantUser.user_id == user.id).order_by(TenantUser.is_primary.desc(), TenantUser.created_at.asc())
    )
    all_memberships = all_memberships_res.scalars().all()

    membership = None
    if payload.tenant_id:
        for m in all_memberships:
            if m.tenant_id == payload.tenant_id:
                membership = m
                break
        if not membership and all_memberships:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: User is not a member of the requested organization."
            )
    elif all_memberships:
        membership = all_memberships[0]

    if not membership:
        # Brand-new user with no organization: provision an isolated tenant (never attach to an existing tenant)
        from sqlalchemy import text
        rand_suffix = uuid.uuid4().hex[:4].upper()
        unique_pan = f"AABC{rand_suffix[:1]}{uuid.uuid4().int % 9000 + 1000}F"
        new_tenant = Tenant(
            legal_name=f"{user.first_name} {user.last_name} Enterprise Pvt Ltd",
            trade_name=f"{user.first_name} Enterprise",
            pan=unique_pan,
            state_code="29",
            registered_office="",
            currency="INR"
        )
        db.add(new_tenant)
        await db.flush()

        membership = TenantUser(
            tenant_id=new_tenant.id,
            user_id=user.id,
            role="owner",
            is_primary=True
        )
        db.add(membership)
        await db.flush()

        # Provision clean Schedule III Chart of Accounts (zero transactions)
        try:
            await db.execute(text("SELECT seed_tenant_chart_of_accounts(:tid)"), {"tid": str(new_tenant.id)})
        except Exception:
            pass

    await db.commit()

    tenant_id_str = str(membership.tenant_id) if membership else None
    role_str = membership.role.value if hasattr(membership.role, "value") else str(membership.role)

    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": tenant_id_str,
        "role": role_str
    }
    access_token = create_access_token(data=token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "email": user.email,
        "tenant_id": tenant_id_str,
        "role": role_str
    }

@router.post("/login", response_model=Token)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user's primary tenant membership
    tu_stmt = select(TenantUser).where(TenantUser.user_id == user.id)
    if credentials.tenant_id:
        tu_stmt = tu_stmt.where(TenantUser.tenant_id == credentials.tenant_id)
    tu_res = await db.execute(tu_stmt)
    membership = tu_res.scalars().first()

    if credentials.tenant_id and not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: User is not a member of the requested organization."
        )

    tenant_id_str = str(membership.tenant_id) if membership else None
    role_str = (membership.role.value if hasattr(membership.role, "value") else str(membership.role)) if membership else None

    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": tenant_id_str,
        "role": role_str
    }
    access_token = create_access_token(data=token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "email": user.email,
        "tenant_id": tenant_id_str,
        "role": role_str
    }

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Fetch all tenants the user belongs to
    stmt = select(Tenant, TenantUser.role, TenantUser.din).join(
        TenantUser, Tenant.id == TenantUser.tenant_id
    ).where(TenantUser.user_id == current_user.id)
    res = await db.execute(stmt)
    tenants = []
    for tenant, role, din in res.all():
        tenants.append({
            "id": str(tenant.id),
            "legal_name": tenant.legal_name,
            "trade_name": tenant.trade_name,
            "cin": tenant.cin,
            "pan": tenant.pan,
            "gstin": tenant.gstin,
            "state_code": tenant.state_code,
            "role": role,
            "din": din
        })

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "is_active": current_user.is_active,
        "tenants": tenants
    }

@router.post("/logout")
async def logout(
    token: Optional[str] = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user)
):
    """
    DEF-03: Revokes the active JWT access token server-side in Redis.
    Future API requests presenting this token are immediately rejected with 401 Unauthorized.
    """
    if token:
        revoke_token(token)

    return {
        "status": "logged_out",
        "message": "Successfully logged out and session revoked server-side."
    }
