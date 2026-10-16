from typing import Optional, Dict, Any
from datetime import datetime, date
import re
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.api.deps import get_db
from app.core.security import get_password_hash, create_access_token
from app.models.tenant import User, Tenant, TenantUser
from app.schemas.tenant import FirstRunSetupRequest
from app.services.compliance_watchdog import ComplianceWatchdogService
from app.services.gst_calculator import INDIAN_STATE_CODES
from app.services.onboarding_inspector import OnboardingInspectorService

router = APIRouter()

@router.get("/lookup-cin/{cin}")
def lookup_cin(cin: str):
    """
    Parses a 21-digit Indian Corporate Identification Number (CIN)
    e.g. U72900KA2026PTC123456
    """
    try:
        from app.services.cin_service import parse_indian_cin
        return parse_indian_cin(cin)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.get("/inspect-identifier")
def inspect_identifier_endpoint(identifier: str = Query(..., description="CIN, LLPIN, GSTIN, or PAN")):
    """
    Inspects an Indian statutory identifier and automatically extracts
    state, PAN, entity type, and regulatory profile.
    """
    return OnboardingInspectorService.inspect_identifier(identifier)

@router.post("/verify-document")
@router.post("/auto-inspect-document")
async def verify_document_endpoint(
    file: UploadFile = File(...),
    doc_type: str = Form("auto")
):
    """
    Validates an uploaded statutory document against regulatory criteria
    and authenticates government seals, check-digits, and formatting.
    Extracts verified company details so the user does not need to enter them manually.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty document payload")
    return OnboardingInspectorService.verify_statutory_document(
        file_bytes=file_bytes,
        filename=file.filename or "",
        expected_doc_type=doc_type
    )

@router.post("/wizard")
async def run_setup_wizard(payload: FirstRunSetupRequest, db: AsyncSession = Depends(get_db)):
    """
    Executes the 3-step first-run setup wizard:
    1. Provisions SuperAdmin user.
    2. Initializes Tenant organization.
    3. Auto-seeds default Indian Chart of Accounts and statutory compliance countdown milestones.
    """
    # 1. Check if user already exists
    existing_user_res = await db.execute(select(User).where(User.email == payload.admin_email))
    user = existing_user_res.scalar_one_or_none()
    if not user:
        user = User(
            email=payload.admin_email,
            password_hash=get_password_hash(payload.admin_password),
            first_name=payload.admin_first_name,
            last_name=payload.admin_last_name,
            is_active=True,
            is_super_admin=True
        )
        db.add(user)
        await db.flush()
    else:
        user.is_super_admin = True
        await db.flush()

    # 2. Check if tenant PAN/CIN already registered
    pan_clean = payload.pan.strip().upper()
    existing_tenant_res = await db.execute(select(Tenant).where(Tenant.pan == pan_clean))
    tenant = existing_tenant_res.scalar_one_or_none()
    if tenant:
        # Check if user already has membership
        m_res = await db.execute(
            select(TenantUser).where(TenantUser.tenant_id == tenant.id, TenantUser.user_id == user.id)
        )
        membership = m_res.scalar_one_or_none()
        if not membership:
            membership = TenantUser(
                tenant_id=tenant.id,
                user_id=user.id,
                role="owner",
                din=payload.admin_din,
                is_primary=True
            )
            db.add(membership)
            await db.flush()
    else:
        statutory_init = {}
        if payload.tan:
            statutory_init["tan"] = payload.tan.strip().upper()
            statutory_init["tan_status"] = "Active"
            statutory_init["tan_verified"] = True

        tenant = Tenant(
            legal_name=payload.legal_name,
            trade_name=payload.trade_name or payload.legal_name,
            cin=payload.cin.strip().upper() if payload.cin else None,
            pan=pan_clean,
            gstin=payload.gstin.strip().upper() if payload.gstin else None,
            state_code=payload.state_code.strip(),
            registered_office=payload.registered_office,
            currency="INR",
            statutory_profile=statutory_init
        )
        db.add(tenant)
        await db.flush()

        # 3. Create Tenant Membership with 'owner' role and Director DIN
        membership = TenantUser(
            tenant_id=tenant.id,
            user_id=user.id,
            role="owner",
            din=payload.admin_din,
            is_primary=True
        )
        db.add(membership)
        await db.flush()

        # 4. Auto-seed Chart of Accounts using the stored PostgreSQL procedure
        try:
            await db.execute(text(f"SELECT seed_tenant_chart_of_accounts('{str(tenant.id)}')"))
        except Exception as e:
            pass

        # 5. Auto-seed Statutory Compliance Milestones (120-Day BM, KYC, AOC-4, MGT-7)
        inc_date = None
        if payload.incorporation_date:
            try:
                inc_date = datetime.strptime(payload.incorporation_date, "%Y-%m-%d").date()
            except ValueError:
                pass

        await ComplianceWatchdogService.seed_initial_statutory_milestones(
            session=db,
            tenant_id=tenant.id,
            incorporation_date=inc_date
        )

    await db.commit()

    # Generate login token immediately
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": str(tenant.id),
        "role": "owner",
        "is_super_admin": True
    }
    access_token = create_access_token(data=token_data)

    return {
        "message": "b00k5 successfully initialized for your company!",
        "tenant_id": str(tenant.id),
        "legal_name": tenant.legal_name,
        "access_token": access_token,
        "token_type": "bearer",
        "is_super_admin": True,
        "role": "owner"
    }

from app.api.deps import get_current_tenant, get_current_user
import base64

@router.get("/company-profile")
async def get_company_profile(
    tenant: Tenant = Depends(get_current_tenant)
):
    """
    Retrieves full company profile including branding logo, registered office,
    and the parsed statutory profile rule engine.
    """
    return {
        "tenant_id": str(tenant.id),
        "legal_name": tenant.legal_name,
        "trade_name": tenant.trade_name,
        "cin": tenant.cin,
        "pan": tenant.pan,
        "gstin": tenant.gstin,
        "state_code": tenant.state_code,
        "registered_office": tenant.registered_office,
        "logo_url": tenant.logo_url,
        "statutory_profile": tenant.statutory_profile or {}
    }

@router.put("/company-profile")
async def update_company_profile(
    payload: dict,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates company legal details, address, and statutory metadata.
    """
    if "legal_name" in payload and payload["legal_name"]:
        tenant.legal_name = payload["legal_name"].strip()
    if "trade_name" in payload and payload["trade_name"]:
        tenant.trade_name = payload["trade_name"].strip()
    if "registered_office" in payload and payload["registered_office"]:
        tenant.registered_office = payload["registered_office"].strip()
    if "cin" in payload and payload["cin"]:
        tenant.cin = payload["cin"].strip().upper()
    if "pan" in payload and payload["pan"]:
        tenant.pan = payload["pan"].strip().upper()
    if "gstin" in payload and payload["gstin"]:
        tenant.gstin = payload["gstin"].strip().upper()
    if "logo_url" in payload and payload["logo_url"]:
        tenant.logo_url = payload["logo_url"]

    if "statutory_profile" in payload:
        sp = dict(tenant.statutory_profile or {})
        sp.update(payload["statutory_profile"])
        tenant.statutory_profile = sp

    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return {
        "message": "Company profile updated successfully.",
        "tenant": {
            "legal_name": tenant.legal_name,
            "registered_office": tenant.registered_office,
            "cin": tenant.cin,
            "pan": tenant.pan,
            "gstin": tenant.gstin,
            "logo_url": tenant.logo_url,
            "statutory_profile": tenant.statutory_profile
        }
    }

@router.post("/upload-logo")
async def upload_company_logo(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Uploads company logo image (PNG/JPEG/SVG/WebP) and stores it as an optimized
    Data URI and MinIO S3 asset for document letterheads and invoices.
    """
    import base64
    import hashlib
    import os
    from app.core.s3 import storage_manager
    from app.core.config import settings

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty logo file")

    filename = (file.filename or "logo.png").lower()
    ext = os.path.splitext(filename)[1] or ".png"
    content_type = file.content_type or ("image/png" if ext == ".png" else "image/jpeg")

    b64_str = base64.b64encode(file_bytes).decode('utf-8')
    data_uri = f"data:{content_type};base64,{b64_str}"

    file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
    s3_key = f"{tenant.id}/branding/logo_{file_hash}{ext}"

    try:
        storage_manager.save_document(
            bucket_name=getattr(settings, "BUCKET_STATUTORY", "b00k5-statutory"),
            object_name=s3_key,
            file_bytes=file_bytes,
            content_type=content_type
        )
        tenant.logo_s3_key = s3_key
    except Exception:
        pass

    tenant.logo_url = data_uri
    prof = dict(tenant.statutory_profile or {})
    prof["logo_url"] = data_uri
    if getattr(tenant, "logo_s3_key", None):
        prof["logo_s3_key"] = tenant.logo_s3_key
    tenant.statutory_profile = prof

    # Invalidate cached invoice PDFs so fresh invoices display the uploaded logo immediately
    try:
        await db.execute(
            text("UPDATE invoices SET pdf_s3_key = NULL WHERE tenant_id = :tid").params(tid=tenant.id)
        )
    except Exception:
        pass

    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return {
        "message": "Company logo uploaded successfully",
        "logo_url": tenant.logo_url,
        "logo_s3_key": tenant.logo_s3_key
    }

@router.delete("/remove-logo")
async def remove_company_logo(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Removes company logo from tenant and statutory profile."""
    tenant.logo_url = None
    prof = dict(tenant.statutory_profile or {})
    prof.pop("logo_url", None)
    tenant.statutory_profile = prof

    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return {
        "message": "Company logo removed successfully",
        "logo_url": None
    }

@router.get("/logo")
async def get_company_logo(
    tenant_id: Optional[str] = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Serves company branding logo directly as an image stream with browser caching.
    """
    import base64
    from fastapi.responses import Response
    from app.core.s3 import storage_manager
    from app.core.config import settings

    target_tenant = tenant
    if tenant_id:
        try:
            t_uuid = uuid.UUID(tenant_id)
            t_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
            found = t_res.scalar_one_or_none()
            if found:
                target_tenant = found
        except Exception:
            pass

    # 1. Try MinIO S3
    if target_tenant.logo_s3_key:
        try:
            img_bytes = storage_manager.get_document_bytes(
                getattr(settings, "BUCKET_STATUTORY", "b00k5-statutory"),
                target_tenant.logo_s3_key
            )
            if img_bytes:
                content_type = "image/png" if target_tenant.logo_s3_key.endswith(".png") else "image/jpeg"
                return Response(content=img_bytes, media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass

    # 2. Try Data URI in logo_url
    if target_tenant.logo_url and target_tenant.logo_url.startswith("data:"):
        try:
            header, b64_part = target_tenant.logo_url.split(",", 1)
            mime = "image/png"
            if ";" in header:
                mime = header.split(";")[0].replace("data:", "")
            img_bytes = base64.b64decode(b64_part)
            return Response(content=img_bytes, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="No logo uploaded for this organization")

