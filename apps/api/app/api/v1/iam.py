import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_user, get_current_tenant
from app.models.tenant import User, Tenant, TenantUser
from app.core.security import get_password_hash

router = APIRouter()

class InviteUserRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: str # owner, auditor_ca, finance_manager, employee
    password: str
    din: Optional[str] = None # For Director / Owner

class UpdateRoleRequest(BaseModel):
    role: str
    din: Optional[str] = None

class IAMUserResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    din: Optional[str] = None
    is_primary: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/users", response_model=List[IAMUserResponse])
async def list_organization_users(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all users belonging to the corporate entity, their RBAC roles,
    and Director Identification Numbers (DIN).
    """
    stmt = (
        select(TenantUser)
        .options(selectinload(TenantUser.user))
        .where(TenantUser.tenant_id == tenant.id)
        .order_by(TenantUser.created_at.asc())
    )
    res = await db.execute(stmt)
    memberships = res.scalars().all()

    output = []
    for m in memberships:
        output.append(IAMUserResponse(
            membership_id=m.id,
            user_id=m.user.id,
            email=m.user.email,
            first_name=m.user.first_name,
            last_name=m.user.last_name,
            role=m.role,
            din=m.din,
            is_primary=m.is_primary,
            created_at=m.created_at
        ))
    return output

@router.post("/users", response_model=IAMUserResponse)
async def invite_user_to_organization(
    payload: InviteUserRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Adds/invites a new user (Director, Statutory Auditor CA, Finance Manager, or Staff)
    to the sovereign tenant workspace.
    """
    # Verify valid role
    valid_roles = ['owner', 'auditor_ca', 'finance_manager', 'employee']
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: {', '.join(valid_roles)}"
        )

    # Check if user already exists
    user_stmt = select(User).where(User.email == payload.email)
    res = await db.execute(user_stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            is_active=True
        )
        db.add(user)
        await db.flush()

    # Check if already a member of this tenant
    m_stmt = select(TenantUser).where(
        TenantUser.tenant_id == tenant.id,
        TenantUser.user_id == user.id
    )
    m_res = await db.execute(m_stmt)
    existing_membership = m_res.scalar_one_or_none()

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user is already a member of this organization."
        )

    membership = TenantUser(
        tenant_id=tenant.id,
        user_id=user.id,
        role=payload.role,
        din=payload.din if payload.role == 'owner' else None,
        is_primary=False
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return IAMUserResponse(
        membership_id=membership.id,
        user_id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=membership.role,
        din=membership.din,
        is_primary=membership.is_primary,
        created_at=membership.created_at
    )

@router.put("/users/{membership_id}", response_model=IAMUserResponse)
async def update_member_role(
    membership_id: uuid.UUID,
    payload: UpdateRoleRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates role or Director DIN for an organization member.
    """
    stmt = (
        select(TenantUser)
        .options(selectinload(TenantUser.user))
        .where(TenantUser.id == membership_id, TenantUser.tenant_id == tenant.id)
    )
    res = await db.execute(stmt)
    membership = res.scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=404, detail="Membership record not found")

    membership.role = payload.role
    if payload.din:
        membership.din = payload.din

    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return IAMUserResponse(
        membership_id=membership.id,
        user_id=membership.user.id,
        email=membership.user.email,
        first_name=membership.user.first_name,
        last_name=membership.user.last_name,
        role=membership.role,
        din=membership.din,
        is_primary=membership.is_primary,
        created_at=membership.created_at
    )

@router.delete("/users/{membership_id}")
async def revoke_member_access(
    membership_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Revokes user access from the corporate workspace.
    """
    stmt = select(TenantUser).where(TenantUser.id == membership_id, TenantUser.tenant_id == tenant.id)
    res = await db.execute(stmt)
    membership = res.scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=404, detail="Membership record not found")

    if membership.is_primary:
        raise HTTPException(status_code=400, detail="Cannot revoke access from the primary sovereign founder/owner.")

    await db.delete(membership)
    await db.commit()
    return {"message": "User access successfully revoked from organization."}

@router.get("/roles-matrix")
async def get_roles_permissions_matrix():
    """
    Returns the statutory authorization matrix under Companies Act, 2013 and IT Act, 2000.
    """
    return [
        {
            "role": "owner",
            "title": "Director / Sovereign Founder",
            "statutory_privilege": "Full Admin + DSC Board Minutes Signing + MCA Form Filing",
            "can_sign_dsc": True,
            "can_view_audit_file": True,
            "can_reconcile": True,
            "can_manage_iam": True,
            "requires_din": True
        },
        {
            "role": "auditor_ca",
            "title": "Statutory Auditor (Chartered Accountant)",
            "statutory_privilege": "Read-Only Schedule III Ledger Access + 1-Click Permanent Audit File Download",
            "can_sign_dsc": False,
            "can_view_audit_file": True,
            "can_reconcile": False,
            "can_manage_iam": False,
            "requires_din": False
        },
        {
            "role": "finance_manager",
            "title": "Finance Manager / CFO",
            "statutory_privilege": "3-Tier Bank Reconciliation + GST Invoice Creation + Voucher Entry",
            "can_sign_dsc": False,
            "can_view_audit_file": True,
            "can_reconcile": True,
            "can_manage_iam": False,
            "requires_din": False
        },
        {
            "role": "employee",
            "title": "Operations & Staff",
            "statutory_privilege": "Expense Receipt Upload & SmartScan OCR",
            "can_sign_dsc": False,
            "can_view_audit_file": False,
            "can_reconcile": False,
            "can_manage_iam": False,
            "requires_din": False
        }
    ]
