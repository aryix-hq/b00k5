from typing import List, Optional
from datetime import date, datetime
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_tenant
from app.models.tenant import Tenant, User, TenantUser
from app.models.compliance import ComplianceEvent, CorporateMeeting
from app.models.vault import DocumentVault
from app.schemas.compliance import (
    ComplianceEventCreate, ComplianceEventResponse, ComplianceSummaryResponse
)
from app.services.compliance_watchdog import ComplianceWatchdogService
from app.services.document_assembly import DocumentAssemblyService
from app.services.esign_service import ESignService
from app.core.s3 import storage_manager

router = APIRouter()

@router.get("/directors")
async def get_tenant_director_roster(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns verified director roster binding DINs and designations for current tenant
    from both MCA Statutory Documents (tenant.statutory_profile['directors']) and TenantUser records.
    """
    from app.services.statutory_vault_engine import _is_valid_person_name
    prof = tenant.statutory_profile or {}
    raw_mca_directors = list(prof.get("directors") or [])
    mca_directors = [
        md for md in raw_mca_directors
        if isinstance(md, dict) and _is_valid_person_name(md.get("name", ""))
    ]
    fallback_dins = list(prof.get("founding_director_dins") or [])
    for md in raw_mca_directors:
        if isinstance(md, dict) and md.get("din") and md.get("din") not in ("", "N/A") and md.get("din") not in fallback_dins:
            fallback_dins.append(md["din"])

    stmt = (
        select(User.first_name, User.last_name, User.email, TenantUser.role, TenantUser.din)
        .join(TenantUser, TenantUser.user_id == User.id)
        .where(TenantUser.tenant_id == tenant.id)
    )
    res = await db.execute(stmt)
    rows = res.all()

    roster = []
    used_mca_indices = set()

    for fn, ln, email, role, din in rows:
        if role and role.lower() in ("auditor", "ca", "external_auditor", "viewer"):
            continue
        user_full = f"{fn or ''} {ln or ''}".strip()
        user_first = (fn or "").strip().lower()
        matched_mca = None
        for idx, md in enumerate(mca_directors):
            md_name = (md.get("name") or "").strip()
            if (din and md.get("din") == din) or (user_first and user_first in md_name.lower()) or (user_full and user_full.lower() in md_name.lower()):
                matched_mca = md
                used_mca_indices.add(idx)
                break

        mca_name = (matched_mca.get("name") or "").strip() if matched_mca else ""
        if mca_name and (not user_first or user_first in mca_name.lower()) and len(mca_name) >= len(user_full):
            resolved_name = mca_name
        else:
            resolved_name = user_full or mca_name or "Director"

        resolved_din = (
            (matched_mca.get("din") if matched_mca and matched_mca.get("din") not in (None, "", "N/A") else None)
            or din
            or (fallback_dins[0] if fallback_dins else "N/A")
        )
        resolved_desig = (
            (matched_mca.get("designation") if matched_mca and matched_mca.get("designation") else None)
            or ("Director" if role == "owner" else (role.replace("_", " ").title() if role else "Director"))
        )
        roster.append({
            "name": resolved_name,
            "email": email,
            "din": resolved_din,
            "designation": resolved_desig,
            "role": role or "director"
        })

    for idx, md in enumerate(mca_directors):
        if idx not in used_mca_indices and md.get("name"):
            roster.append({
                "name": md["name"],
                "email": md.get("email", ""),
                "din": md.get("din") or "N/A",
                "designation": md.get("designation") or "Director",
                "role": "director"
            })

    if not roster and fallback_dins:
        roster = [
            {"name": f"Director (DIN: {d})", "din": d, "designation": "Director", "email": "", "role": "director"}
            for d in fallback_dins
        ]

    resolved_reg_office = (
        tenant.registered_office
        or prof.get("new_registered_office")
        or prof.get("registered_office")
        or ""
    )

    return {
        "tenant_id": str(tenant.id),
        "legal_name": tenant.legal_name,
        "cin": tenant.cin,
        "registered_office": resolved_reg_office,
        "directors": roster
    }

@router.get("/meetings")
async def list_corporate_meetings(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all corporate meetings recorded for the current tenant.
    """
    stmt = (
        select(CorporateMeeting)
        .where(CorporateMeeting.tenant_id == tenant.id)
        .order_by(CorporateMeeting.meeting_date.desc())
    )
    res = await db.execute(stmt)
    meetings = res.scalars().all()
    return [
        {
            "id": str(m.id),
            "meeting_type": m.meeting_type,
            "meeting_number": m.meeting_number,
            "meeting_date": m.meeting_date.isoformat(),
            "meeting_time": m.meeting_time,
            "venue": m.venue,
            "directors_present": m.directors_present,
            "agenda_items": m.agenda_items,
            "resolutions": m.resolutions,
            "status": m.status,
            "signed_document_key": m.signed_document_key,
            "sha256_hash": m.sha256_hash,
            "created_at": m.created_at.isoformat()
        }
        for m in meetings
    ]

@router.get("/dashboard", response_model=ComplianceSummaryResponse)
async def get_compliance_dashboard(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns statutory countdowns, pending deadlines, and penalty risk overview.
    """
    stmt = (
        select(ComplianceEvent)
        .where(ComplianceEvent.tenant_id == tenant.id)
        .order_by(ComplianceEvent.due_date.asc())
    )
    res = await db.execute(stmt)
    events = res.scalars().all()

    # Auto-synchronize events with DocumentVault uploaded filings
    from app.models.vault import DocumentVault
    vault_stmt = select(DocumentVault).where(DocumentVault.tenant_id == tenant.id)
    vault_docs = (await db.execute(vault_stmt)).scalars().all()
    uploaded_doc_names = [d.document_name.lower() for d in vault_docs]

    # Check INC-20A
    has_inc20a = any(
        "inc-20a" in name or "inc_20a" in name or "inc20a" in name or "inc 20a" in name or "inc 20 a" in name or "commencement" in name
        for name in uploaded_doc_names
    ) or any(
        (d.metadata_json or {}).get("document_type") in ("form_inc_20a", "inc_20a", "INC_20A") or
        "inc 20" in (d.document_name or "").lower() or
        "inc-20" in (d.document_name or "").lower() or
        "inc20" in (d.document_name or "").lower() or
        "inc_20" in (d.document_name or "").lower()
        for d in vault_docs
    ) or bool((tenant.statutory_profile or {}).get("inc20a_status")) or bool((tenant.statutory_profile or {}).get("inc20a_verified")) or bool((tenant.statutory_profile or {}).get("borrowing_powers_active"))

    # Check ADT-1
    has_adt1 = any(
        "adt-1" in name or "adt_1" in name or "adt1" in name or "adt 1" in name or "auditor" in name
        for name in uploaded_doc_names
    ) or any(
        (d.metadata_json or {}).get("document_type") in ("form_adt_1", "adt_1", "ADT_1") or
        "adt 1" in (d.document_name or "").lower() or
        "adt-1" in (d.document_name or "").lower()
        for d in vault_docs
    ) or bool((tenant.statutory_profile or {}).get("auditor_name")) or bool((tenant.statutory_profile or {}).get("auditor_frn"))

    # Check AOC-4
    has_aoc4 = any(
        "aoc-4" in name or "aoc_4" in name or "aoc4" in name or "aoc 4" in name or "financial statements" in name
        for name in uploaded_doc_names
    ) or any(
        (d.metadata_json or {}).get("document_type") in ("form_aoc_4", "aoc_4", "AOC_4")
        for d in vault_docs
    )

    # Check MGT-7
    has_mgt7 = any(
        "mgt-7" in name or "mgt_7" in name or "mgt7" in name or "mgt 7" in name or "annual return" in name
        for name in uploaded_doc_names
    ) or any(
        (d.metadata_json or {}).get("document_type") in ("form_mgt_7", "mgt_7", "MGT_7", "MGT_7A")
        for d in vault_docs
    )

    # Check ITR
    has_itr = any(
        "itr" in name or "income tax" in name or "itr-6" in name or "itr 6" in name
        for name in uploaded_doc_names
    ) or any(
        (d.metadata_json or {}).get("document_type") in ("itr", "itr_6", "ITR_6", "form_itr_6")
        for d in vault_docs
    )

    events_updated = False
    new_recurring_events = []

    for ev in events:
        if ev.category == "inc_20a" and has_inc20a and ev.status != "completed":
            ev.status = "completed"
            ev.completed_at = datetime.utcnow()
            events_updated = True
        elif ev.category == "adt_1" and has_adt1 and ev.status != "completed":
            ev.status = "completed"
            ev.completed_at = datetime.utcnow()
            events_updated = True
        elif ev.category == "aoc_4" and has_aoc4 and ev.status != "completed":
            ev.status = "completed"
            ev.completed_at = datetime.utcnow()
            events_updated = True
            # Roll over to next annual cycle
            next_due = date(ev.due_date.year + 1, 10, 30)
            if not any(e.category == "aoc_4" and e.due_date == next_due for e in events):
                new_recurring_events.append(ComplianceEvent(
                    tenant_id=tenant.id,
                    category="aoc_4",
                    title="Form AOC-4: Annual Financial Statements",
                    description="Annual filing of audited Balance Sheet, P&L, and Board Report under Section 137.",
                    due_date=next_due,
                    statutory_reference="Companies Act 2013 Sec 137",
                    fine_per_day_inr=Decimal("100.00"),
                    status="upcoming"
                ))
        elif ev.category == "mgt_7" and has_mgt7 and ev.status != "completed":
            ev.status = "completed"
            ev.completed_at = datetime.utcnow()
            events_updated = True
            # Roll over to next annual cycle (Nov 29 next year)
            next_due = date(ev.due_date.year + 1, 11, 29)
            if not any(e.category == "mgt_7" and e.due_date == next_due for e in events):
                new_recurring_events.append(ComplianceEvent(
                    tenant_id=tenant.id,
                    category="mgt_7",
                    title="Form MGT-7 / MGT-7A: Annual Return",
                    description="Annual disclosure of shareholding pattern, directors, and indebtedness under Section 92(4).",
                    due_date=next_due,
                    statutory_reference="Companies Act 2013 Sec 92(4)",
                    fine_per_day_inr=Decimal("100.00"),
                    status="upcoming"
                ))
        elif ev.category == "itr_filing" and has_itr and ev.status != "completed":
            ev.status = "completed"
            ev.completed_at = datetime.utcnow()
            events_updated = True
            # Roll over to next annual ITR cycle (Oct 31 next year)
            next_due = date(ev.due_date.year + 1, 10, 31)
            if not any(e.category == "itr_filing" and e.due_date == next_due for e in events):
                new_recurring_events.append(ComplianceEvent(
                    tenant_id=tenant.id,
                    category="itr_filing",
                    title="Form ITR-6: Corporate Income Tax Return",
                    description="Annual Corporate Income Tax Return filing under Section 139(1).",
                    due_date=next_due,
                    statutory_reference="Income Tax Act 1961 Sec 139(1)",
                    fine_per_day_inr=Decimal("50.00"),
                    status="upcoming"
                ))

    # Auto-provision ITR-6 only if COI is verified and missing from the tenant's compliance calendar
    prof_dict = tenant.statutory_profile or {}
    tenant_inc_date = prof_dict.get("incorporation_date") or prof_dict.get("incorporation_year") or tenant.cin
    if tenant_inc_date and not any(e.category == "itr_filing" for e in events):
        curr_yr = date.today().year
        itr_target_due = date(curr_yr, 10, 31) if date.today() <= date(curr_yr, 10, 31) else date(curr_yr + 1, 10, 31)
        new_recurring_events.append(ComplianceEvent(
            tenant_id=tenant.id,
            category="itr_filing",
            title="Form ITR-6: Corporate Income Tax Return",
            description="Annual Corporate Income Tax Return filing under Section 139(1). Late fees accrue under Section 234F.",
            due_date=itr_target_due,
            statutory_reference="Income Tax Act 1961 Sec 139(1)",
            fine_per_day_inr=Decimal("50.00"),
            status="upcoming"
        ))

    if new_recurring_events:
        db.add_all(new_recurring_events)
        events.extend(new_recurring_events)
        events_updated = True

    if events_updated:
        await db.commit()

    today = date.today()
    calculated_events = []
    total_penalty = Decimal("0.00")
    overdue_count = 0
    due_soon_count = 0

    for ev in events:
        metrics = ComplianceWatchdogService.calculate_event_metrics(ev, today)
        calculated_events.append(metrics)
        if metrics["status"] == "overdue":
            overdue_count += 1
            total_penalty += metrics["accumulated_penalty_inr"]
        elif metrics["status"] == "due_soon":
            due_soon_count += 1

    return {
        "total_events": len(calculated_events),
        "overdue_count": overdue_count,
        "due_soon_count": due_soon_count,
        "total_penalty_accruing_inr": total_penalty,
        "upcoming_events": calculated_events
    }

@router.post("/events", response_model=ComplianceEventResponse)
async def create_compliance_event(
    payload: ComplianceEventCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    ev = ComplianceEvent(
        tenant_id=tenant.id,
        category=payload.category,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        statutory_reference=payload.statutory_reference,
        fine_per_day_inr=payload.fine_per_day_inr,
        metadata_json=payload.metadata_json or {}
    )
    db.add(ev)
    await db.commit()
    await db.refresh(ev)

    metrics = ComplianceWatchdogService.calculate_event_metrics(ev, date.today())
    return metrics

@router.post("/{event_id}/complete")
async def mark_event_complete(
    event_id: uuid.UUID,
    document_id: Optional[uuid.UUID] = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ComplianceEvent).where(
        ComplianceEvent.id == event_id,
        ComplianceEvent.tenant_id == tenant.id
    )
    res = await db.execute(stmt)
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Compliance event not found")

    ev.status = "completed"
    ev.completed_at = datetime.utcnow()
    if document_id:
        ev.document_id = document_id

    await db.commit()
    return {"message": f"Compliance milestone '{ev.title}' marked as completed."}

@router.post("/evaluate-bm-cadence")
async def evaluate_board_meeting_cadence(
    last_meeting_date: str,
    check_date: Optional[str] = None
):
    """
    Evaluates Section 173(1) 120-day Board Meeting interval:
    Flags warning if > 100 days, and statutory violation if > 120 days.
    """
    try:
        last_dt = datetime.strptime(last_meeting_date, "%Y-%m-%d").date()
        today_dt = datetime.strptime(check_date, "%Y-%m-%d").date() if check_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    return ComplianceWatchdogService.evaluate_board_meeting_cadence(last_dt, today_dt)

@router.post("/generate-document")
async def generate_statutory_document(
    doc_type: str,
    payload: dict,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Compiles statutory documents (board_minutes, board_notice) into valid PDF documents,
    strictly binding Company Master Profile, CIN, Registered Office, and Director Roster (DEF-01).
    """
    # 1. Bind Company Master Profile
    payload["company_name"] = tenant.legal_name
    payload["cin"] = tenant.cin or "U72200KA2024PTC189000"
    payload["registered_office"] = tenant.registered_office or "Indiranagar, Bengaluru - 560038, Karnataka"

    # 2. Resolve & bind Director Roster
    directors_present = payload.get("directors_present")
    if not directors_present:
        stmt = (
            select(User.first_name, User.last_name, TenantUser.role, TenantUser.din)
            .join(TenantUser, TenantUser.user_id == User.id)
            .where(TenantUser.tenant_id == tenant.id)
        )
        res = await db.execute(stmt)
        rows = res.all()
        roster = []
        for fn, ln, role, din in rows:
            designation = "Managing Director" if role == "owner" else (role.replace("_", " ").title() if role else "Director")
            roster.append({
                "name": f"{fn} {ln}".strip(),
                "din": din or "09876541",
                "designation": designation
            })

        if not roster and tenant.statutory_profile:
            if tenant.statutory_profile.get("directors"):
                roster = tenant.statutory_profile.get("directors")
            elif tenant.statutory_profile.get("founding_director_dins"):
                roster = [
                    {"name": f"Director ({d})", "din": d, "designation": "Director"}
                    for d in tenant.statutory_profile.get("founding_director_dins")
                ]
        if not roster:
            roster = [
                {"name": "Authorized Director", "din": "09876541", "designation": "Director"}
            ]
        payload["directors_present"] = roster

    # 3. Assemble statutory PDF
    if doc_type == "board_minutes":
        pdf_bytes = DocumentAssemblyService.assemble_board_minutes(payload)
        filename = f"Board_Minutes_{payload.get('meeting_date', 'draft')}.pdf"
    elif doc_type == "board_notice":
        pdf_bytes = DocumentAssemblyService.assemble_board_notice_and_agenda(payload)
        filename = f"Board_Notice_{payload.get('meeting_date', 'draft')}.pdf"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported document type: {doc_type}")

    # 4. Persist to local MinIO storage
    s3_key = f"statutory/{uuid.uuid4()}_{filename}"
    obj_name, sha256_hash, file_size = storage_manager.save_document(
        bucket_name="b00k5-statutory",
        object_name=s3_key,
        file_bytes=pdf_bytes,
        content_type="application/pdf"
    )

    presigned_url = storage_manager.generate_presigned_url("b00k5-statutory", s3_key)

    # 5. Persist corporate meeting record in database
    try:
        mtg_dt = datetime.strptime(payload.get("meeting_date", date.today().isoformat()), "%Y-%m-%d").date()
    except Exception:
        mtg_dt = date.today()

    meeting = CorporateMeeting(
        tenant_id=tenant.id,
        meeting_type="board_meeting" if doc_type == "board_minutes" else "board_notice",
        meeting_number=payload.get("meeting_number", "BM/2026-27/01"),
        meeting_date=mtg_dt,
        meeting_time=payload.get("meeting_time", "11:00 AM IST"),
        venue=payload.get("venue", tenant.registered_office or "Registered Office"),
        directors_present=payload.get("directors_present", []),
        agenda_items=payload.get("agenda_items", []),
        resolutions=payload.get("resolutions", []),
        signed_document_key=s3_key,
        sha256_hash=sha256_hash,
        status="generated"
    )
    db.add(meeting)
    await db.commit()

    return {
        "document_type": doc_type,
        "filename": filename,
        "s3_bucket": "b00k5-statutory",
        "s3_key": s3_key,
        "sha256_hash": sha256_hash,
        "file_size_bytes": file_size,
        "presigned_url": presigned_url,
        "meeting_id": str(meeting.id),
        "bound_company_name": tenant.legal_name,
        "bound_cin": tenant.cin,
        "bound_registered_office": tenant.registered_office,
        "bound_directors": payload["directors_present"]
    }

@router.post("/sign-document")
async def sign_statutory_document(
    s3_key: str,
    signer_name: str,
    din: Optional[str] = None,
    designation: str = "Director",
    reason: str = "Approved under Companies Act 2013",
    location: str = "Bengaluru, India"
):
    """
    Applies visual signature and cryptographic SHA-256 seal to an existing PDF in storage.
    """
    pdf_bytes = storage_manager.get_document_bytes("b00k5-statutory", s3_key)
    signed_meta = ESignService.apply_digital_signature(
        pdf_bytes=pdf_bytes,
        signer_name=signer_name,
        din=din,
        designation=designation,
        reason=reason,
        location=location
    )

    signed_s3_key = f"statutory/signed_{s3_key.split('/')[-1]}"
    storage_manager.save_document(
        bucket_name="b00k5-statutory",
        object_name=signed_s3_key,
        file_bytes=signed_meta["signed_pdf_bytes"],
        content_type="application/pdf"
    )

    return {
        "signed_s3_key": signed_s3_key,
        "seal_id": signed_meta["seal_id"],
        "raw_sha256": signed_meta["raw_sha256"],
        "signed_sha256": signed_meta["signed_sha256"],
        "signer_name": signed_meta["signer_name"],
        "timestamp": signed_meta["timestamp"],
        "is_sealed": True
    }

@router.post("/verify-signature")
async def verify_document_signature(s3_key: str):
    """
    Verifies digital seal and checks for tamper-evidence.
    """
    signed_bytes = storage_manager.get_document_bytes("b00k5-statutory", s3_key)
    return ESignService.verify_signature(signed_bytes)

STATUTORY_CATALOG = [
    {
        "code": "COI",
        "name": "Certificate of Incorporation",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Establishes legal identity, corporate age, and statutory base calendar.",
        "category": "corporate_legal",
        "key_entity": "cin"
    },
    {
        "code": "MOA",
        "name": "Memorandum of Association",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Defines corporate charter, Main Objects Clause, and Authorized Share Capital.",
        "category": "corporate_legal",
        "key_entity": "main_objects"
    },
    {
        "code": "AOA",
        "name": "Articles of Association",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Internal governance regulations, quorum thresholds, and director voting rules.",
        "category": "corporate_legal",
        "key_entity": "quorum"
    },
    {
        "code": "PAN",
        "name": "Permanent Account Number (PAN Card)",
        "authority": "Income Tax Department (CBDT)",
        "purpose": "Corporate direct tax identity for Section 139 tax returns and banking.",
        "category": "tax_registration",
        "key_entity": "pan"
    },
    {
        "code": "TAN",
        "name": "Tax Deduction and Collection Account Number",
        "authority": "Income Tax Department (CBDT)",
        "purpose": "Enables withholding tax remittance (TDS u/s 194C, 194J, 192) and Form 26Q filings.",
        "category": "tax_registration",
        "key_entity": "tan"
    },
    {
        "code": "GST_REG06",
        "name": "GST Registration Certificate (REG-06)",
        "authority": "Goods and Services Tax Network (CBIC)",
        "purpose": "15-digit GSTIN, principal place of business, and legal trade name proof.",
        "category": "tax_registration",
        "key_entity": "gstin"
    },
    {
        "code": "INC_20A",
        "name": "Commencement of Business (Form INC-20A)",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Mandatory declaration u/s 10A within 180 days of incorporation before borrowing powers activate.",
        "category": "statutory_filing",
        "key_entity": "srn"
    },
    {
        "code": "INC_22",
        "name": "Notice of Registered Office (Form INC-22)",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Statutory proof of registered office location under Section 12.",
        "category": "corporate_legal",
        "key_entity": "registered_office"
    },
    {
        "code": "ADT_1",
        "name": "Appointment of Statutory Auditor (Form ADT-1)",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Notifies RoC of statutory auditor appointment under Section 139(1) with FRN.",
        "category": "statutory_filing",
        "key_entity": "auditor_frn"
    },
    {
        "code": "DIR_12",
        "name": "Appointment / Changes in Directors (Form DIR-12)",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Roster of directors, DINs, and changes in corporate management.",
        "category": "equity_governance",
        "key_entity": "din"
    },
    {
        "code": "MGT_7A",
        "name": "Abridged Annual Return (Form MGT-7A)",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Annual return for small companies u/s 92(1) detailing shareholding and meetings.",
        "category": "statutory_filing",
        "key_entity": "mgt7_srn"
    },
    {
        "code": "AOC_4",
        "name": "Financial Statements Filing (Form AOC-4)",
        "authority": "Ministry of Corporate Affairs (MCA)",
        "purpose": "Balance Sheet, P&L, and Notes to Accounts submitted to RoC u/s 137.",
        "category": "statutory_filing",
        "key_entity": "aoc4_srn"
    },
    {
        "code": "BOARD_REPORT",
        "name": "Extract of Board's Report (Section 134)",
        "authority": "Board of Directors",
        "purpose": "Director Responsibility Statement and operational disclosures for annual filing.",
        "category": "equity_governance",
        "key_entity": "board_report"
    },
    {
        "code": "AUDITOR_REPORT",
        "name": "Extract of Auditor's Report (Standalone)",
        "authority": "Independent Statutory Auditor",
        "purpose": "True and fair view audit opinion, CARO 2020 clauses, and internal financial controls.",
        "category": "statutory_filing",
        "key_entity": "audit_opinion"
    },
    {
        "code": "ITR",
        "name": "Income Tax Return (Form ITR-6 / ITR-V Ack)",
        "authority": "Income Tax Department / CBDT",
        "purpose": "Mandatory corporate tax return filed u/s 139 with computation of taxable income.",
        "category": "tax_registration",
        "key_entity": "itr_ack"
    }
]

@router.get("/statutory-documents-status")
async def get_statutory_documents_status(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the comprehensive 15-document statutory compliance status for the company,
    showing verified documents, extracted entity metadata, and direct download links.
    """
    DOC_MAP = {
        "coi": "COI",
        "moa": "MOA",
        "aoa": "AOA",
        "pan_card": "PAN",
        "tan_letter": "TAN",
        "gst_reg06": "GST_REG06",
        "form_inc_20a": "INC_20A",
        "form_inc_22": "INC_22",
        "form_adt_1": "ADT_1",
        "form_dir_12": "DIR_12",
        "dir_12": "DIR_12",
        "form_mgt_7": "MGT_7A",
        "form_aoc_4": "AOC_4",
        "board_report": "BOARD_REPORT",
        "auditor_report": "AUDITOR_REPORT",
        "itr": "ITR",
        "form_itr": "ITR",
        "itr_6": "ITR",
        "itr-6": "ITR"
    }

    vault_stmt = select(DocumentVault).where(DocumentVault.tenant_id == tenant.id)
    vault_docs = (await db.execute(vault_stmt)).scalars().all()
    comp_stmt = select(ComplianceEvent).where(ComplianceEvent.tenant_id == tenant.id)
    comp_events = (await db.execute(comp_stmt)).scalars().all()
    vault_map = {}
    for d in vault_docs:
        meta = d.metadata_json or {}
        doc_type = meta.get("document_type")
        if doc_type:
            vault_map[doc_type] = d
            if doc_type in DOC_MAP:
                vault_map[DOC_MAP[doc_type]] = d
        if d.category and d.category in DOC_MAP:
            vault_map[DOC_MAP[d.category]] = d
        if d.document_name:
            vault_map[d.document_name] = d
            dname_low = d.document_name.lower()
            if "auditor" in dname_low and "report" in dname_low:
                vault_map["AUDITOR_REPORT"] = d
            elif ("board" in dname_low or "director" in dname_low) and "report" in dname_low:
                vault_map["BOARD_REPORT"] = d
            elif "dir-12" in dname_low or "dir 12" in dname_low:
                vault_map["DIR_12"] = d
            elif "itr" in dname_low or "income tax return" in dname_low:
                vault_map["ITR"] = d
            elif "aoc-4" in dname_low or "aoc 4" in dname_low or "aoc_4" in dname_low:
                vault_map["AOC_4"] = d
            elif "mgt-7" in dname_low or "mgt 7" in dname_low or "mgt_7" in dname_low:
                vault_map["MGT_7A"] = d
            else:
                for c, mapped_code in DOC_MAP.items():
                    if c.replace('_', ' ') in dname_low:
                        vault_map[mapped_code] = d

    prof = tenant.statutory_profile or {}
    docs_status = []

    for item in STATUTORY_CATALOG:
        code = item["code"]
        vault_doc = vault_map.get(code) or vault_map.get(code.lower()) or vault_map.get(item["name"])

        # Determine verification & extracted attributes
        is_verified = False
        extracted_info = {}
        if vault_doc and vault_doc.metadata_json:
            extracted_info = dict(vault_doc.metadata_json.get("extracted_fields", {}))

        if code == "COI":
            if vault_doc or prof.get("coi_verified"):
                is_verified = True
                extracted_info = {
                    "cin": tenant.cin or prof.get("cin") or "",
                    "legal_name": tenant.legal_name,
                    "date_of_incorporation": prof.get("incorporation_date") or (tenant.created_at.strftime("%Y-%m-%d") if tenant.created_at else "")
                }
            else:
                is_verified = False
                extracted_info = {"cin": tenant.cin or "Pending COI Upload"}
        elif code == "PAN":
            if vault_doc or prof.get("pan_verified"):
                is_verified = True
                extracted_info = {"pan": tenant.pan or prof.get("pan")}
            else:
                is_verified = False
                extracted_info = {"pan": "Pending PAN Card Upload"}
        elif code == "GST_REG06":
            gst_val = tenant.gstin or prof.get("gstin")
            has_gst_doc = bool(vault_map.get("GST_REG06") or prof.get("gst_reg06_verified"))
            if has_gst_doc and gst_val and not str(gst_val).startswith("29AABCA1234"):
                is_verified = True
                extracted_info = {"gstin": gst_val, "state_code": tenant.state_code or "29"}
            else:
                is_verified = False
                extracted_info = {"gstin": "Not Registered / Upload Certificate", "state_code": ""}
        elif code == "TAN":
            tan_val = prof.get("tan")
            has_tan_doc = bool(vault_map.get("TAN") or prof.get("tan_verified"))
            if has_tan_doc and tan_val and not str(tan_val).startswith("BLRA12345"):
                is_verified = True
                extracted_info = {"tan": tan_val}
            else:
                is_verified = False
                extracted_info = {"tan": "Not Registered / Upload Certificate"}
        elif code == "INC_22":
            if vault_doc or prof.get("inc22_verified"):
                is_verified = True
                extracted_info = {"registered_office": tenant.registered_office or ""}
            else:
                is_verified = False
                extracted_info = {"registered_office": "Pending Form INC-22 Upload"}
        elif code == "ADT_1":
            if vault_doc or prof.get("auditor_frn") or prof.get("auditor_name"):
                is_verified = True
                extracted_info = {
                    "auditor_name": prof.get("auditor_name") or extracted_info.get("auditor_name") or "Statutory Auditors Appointed",
                    "auditor_frn": prof.get("auditor_frn") or extracted_info.get("auditor_frn") or "FRN Verified"
                }
            else:
                is_verified = False
                extracted_info = {"auditor_name": "Pending ADT-1 Filing", "auditor_frn": ""}
        elif code == "INC_20A":
            has_inc20a_doc = bool(
                vault_map.get("INC_20A") or
                vault_map.get("inc_20a") or
                vault_map.get("form_inc_20a") or
                prof.get("inc20a_status") or
                prof.get("inc20a_verified") or
                prof.get("borrowing_powers_active") or
                any(e.category == "inc_20a" and e.status == "completed" for e in comp_events)
            )
            if has_inc20a_doc:
                is_verified = True
                extracted_info = {
                    "declaration": "Business Commencement Declared u/s 10A",
                    "borrowing_powers": "Active & Verified"
                }
            else:
                is_verified = False
                extracted_info = {
                    "declaration": "Pending Form INC-20A Filing",
                    "borrowing_powers": "Inactive until Form INC-20A uploaded"
                }
        elif code == "AUDITOR_REPORT":
            if vault_doc or prof.get("auditor_report_verified"):
                is_verified = True
                extracted_info = {
                    "audit_opinion": extracted_info.get("audit_opinion") or prof.get("audit_opinion") or "Unqualified (Clean Opinion)",
                    "cin": extracted_info.get("cin") or tenant.cin or "",
                    "srn": extracted_info.get("srn") or prof.get("srn") or ""
                }
            else:
                is_verified = False
                extracted_info = {"audit_opinion": "Pending Extract of Auditor's Report Upload"}
        elif code == "BOARD_REPORT":
            if vault_doc or prof.get("board_report_verified"):
                is_verified = True
                extracted_info = {
                    "board_report_status": extracted_info.get("board_report_status") or prof.get("board_report_status") or "Verified u/s 134",
                    "cin": extracted_info.get("cin") or tenant.cin or "",
                    "srn": extracted_info.get("srn") or prof.get("srn") or ""
                }
            else:
                is_verified = False
                extracted_info = {"board_report_status": "Pending Extract of Board's Report Upload"}
        elif code == "DIR_12":
            if vault_doc or prof.get("dir12_verified"):
                is_verified = True
            else:
                is_verified = False
                if prof.get("directors"):
                    d_str = ", ".join(f"{d.get('name')} (DIN: {d.get('din')})" for d in prof["directors"])
                    extracted_info = {"directors_extracted": d_str}
        elif code == "AOC_4":
            if vault_doc or prof.get("aoc4_verified"):
                is_verified = True
                extracted_info = {
                    "srn": extracted_info.get("srn") or prof.get("aoc4_srn") or "Verified AOC-4 Filing",
                    "financial_year": extracted_info.get("financial_year") or prof.get("financial_year") or "",
                    "agm_date": extracted_info.get("agm_date") or ""
                }
            else:
                is_verified = False
                extracted_info = {"srn": "Pending Form AOC-4 Filing"}
        elif code == "MGT_7A":
            if vault_doc or prof.get("mgt7_verified"):
                is_verified = True
                extracted_info = {
                    "srn": extracted_info.get("srn") or prof.get("mgt7_srn") or "Verified MGT-7A Return",
                    "board_meetings_count": str(extracted_info.get("board_meetings_held_count") or "")
                }
            else:
                is_verified = False
                extracted_info = {"srn": "Pending Form MGT-7A Filing"}
        elif code == "ITR":
            if vault_doc or prof.get("itr_verified"):
                is_verified = True
                extracted_info = {
                    "acknowledgement_number": extracted_info.get("itr_ack_number") or extracted_info.get("acknowledgement_number") or prof.get("itr_ack") or "Verified u/s 139",
                    "assessment_year": extracted_info.get("assessment_year") or prof.get("assessment_year") or "",
                    "pan": extracted_info.get("pan") or tenant.pan or "",
                    "filing_date": extracted_info.get("filing_date") or ""
                }
            else:
                is_verified = False
                extracted_info = {"acknowledgement_number": "Pending Income Tax Return (ITR-6) Upload"}
        else:
            if vault_doc:
                is_verified = True
                if not extracted_info and vault_doc.metadata_json:
                    extracted_info = vault_doc.metadata_json.get("extracted_fields", {})

        docs_status.append({
            "code": code,
            "name": item["name"],
            "authority": item["authority"],
            "purpose": item["purpose"],
            "category": item["category"],
            "status": "verified" if is_verified else "pending",
            "is_uploaded": vault_doc is not None,
            "file_size_bytes": vault_doc.file_size_bytes if vault_doc else None,
            "sha256_hash": vault_doc.sha256_hash if vault_doc else None,
            "extracted_entities": extracted_info,
            "can_download": True,
            "download_url": f"/api/v1/compliance/download-document/{code}"
        })

    return {
        "tenant_id": str(tenant.id),
        "legal_name": tenant.legal_name,
        "cin": tenant.cin,
        "pan": tenant.pan if (tenant.pan and not str(tenant.pan).startswith("AABCA1234")) else "",
        "gstin": tenant.gstin if ((vault_map.get("GST_REG06") or prof.get("gst_reg06_verified")) and tenant.gstin and not str(tenant.gstin).startswith("29AABCA1234")) else "",
        "tan": prof.get("tan") if ((vault_map.get("TAN") or prof.get("tan_verified")) and prof.get("tan") and not str(prof.get("tan")).startswith("BLRA12345")) else "",
        "registered_office": tenant.registered_office,
        "total_statutory_documents": len(STATUTORY_CATALOG),
        "verified_count": sum(1 for d in docs_status if d["status"] == "verified"),
        "documents": docs_status
    }

@router.get("/download-document/{doc_code}")
async def download_statutory_document(
    doc_code: str,
    tenant: Tenant = Depends(get_current_tenant)
):
    """
    Downloads the official statutory document or certified source-of-truth extract PDF.
    """
    data = {
        "company_name": tenant.legal_name,
        "legal_name": tenant.legal_name,
        "cin": tenant.cin or "",
        "registered_office": tenant.registered_office or "Indiranagar, Bengaluru - 560038, Karnataka, India",
        "pan": tenant.pan or "",
        "gstin": tenant.gstin if tenant.gstin and not str(tenant.gstin).startswith("29AABCA1234") else ""
    }
    pdf_bytes = DocumentAssemblyService.assemble_statutory_extract(doc_code, data)
    filename = f"{tenant.legal_name.replace(' ', '_')}_{doc_code.upper()}_EXTRACT.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.post("/generate-letterhead")
async def generate_company_letterhead(
    tenant: Tenant = Depends(get_current_tenant)
):
    """
    Generates a certified official Corporate Letterhead PDF binding the company name,
    CIN, PAN, GSTIN, and registered office.
    """
    data = {
        "company_name": tenant.legal_name,
        "legal_name": tenant.legal_name,
        "cin": tenant.cin or "",
        "pan": tenant.pan or "",
        "gstin": tenant.gstin if tenant.gstin and not str(tenant.gstin).startswith("29AABCK9012") else "",
        "registered_office": tenant.registered_office or "Indiranagar, Bengaluru - 560038, Karnataka, India",
        "email": "compliance@b00k5.internal"
    }
    pdf_bytes = DocumentAssemblyService.assemble_letterhead(data)
    filename = f"{tenant.legal_name.replace(' ', '_')}_OFFICIAL_LETTERHEAD.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

class UpdateProfileRequest(BaseModel):
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    cin: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    state_code: Optional[str] = None
    registered_office: Optional[str] = None
    logo_url: Optional[str] = None

@router.post("/update-company-profile")
async def update_company_profile(
    payload: UpdateProfileRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the master company profile attributes and synchronizes with the statutory profile.
    """
    if payload.legal_name: tenant.legal_name = payload.legal_name
    if payload.trade_name: tenant.trade_name = payload.trade_name
    if payload.cin: tenant.cin = payload.cin.strip().upper()
    if payload.pan: tenant.pan = payload.pan.strip().upper()
    if payload.gstin: tenant.gstin = payload.gstin.strip().upper()
    if payload.state_code: tenant.state_code = payload.state_code.strip()
    if payload.registered_office: tenant.registered_office = payload.registered_office

    prof = dict(tenant.statutory_profile or {})
    if payload.logo_url: prof["logo_url"] = payload.logo_url
    if payload.registered_office: prof["registered_office"] = payload.registered_office
    tenant.statutory_profile = prof

    await db.commit()
    await db.refresh(tenant)

    return {
        "success": True,
        "message": "Company profile updated successfully.",
        "tenant": {
            "legal_name": tenant.legal_name,
            "trade_name": tenant.trade_name,
            "cin": tenant.cin,
            "pan": tenant.pan,
            "gstin": tenant.gstin,
            "state_code": tenant.state_code,
            "registered_office": tenant.registered_office
        }
    }


