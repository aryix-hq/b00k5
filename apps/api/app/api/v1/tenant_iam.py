"""
Multi-Company Tenant Context, IAM Memberships, and Invitation Controller
Provides:
- GET /api/v1/tenants/my-companies
- POST /api/v1/auth/switch-tenant
- POST /api/v1/tenants/invite
- POST /api/v1/tenants/accept-invite
- GET /api/v1/tenants/members
- DELETE /api/v1/tenants/members/{membership_id}
"""

import uuid
import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_user
from app.core.iam import require_owner, require_ca_or_owner, IAMContext
from app.core.security import create_access_token, get_password_hash
from app.models.tenant import User, Tenant, TenantUser, TenantInvitation


router = APIRouter()


class CompanySummaryResponse(BaseModel):
    id: uuid.UUID
    legal_name: str
    trade_name: Optional[str] = None
    cin: Optional[str] = None
    pan: str
    gstin: Optional[str] = None
    entity_type: str
    role: str
    is_primary: bool
    is_archived: bool = False
    logo_url: Optional[str] = None


class AdminCreateTenantRequest(BaseModel):
    legal_name: str
    trade_name: Optional[str] = None
    entity_type: str = "Private Limited Company"
    pan: str
    cin: Optional[str] = None
    gstin: Optional[str] = None
    state_code: str = "29"
    registered_office: str = "Bangalore, Karnataka, India"
    currency: str = "INR"
    admin_din: Optional[str] = None
    incorporation_date: Optional[str] = None



class SwitchTenantRequest(BaseModel):
    tenant_id: uuid.UUID


class SwitchTenantResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: uuid.UUID
    legal_name: str
    cin: Optional[str] = None
    role: str
    is_super_admin: bool


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str  # company_owner, ca_auditor, finance_manager, employee
    din: Optional[str] = None
    icai_membership_no: Optional[str] = None


class InviteMemberResponse(BaseModel):
    invitation_id: uuid.UUID
    email: str
    role: str
    token: str
    expires_at: datetime
    invite_url: str


class AcceptInviteRequest(BaseModel):
    token: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None


class MemberResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    din: Optional[str] = None
    icai_membership_no: Optional[str] = None
    is_primary: bool
    is_active: bool
    created_at: datetime


@router.get("/my-companies", response_model=List[CompanySummaryResponse])
async def list_my_companies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all company workspaces the logged-in user belongs to,
    including company name, CIN, entity type, logo, and user's role.
    Super Admins also have access to all companies.
    """
    is_super = bool(getattr(current_user, "is_super_admin", False))

    if is_super:
        all_tenants = (await db.execute(select(Tenant).order_by(Tenant.legal_name.asc()))).scalars().all()
        # Fetch memberships for this user
        user_memberships = {
            tu.tenant_id: tu for tu in
            (await db.execute(select(TenantUser).where(TenantUser.user_id == current_user.id))).scalars().all()
        }
        res = []
        for t in all_tenants:
            m = user_memberships.get(t.id)
            res.append(CompanySummaryResponse(
                id=t.id,
                legal_name=t.legal_name,
                trade_name=t.trade_name,
                cin=t.cin,
                pan=t.pan,
                gstin=t.gstin,
                entity_type=t.entity_type or "Private Limited Company",
                role=str(m.role) if m else "company_owner",
                is_primary=bool(m.is_primary) if m else False,
                is_archived=bool(getattr(t, "is_archived", False)),
                logo_url=t.logo_url
            ))
        return res

    # Regular user memberships
    stmt = (
        select(TenantUser, Tenant)
        .join(Tenant, TenantUser.tenant_id == Tenant.id)
        .where(TenantUser.user_id == current_user.id, TenantUser.is_active == True)
        .order_by(TenantUser.is_primary.desc(), Tenant.legal_name.asc())
    )
    rows = (await db.execute(stmt)).all()
    results = []
    for tu, t in rows:
        results.append(CompanySummaryResponse(
            id=t.id,
            legal_name=t.legal_name,
            trade_name=t.trade_name,
            cin=t.cin,
            pan=t.pan,
            gstin=t.gstin,
            entity_type=t.entity_type or "Private Limited Company",
            role=str(tu.role),
            is_primary=bool(tu.is_primary),
            is_archived=bool(getattr(t, "is_archived", False)),
            logo_url=t.logo_url
        ))
    return results


@router.post("/switch-tenant", response_model=SwitchTenantResponse)
async def switch_tenant_context(
    payload: SwitchTenantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validates company membership and issues an updated JWT bound to the target company.
    """
    is_super = bool(getattr(current_user, "is_super_admin", False))
    target_tenant = (await db.execute(select(Tenant).where(Tenant.id == payload.tenant_id))).scalar_one_or_none()
    if not target_tenant:
        raise HTTPException(status_code=404, detail="Target company not found")

    membership = (await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == payload.tenant_id,
            TenantUser.user_id == current_user.id,
            TenantUser.is_active == True
        )
    )).scalar_one_or_none()

    if not membership and not is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied: You do not have an active membership in '{target_tenant.legal_name}'."
        )

    effective_role = str(membership.role) if membership else ("company_owner" if is_super else "employee")

    # Generate new token bound to this company
    token_claims = {
        "sub": str(current_user.id),
        "email": current_user.email,
        "tenant_id": str(target_tenant.id),
        "role": effective_role,
        "legal_name": target_tenant.legal_name,
        "cin": target_tenant.cin,
        "is_super_admin": is_super
    }
    new_token = create_access_token(token_claims)

    return SwitchTenantResponse(
        access_token=new_token,
        tenant_id=target_tenant.id,
        legal_name=target_tenant.legal_name,
        cin=target_tenant.cin,
        role=effective_role,
        is_super_admin=is_super
    )


@router.post("/invite", response_model=InviteMemberResponse)
async def invite_member(
    payload: InviteMemberRequest,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (Company Owner only) Issues an invitation token for a Chartered Accountant, Manager, or Employee.
    """
    norm_role = payload.role.lower().strip()
    valid_roles = ["company_owner", "owner", "ca_auditor", "auditor_ca", "finance_manager", "employee"]
    if norm_role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{payload.role}'. Must be one of: company_owner, ca_auditor, finance_manager, employee"
        )

    # Standardize alias
    if norm_role == "owner": norm_role = "company_owner"
    if norm_role == "auditor_ca": norm_role = "ca_auditor"

    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(days=7)

    invitation = TenantInvitation(
        tenant_id=ctx.tenant.id,
        email=payload.email.lower().strip(),
        role=norm_role,
        token=token,
        invited_by=ctx.user.id,
        expires_at=expires,
        is_accepted=False
    )
    db.add(invitation)
    await db.commit()

    return InviteMemberResponse(
        invitation_id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        expires_at=invitation.expires_at,
        invite_url=f"/accept-invite?token={token}"
    )


@router.post("/accept-invite")
async def accept_invitation(
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts invitation token, binds user to the company in tenant_users,
    and returns a valid authentication token.
    """
    stmt = select(TenantInvitation).where(
        TenantInvitation.token == payload.token.strip(),
        TenantInvitation.is_accepted == False
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=400, detail="Invalid, expired, or already accepted invitation token.")

    exp_at = inv.expires_at.replace(tzinfo=None) if inv.expires_at and inv.expires_at.tzinfo else inv.expires_at
    if exp_at and exp_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invitation token has expired.")

    # Find or provision user
    user_stmt = select(User).where(User.email == inv.email.lower())
    user = (await db.execute(user_stmt)).scalar_one_or_none()

    if not user:
        if not payload.password:
            raise HTTPException(status_code=400, detail="New user must provide a password to complete registration.")
        user = User(
            id=uuid.uuid4(),
            email=inv.email.lower(),
            password_hash=get_password_hash(payload.password),
            first_name=payload.first_name or inv.email.split("@")[0].capitalize(),
            last_name=payload.last_name or "Member",
            is_active=True
        )
        db.add(user)
        await db.flush()

    # Check if membership already exists
    tu_stmt = select(TenantUser).where(
        TenantUser.tenant_id == inv.tenant_id,
        TenantUser.user_id == user.id
    )
    existing_tu = (await db.execute(tu_stmt)).scalar_one_or_none()
    if existing_tu:
        existing_tu.role = inv.role
        existing_tu.is_active = True
    else:
        new_tu = TenantUser(
            id=uuid.uuid4(),
            tenant_id=inv.tenant_id,
            user_id=user.id,
            role=inv.role,
            is_active=True,
            is_primary=False
        )
        db.add(new_tu)

    inv.is_accepted = True
    await db.commit()

    # Fetch tenant for JWT claims
    tenant = (await db.execute(select(Tenant).where(Tenant.id == inv.tenant_id))).scalar_one()

    token_claims = {
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": str(tenant.id),
        "role": inv.role,
        "legal_name": tenant.legal_name,
        "cin": tenant.cin,
        "is_super_admin": bool(getattr(user, "is_super_admin", False))
    }
    jwt_token = create_access_token(token_claims)

    return {
        "success": True,
        "message": f"Successfully joined {tenant.legal_name} as {inv.role}.",
        "access_token": jwt_token,
        "tenant_id": str(tenant.id),
        "role": inv.role
    }


@router.get("/members", response_model=List[MemberResponse])
async def list_company_members(
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (Owner & CA) Lists all active members and their statutory designations.
    """
    stmt = (
        select(TenantUser)
        .options(selectinload(TenantUser.user))
        .where(TenantUser.tenant_id == ctx.tenant.id, TenantUser.is_active == True)
        .order_by(TenantUser.is_primary.desc(), TenantUser.created_at.asc())
    )
    memberships = (await db.execute(stmt)).scalars().all()

    out = []
    for m in memberships:
        out.append(MemberResponse(
            membership_id=m.id,
            user_id=m.user.id,
            email=m.user.email,
            first_name=m.user.first_name,
            last_name=m.user.last_name,
            role=str(m.role),
            din=m.din,
            icai_membership_no=m.icai_membership_no,
            is_primary=bool(m.is_primary),
            is_active=bool(m.is_active),
            created_at=m.created_at
        ))
    return out


@router.delete("/members/{membership_id}")
async def revoke_company_membership(
    membership_id: uuid.UUID,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    (Company Owner only) Revokes an active user's access to the company.
    """
    stmt = select(TenantUser).where(
        TenantUser.id == membership_id,
        TenantUser.tenant_id == ctx.tenant.id
    )
    tu = (await db.execute(stmt)).scalar_one_or_none()
    if not tu:
        raise HTTPException(status_code=404, detail="Membership record not found")

    if tu.is_primary:
        raise HTTPException(status_code=400, detail="Cannot revoke the primary company founder/owner account.")

    tu.is_active = False
    await db.commit()
    return {"success": True, "message": "Membership successfully revoked."}


@router.post("/admin/create-tenant", response_model=CompanySummaryResponse)
async def create_tenant_as_admin(
    payload: AdminCreateTenantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    (Super Admin only) Provisions a new company workspace,
    automatically seeds Schedule III Chart of Accounts and Compliance Countdown Milestones.
    """
    if not getattr(current_user, "is_super_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin privileges required to provision new corporate entities."
        )

    clean_pan = payload.pan.strip().upper()
    existing = (await db.execute(select(Tenant).where(Tenant.pan == clean_pan))).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An entity with PAN {clean_pan} is already registered on this platform."
        )

    from sqlalchemy import text
    from app.services.compliance_watchdog import ComplianceWatchdogService

    clean_cin = payload.cin.strip().upper() if payload.cin else None
    clean_gstin = payload.gstin.strip().upper() if payload.gstin else None

    new_tenant = Tenant(
        legal_name=payload.legal_name.strip(),
        trade_name=payload.trade_name.strip() if payload.trade_name else payload.legal_name.strip(),
        entity_type=payload.entity_type,
        cin=clean_cin,
        pan=clean_pan,
        gstin=clean_gstin,
        state_code=payload.state_code.strip(),
        registered_office=payload.registered_office.strip(),
        currency=payload.currency or "INR",
        statutory_profile={}
    )
    db.add(new_tenant)
    await db.flush()

    membership = TenantUser(
        tenant_id=new_tenant.id,
        user_id=current_user.id,
        role="company_owner",
        din=payload.admin_din,
        is_primary=True,
        is_active=True
    )
    db.add(membership)
    await db.flush()

    try:
        await db.execute(text(f"SELECT seed_tenant_chart_of_accounts('{str(new_tenant.id)}')"))
    except Exception:
        pass

    inc_date = None
    if payload.incorporation_date:
        try:
            inc_date = datetime.strptime(payload.incorporation_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    try:
        await ComplianceWatchdogService.seed_initial_statutory_milestones(
            session=db,
            tenant_id=new_tenant.id,
            incorporation_date=inc_date
        )
    except Exception:
        pass

    await db.commit()
    await db.refresh(new_tenant)

    return CompanySummaryResponse(
        id=new_tenant.id,
        legal_name=new_tenant.legal_name,
        trade_name=new_tenant.trade_name,
        cin=new_tenant.cin,
        pan=new_tenant.pan,
        gstin=new_tenant.gstin,
        entity_type=new_tenant.entity_type or "Private Limited Company",
        role="company_owner",
        is_primary=True,
        is_archived=False,
        logo_url=None
    )


@router.post("/admin/{tenant_id}/archive")
async def toggle_tenant_archive_as_admin(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    (Super Admin only) Archives or restores a tenant organization workspace.
    """
    if not getattr(current_user, "is_super_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin privileges required.")

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant organization not found")

    new_archived_state = not bool(getattr(tenant, "is_archived", False))
    tenant.is_archived = new_archived_state
    tenant.archived_at = datetime.utcnow() if new_archived_state else None
    await db.commit()

    action = "archived" if new_archived_state else "restored"
    return {
        "success": True,
        "message": f"Tenant '{tenant.legal_name}' has been successfully {action}.",
        "is_archived": new_archived_state
    }


@router.delete("/admin/{tenant_id}")
async def delete_tenant_as_admin(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    (Super Admin only) Permanently removes an entity workspace from the database.
    """
    if not getattr(current_user, "is_super_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin privileges required.")

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant organization not found")

    t_name = tenant.legal_name
    await db.delete(tenant)
    await db.commit()

    return {
        "success": True,
        "message": f"Tenant organization '{t_name}' ({tenant_id}) has been permanently deleted from sovereign storage."
    }

