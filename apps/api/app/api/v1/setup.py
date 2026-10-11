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
            is_active=True
        )
        db.add(user)
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
        "role": "owner"
    }
    access_token = create_access_token(data=token_data)

    return {
        "message": "b00k5 successfully initialized for your company!",
        "tenant_id": str(tenant.id),
        "legal_name": tenant.legal_name,
        "access_token": access_token,
        "token_type": "bearer"
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
    if "logo_url" in payload:
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
    Data URI / S3 asset for document letterheads and invoices.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty logo file")

    content_type = file.content_type or "image/png"
    b64_str = base64.b64encode(file_bytes).decode('utf-8')
    data_uri = f"data:{content_type};base64,{b64_str}"

    tenant.logo_url = data_uri
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return {
        "message": "Company logo uploaded successfully",
        "logo_url": tenant.logo_url
    }
