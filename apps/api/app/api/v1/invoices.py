from typing import List, Optional
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user, get_current_tenant
from app.models.tenant import User, Tenant
from app.models.invoice import Invoice, InvoiceItem, Contact
from app.schemas.invoice import (
    InvoiceCreate, InvoiceResponse,
    ContactCreate, ContactResponse
)
from app.services.gst_calculator import calculate_tax_breakdown, COMMON_HSN_SAC
from app.services.ledger_service import LedgerService
from app.services.pdf_service import PDFService
from app.services.bill_invoice_parser import BillInvoiceParser
from app.core.s3 import upload_document
from app.core.config import settings
from app.core.fiscal_year import get_or_create_fiscal_year

router = APIRouter()

@router.get("/hsn-catalog")
def get_hsn_catalog():
    """Returns standard Indian HSN/SAC master database."""
    return [{"code": k, **v} for k, v in COMMON_HSN_SAC.items()]

@router.post("/contacts", response_model=ContactResponse)
async def create_contact(
    payload: ContactCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    contact = Contact(
        tenant_id=tenant.id,
        name=payload.name,
        is_customer=payload.is_customer,
        is_vendor=payload.is_vendor,
        gstin=payload.gstin.strip().upper() if payload.gstin else None,
        pan=payload.pan.strip().upper() if payload.pan else None,
        state_code=payload.state_code.strip(),
        billing_address=payload.billing_address,
        shipping_address=payload.shipping_address,
        email=payload.email,
        phone=payload.phone
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact

@router.get("/contacts", response_model=List[ContactResponse])
async def list_contacts(
    is_customer: Optional[bool] = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contact).where(Contact.tenant_id == tenant.id)
    if is_customer is not None:
        stmt = stmt.where(Contact.is_customer == is_customer)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/", response_model=InvoiceResponse)
async def create_invoice(
    payload: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a GST-compliant Tax Invoice, dynamically determines IGST vs CGST+SGST
    based on Company Operating State vs Place of Supply (POS), and automatically
    posts balanced double-entry accounts receivable entries into the General Ledger.
    """
    # 1. Validate contact
    contact_res = await db.execute(
        select(Contact).where(Contact.id == payload.contact_id, Contact.tenant_id == tenant.id)
    )
    contact = contact_res.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Selected contact not found")

    # 2. Check for duplicate invoice number
    existing_inv = await db.execute(
        select(Invoice).where(Invoice.invoice_number == payload.invoice_number, Invoice.tenant_id == tenant.id)
    )
    if existing_inv.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate invoice detected: Invoice number '{payload.invoice_number}' already exists in your ledger."
        )

    # 3. Calculate tax breakdown across items
    operating_state = tenant.state_code
    pos = payload.place_of_supply.strip()
    is_interstate = (operating_state != pos)

    subtotal = Decimal("0.00")
    cgst_total = Decimal("0.00")
    sgst_total = Decimal("0.00")
    igst_total = Decimal("0.00")
    grand_total = Decimal("0.00")

    calculated_items = []
    for item_in in payload.items:
        taxable_val = round(item_in.quantity * item_in.unit_price, 2)
        calc = calculate_tax_breakdown(
            operating_state=operating_state,
            place_of_supply=pos,
            taxable_value=taxable_val,
            gst_rate_percent=item_in.gst_rate_percent
        )

        item = InvoiceItem(
            item_description=item_in.item_description,
            hsn_sac_code=item_in.hsn_sac_code,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price,
            taxable_value=taxable_val,
            gst_rate_percent=item_in.gst_rate_percent,
            cgst_amount=calc["cgst_amount"],
            sgst_amount=calc["sgst_amount"],
            igst_amount=calc["igst_amount"],
            total_amount=calc["total_amount"]
        )
        calculated_items.append(item)

        subtotal += taxable_val
        cgst_total += calc["cgst_amount"]
        sgst_total += calc["sgst_amount"]
        igst_total += calc["igst_amount"]
        grand_total += calc["total_amount"]

    # 4. Resolve Dynamic Fiscal Year and Create Invoice Record
    fy_record = await get_or_create_fiscal_year(db, tenant.id, payload.issue_date)

    invoice = Invoice(
        tenant_id=tenant.id,
        contact_id=contact.id,
        invoice_number=payload.invoice_number,
        type=payload.type,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        place_of_supply=pos,
        is_interstate=is_interstate,
        subtotal=subtotal,
        cgst_total=cgst_total,
        sgst_total=sgst_total,
        igst_total=igst_total,
        grand_total=grand_total,
        status="sent",
        fiscal_year_id=fy_record.id,
        items=calculated_items
    )
    db.add(invoice)
    await db.flush()

    # 5. Automatically post Double-Entry Journal Entry
    try:
        await LedgerService.post_invoice_journal(db, invoice, current_user.id)
    except Exception as e:
        # If journal posting encounters an error, roll back
        raise HTTPException(status_code=500, detail=f"Ledger posting error: {str(e)}")

    # 6. Generate and upload Invoice PDF to MinIO
    try:
        pdf_bytes = PDFService.generate_simple_invoice_pdf({
            "invoice_number": invoice.invoice_number,
            "grand_total": str(invoice.grand_total),
            "subtotal": str(invoice.subtotal),
            "cgst_total": str(invoice.cgst_total),
            "sgst_total": str(invoice.sgst_total),
            "igst_total": str(invoice.igst_total),
            "issue_date": str(invoice.issue_date),
            "contact_name": contact.name,
            "place_of_supply": pos
        })
        s3_key = f"{tenant.id}/invoices/{invoice.invoice_number}.pdf"
        upload_document(settings.BUCKET_INVOICES, pdf_bytes, s3_key, "application/pdf")
        invoice.pdf_s3_key = s3_key
    except Exception:
        # Non-fatal during dev if MinIO is not running
        pass

    await db.commit()
    await db.refresh(invoice)
    return invoice

@router.get("/", response_model=List[InvoiceResponse])
async def list_invoices(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.tenant_id == tenant.id)
        .order_by(Invoice.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant.id)
    )
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv

@router.post("/scan-invoice")
async def scan_customer_invoice(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests and OCR-extracts outward customer invoices (PDF/image):
    - Extracts invoice number, issue date, customer details, line items, taxes, totals
    - Prevents duplicates by verifying invoice_number against tenant's registered invoices
    - Automatically links or prepares contact
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file payload")

    closed_fys = (tenant.statutory_profile or {}).get("closed_fiscal_years", {})
    parsed = BillInvoiceParser.parse_customer_invoice(
        file_bytes=file_bytes,
        filename=file.filename or "invoice.pdf",
        password=password,
        closed_fiscal_years=closed_fys
    )

    if parsed.get("needs_password"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "needs_password": True,
                "message": parsed.get("message", "This invoice PDF is encrypted. Please provide password.")
            }
        )

    # Deduplication check
    inv_num = parsed["invoice_number"]
    dup_stmt = select(Invoice).where(
        Invoice.tenant_id == tenant.id,
        Invoice.invoice_number == inv_num
    )
    existing_inv = (await db.execute(dup_stmt)).scalars().first()

    is_duplicate = False
    duplicate_reason = None
    if existing_inv:
        is_duplicate = True
        duplicate_reason = f"Duplicate invoice detected: Invoice '{inv_num}' already exists in your ledger."

    # Find or auto-provision contact
    contact_stmt = select(Contact).where(
        Contact.tenant_id == tenant.id,
        Contact.name == parsed["customer_name"]
    )
    contact = (await db.execute(contact_stmt)).scalars().first()
    if not contact:
        contact = Contact(
            tenant_id=tenant.id,
            name=parsed["customer_name"],
            is_customer=True,
            gstin=parsed["customer_gstin"],
            state_code=parsed["place_of_supply"],
            billing_address="Commercial Registered Address",
            shipping_address="Commercial Registered Address"
        )
        db.add(contact)
        await db.flush()

    return {
        **parsed,
        "is_duplicate": is_duplicate,
        "duplicate_reason": duplicate_reason,
        "contact_id": str(contact.id)
    }

