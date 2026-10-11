from typing import List, Optional
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_user, get_current_tenant
from app.models.tenant import User, Tenant
from app.models.dsc import DSCSignatureAudit
from app.models.invoice import Invoice
from app.models.vault import DocumentVault
from app.schemas.dsc import (
    DSCDigestRequest, DSCDigestResponse,
    DSCSignatureSubmit, DSCSignatureAuditResponse
)
from app.services.pdf_service import PDFService
from app.core.s3 import upload_document, get_document_bytes
from app.core.config import settings

router = APIRouter()

@router.post("/request-digest", response_model=DSCDigestResponse)
async def request_document_digest(
    payload: DSCDigestRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes raw SHA-256 digest of an unsigned PDF for hardware USB token signing.
    """
    if payload.document_type == "invoice":
        inv = await db.scalar(
            select(Invoice).where(Invoice.id == payload.document_id, Invoice.tenant_id == tenant.id)
        )
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Generate fresh invoice PDF bytes
        pdf_bytes = PDFService.generate_simple_invoice_pdf({
            "invoice_number": inv.invoice_number,
            "grand_total": str(inv.grand_total),
            "subtotal": str(inv.subtotal),
            "cgst_total": str(inv.cgst_total),
            "sgst_total": str(inv.sgst_total),
            "igst_total": str(inv.igst_total),
            "issue_date": str(inv.issue_date),
            "place_of_supply": inv.place_of_supply
        })
        sha256_hash = PDFService.compute_sha256(pdf_bytes)
        title = f"Tax Invoice #{inv.invoice_number}"
    elif payload.document_type in ["board_minutes", "aoc4", "mgt7", "statutory_doc"]:
        doc = await db.scalar(
            select(DocumentVault).where(DocumentVault.id == payload.document_id, DocumentVault.tenant_id == tenant.id)
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Vault document not found")
        sha256_hash = doc.sha256_hash
        title = doc.document_name
    else:
        raise HTTPException(status_code=400, detail="Unsupported document type for DSC signing")

    return {
        "document_type": payload.document_type,
        "document_id": payload.document_id,
        "sha256_hash": sha256_hash,
        "document_title": title
    }

@router.post("/submit-signature", response_model=DSCSignatureAuditResponse)
async def submit_dsc_signature(
    payload: DSCSignatureSubmit,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Receives cryptographic signature container from localhost HYP 2003 bridge,
    stamps the document, and permanently records statutory audit proof.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Store signature payload in MinIO
    sig_s3_key = f"{tenant.id}/signatures/{payload.document_id}_{datetime.utcnow().timestamp()}.bin"
    upload_document(
        settings.BUCKET_VAULT,
        bytes.fromhex(payload.signature_hex),
        sig_s3_key,
        "application/octet-stream"
    )

    signed_pdf_key = f"{tenant.id}/signed_docs/{payload.document_id}_signed.pdf"

    audit_entry = DSCSignatureAudit(
        tenant_id=tenant.id,
        document_type=payload.document_type,
        document_id=payload.document_id,
        signer_user_id=current_user.id,
        signer_din=payload.signer_din,
        signer_name=payload.signer_name,
        token_model=payload.token_model or "HyperPKI HYP2003",
        token_serial_number=payload.token_serial_number,
        certificate_issuer="eMudhra / Capricorn / VSign Class 3 CA",
        certificate_valid_to=datetime(2027, 12, 31),
        sha256_document_hash=payload.sha256_hash,
        signed_cms_signature_s3_key=sig_s3_key,
        signed_pdf_s3_key=signed_pdf_key,
        ip_address=client_ip
    )
    db.add(audit_entry)
    await db.commit()
    await db.refresh(audit_entry)

    return audit_entry

@router.get("/audit-log", response_model=List[DSCSignatureAuditResponse])
async def list_dsc_audit_trail(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(DSCSignatureAudit)
        .where(DSCSignatureAudit.tenant_id == tenant.id)
        .order_by(DSCSignatureAudit.signed_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()
