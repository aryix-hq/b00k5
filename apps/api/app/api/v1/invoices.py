from typing import List, Optional, Any, Dict
import uuid
from decimal import Decimal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user, get_current_tenant, check_mandatory_company_documents
from app.models.tenant import User, Tenant
from app.models.invoice import Invoice, InvoiceItem, Contact
from app.models.ledger import JournalEntry, JournalLine
from app.schemas.invoice import (
    InvoiceCreate, InvoiceUpdate, InvoiceResponse,
    ContactCreate, ContactResponse
)
from app.services.gst_calculator import calculate_tax_breakdown, COMMON_HSN_SAC
from app.services.ledger_service import LedgerService
from app.services.pdf_service import PDFService
from app.services.bill_invoice_parser import BillInvoiceParser
from app.core.s3 import upload_document
from app.core.config import settings
from app.core.fiscal_year import get_or_create_fiscal_year
from app.core.iam import require_owner, require_ca_or_owner, IAMContext
from app.services.einvoice_service import EInvoiceService
from app.services.gstr1_export_service import GSTR1ExportService
from app.schemas.einvoice import EInvoiceResponse, EInvoiceGenerateRequest
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/hsn-catalog")
def get_hsn_catalog():
    """Returns standard Indian HSN/SAC master database."""
    return [{"code": k, **v} for k, v in COMMON_HSN_SAC.items()]

@router.post("/contacts", response_model=ContactResponse)
async def create_contact(
    payload: ContactCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    contact = Contact(
        tenant_id=ctx.tenant.id,
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
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contact).where(Contact.tenant_id == ctx.tenant.id)
    if is_customer is not None:
        stmt = stmt.where(Contact.is_customer == is_customer)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.put("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: uuid.UUID,
    payload: ContactCreate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contact).where(Contact.id == contact_id, Contact.tenant_id == ctx.tenant.id)
    contact = (await db.execute(stmt)).scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.name = payload.name.strip()
    contact.gstin = payload.gstin.strip().upper() if payload.gstin else None
    contact.pan = payload.pan.strip().upper() if payload.pan else None
    contact.state_code = payload.state_code.strip()
    contact.billing_address = payload.billing_address.strip()
    if payload.shipping_address:
        contact.shipping_address = payload.shipping_address.strip()
    contact.email = payload.email.strip() if payload.email else None
    contact.phone = payload.phone.strip() if payload.phone else None
    await db.commit()
    await db.refresh(contact)
    return contact

@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: uuid.UUID,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes an unreferenced customer contact.
    Enforces statutory invariant: contacts with linked tax invoices cannot be deleted
    to preserve Companies Act Section 128 double-entry audit trails and GST records.
    """
    stmt = select(Contact).where(Contact.id == contact_id, Contact.tenant_id == ctx.tenant.id)
    contact = (await db.execute(stmt)).scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer contact not found")

    # Check for linked invoices
    inv_count_stmt = select(func.count(Invoice.id)).where(
        Invoice.contact_id == contact_id,
        Invoice.tenant_id == ctx.tenant.id
    )
    linked_count = (await db.execute(inv_count_stmt)).scalar() or 0
    if linked_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete customer '{contact.name}': {linked_count} tax invoice(s) are linked to this record. Companies Act audit trail rules require customer records with posted transactions to be preserved."
        )

    await db.delete(contact)
    await db.commit()
    return {"status": "success", "message": f"Customer '{contact.name}' deleted successfully."}

@router.post("/", response_model=InvoiceResponse)
async def create_invoice(
    payload: InvoiceCreate,
    ctx: IAMContext = Depends(require_owner),
    _doc_guard: Tenant = Depends(check_mandatory_company_documents),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a GST-compliant Tax Invoice, dynamically determines IGST vs CGST+SGST
    based on Company Operating State vs Place of Supply (POS), and automatically
    posts balanced double-entry accounts receivable entries into the General Ledger.
    """
    current_user = ctx.user
    tenant = ctx.tenant

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

    has_gstin = bool(tenant.gstin and len(tenant.gstin.strip()) == 15)

    if not has_gstin:
        for item_in in payload.items:
            rate_dec = Decimal(str(item_in.gst_rate_percent or 0))
            if rate_dec > Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Statutory Violation (Section 32 CGST Act): Unregistered entities without a verified GSTIN cannot collect GST or issue Tax Invoices. Tax rate must be 0.00% (Bill of Supply)."
                )

    calculated_items = []
    for item_in in payload.items:
        taxable_val = round(item_in.quantity * item_in.unit_price, 2)
        if has_gstin:
            calc = calculate_tax_breakdown(
                operating_state=operating_state,
                place_of_supply=pos,
                taxable_value=taxable_val,
                gst_rate_percent=item_in.gst_rate_percent
            )
            item_gst_rate = item_in.gst_rate_percent
        else:
            # Unregistered supplier under CGST Act Section 22 / 32: Tax rate is strictly 0.00%
            calc = {
                "cgst_amount": Decimal("0.00"),
                "sgst_amount": Decimal("0.00"),
                "igst_amount": Decimal("0.00"),
                "total_amount": taxable_val
            }
            item_gst_rate = Decimal("0.00")

        item = InvoiceItem(
            item_description=item_in.item_description,
            hsn_sac_code=item_in.hsn_sac_code,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price,
            taxable_value=taxable_val,
            gst_rate_percent=item_gst_rate,
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

    # 6. Preserve original uploaded Invoice PDF if provided; only generate simple PDF for manually typed invoices
    if getattr(payload, "pdf_s3_key", None):
        invoice.pdf_s3_key = payload.pdf_s3_key
    else:
        try:
            primary_ac = (tenant.statutory_profile or {}).get("primary_bank_account") or {}
            pdf_bytes = PDFService.generate_simple_invoice_pdf({
                "invoice_number": invoice.invoice_number,
                "seller_name": tenant.legal_name,
                "seller_cin": tenant.cin,
                "seller_gstin": tenant.gstin,
                "seller_pan": tenant.pan,
                "seller_address": tenant.registered_office,
                "seller_email": getattr(current_user, "email", "") or "",
                "seller_phone": getattr(current_user, "phone", "") or "",
                "logo_url": tenant.logo_url or (tenant.statutory_profile or {}).get("logo_url"),
                "logo_s3_key": tenant.logo_s3_key or (tenant.statutory_profile or {}).get("logo_s3_key"),
                "issue_date": str(invoice.issue_date),
                "due_date": str(invoice.due_date),
                "place_of_supply": pos,
                "customer_name": contact.name,
                "customer_gstin": contact.gstin or "",
                "customer_address": contact.billing_address or "",
                "customer_email": getattr(contact, "email", "") or "",
                "customer_phone": getattr(contact, "phone", "") or "",
                "subtotal": float(invoice.subtotal),
                "cgst_total": float(invoice.cgst_total),
                "sgst_total": float(invoice.sgst_total),
                "igst_total": float(invoice.igst_total),
                "grand_total": float(invoice.grand_total),
                "items": [
                    {
                        "description": getattr(it, "item_description", getattr(it, "description", "Services")),
                        "hsn_sac_code": getattr(it, "hsn_sac_code", "-"),
                        "quantity": float(it.quantity or 1),
                        "unit_price": float(it.unit_price or 0),
                        "taxable_amount": float(getattr(it, "taxable_value", getattr(it, "taxable_amount", 0)))
                    }
                    for it in invoice.items
                ],
                "bank_details": primary_ac
            })
            s3_key = f"{tenant.id}/invoices/{invoice.invoice_number}.pdf"
            upload_document(settings.BUCKET_INVOICES, pdf_bytes, s3_key, "application/pdf")
            invoice.pdf_s3_key = s3_key
        except Exception:
            pass

    # 7. Auto-reconcile any open bank statements so newly added invoice matches existing statement lines
    try:
        from app.models.bank import BankStatement
        from app.services.reconciliation_engine import ReconciliationEngine
        stmts = (await db.execute(
            select(BankStatement).where(BankStatement.tenant_id == tenant.id)
        )).scalars().all()
        for s in stmts:
            await ReconciliationEngine.reconcile_statement(
                session=db, tenant_id=tenant.id, statement_id=s.id, user_id=current_user.id
            )
    except Exception:
        pass

    await db.commit()
    stmt_ref = (
        select(Invoice)
        .options(selectinload(Invoice.items), selectinload(Invoice.contact))
        .where(Invoice.id == invoice.id)
    )
    return (await db.execute(stmt_ref)).scalar_one()

@router.get("/", response_model=List[InvoiceResponse])
async def list_invoices(
    fy: Optional[str] = Query(None),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items), selectinload(Invoice.contact))
        .where(Invoice.tenant_id == ctx.tenant.id)
    )
    if fy and fy.lower() != "all":
        from app.core.fiscal_year import get_fy_date_bounds
        try:
            fy_start, fy_end = get_fy_date_bounds(fy)
            stmt = stmt.where(Invoice.issue_date >= fy_start, Invoice.issue_date <= fy_end)
        except Exception:
            pass
    stmt = stmt.order_by(Invoice.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/next-number")
async def get_next_invoice_number(
    invoice_date: Optional[str] = None,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the next sequential invoice number in Indian standard format INV-YYYY-MM-XXX
    (e.g., INV-2026-05-001, INV-2026-10-001).
    """
    from datetime import datetime, date as dt_date
    target_dt = dt_date.today()
    if invoice_date:
        try:
            target_dt = datetime.strptime(invoice_date[:10], "%Y-%m-%d").date()
        except Exception:
            pass

    year_str = str(target_dt.year)
    month_str = f"{target_dt.month:02d}"
    prefix = f"INV-{year_str}-{month_str}-"

    stmt = select(Invoice.invoice_number).where(
        Invoice.tenant_id == ctx.tenant.id,
        Invoice.invoice_number.like(f"{prefix}%")
    )
    existing_nums = (await db.execute(stmt)).scalars().all()

    max_seq = 0
    for num in existing_nums:
        suffix = num[len(prefix):]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))

    next_seq = max_seq + 1
    next_num = f"{prefix}{next_seq:03d}"
    return {
        "next_invoice_number": next_num,
        "format": "INV-YYYY-MM-XXX",
        "year": year_str,
        "month": month_str,
        "sequence": next_seq
    }


class GSTThresholdStatusResponse(BaseModel):
    has_gstin: bool
    gstin: Optional[str] = None
    is_registered: bool
    current_fy: str
    turnover_amount: float
    threshold_limit: float = 2000000.00
    threshold_exceeded: bool
    threshold_approaching: bool
    exemption_active: bool
    status_code: str
    message: str


@router.get("/gst-threshold-status", response_model=GSTThresholdStatusResponse)
async def get_gst_threshold_status(
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Statutory Section 22 CGST Act Turnover Threshold & GST Registration Watchdog.
    - Evaluates aggregate turnover against ₹20,00,000 threshold for the current FY.
    - If GSTIN is absent and turnover exceeds ₹20 Lakhs, prompts mandatory registration.
    - If turnover is under ₹20 Lakhs, confirms Section 22 Exemption (Non-GST / Bill of Supply Mode).
    """
    tenant = ctx.tenant
    clean_gstin = (tenant.gstin or "").strip().upper()
    has_gstin = len(clean_gstin) == 15

    from app.core.fiscal_year import resolve_fiscal_calendar, get_fy_date_bounds
    cal = resolve_fiscal_calendar()
    active_fy = cal.get("active_fy", "2026-27")
    fy_start, fy_end = get_fy_date_bounds(active_fy)

    stmt = (
        select(func.coalesce(func.sum(Invoice.subtotal), Decimal("0.00")))
        .where(
            Invoice.tenant_id == tenant.id,
            Invoice.issue_date.between(fy_start, fy_end),
            Invoice.status != "cancelled"
        )
    )
    res = await db.execute(stmt)
    turnover = Decimal(str(res.scalar_one() or "0.00"))
    turnover_float = float(turnover)

    threshold_limit = 2000000.00
    approaching_limit = 1500000.00

    if has_gstin:
        return GSTThresholdStatusResponse(
            has_gstin=True,
            gstin=clean_gstin,
            is_registered=True,
            current_fy=f"FY {active_fy}",
            turnover_amount=turnover_float,
            threshold_limit=threshold_limit,
            threshold_exceeded=False,
            threshold_approaching=False,
            exemption_active=False,
            status_code="registered",
            message=f"GSTIN {clean_gstin} verified and registered on GSTN."
        )

    if turnover_float >= threshold_limit:
        return GSTThresholdStatusResponse(
            has_gstin=False,
            gstin=None,
            is_registered=False,
            current_fy=f"FY {active_fy}",
            turnover_amount=turnover_float,
            threshold_limit=threshold_limit,
            threshold_exceeded=True,
            threshold_approaching=False,
            exemption_active=False,
            status_code="threshold_exceeded",
            message=(
                f"CGST Section 22 Mandatory Registration Alert: Current FY turnover of ₹{turnover_float:,.2f} "
                f"has exceeded the statutory threshold of ₹20,00,000. Under Section 22 of the CGST Act 2017, "
                f"the company is legally required to apply for GST Registration within 30 days."
            )
        )
    elif turnover_float >= approaching_limit:
        return GSTThresholdStatusResponse(
            has_gstin=False,
            gstin=None,
            is_registered=False,
            current_fy=f"FY {active_fy}",
            turnover_amount=turnover_float,
            threshold_limit=threshold_limit,
            threshold_exceeded=False,
            threshold_approaching=True,
            exemption_active=True,
            status_code="approaching",
            message=(
                f"GST Threshold Warning: Current FY turnover is ₹{turnover_float:,.2f} "
                f"({round((turnover_float / threshold_limit) * 100, 1)}% of ₹20,00,000 limit). "
                f"Mandatory GST registration will be triggered upon crossing ₹20 Lakhs."
            )
        )
    else:
        return GSTThresholdStatusResponse(
            has_gstin=False,
            gstin=None,
            is_registered=False,
            current_fy=f"FY {active_fy}",
            turnover_amount=turnover_float,
            threshold_limit=threshold_limit,
            threshold_exceeded=False,
            threshold_approaching=False,
            exemption_active=True,
            status_code="exempt",
            message=(
                f"Section 22 Exemption Active: Current FY turnover of ₹{turnover_float:,.2f} is below the "
                f"₹20,00,000 threshold. Invoicing is issued in Non-GST / Bill of Supply mode."
            )
        )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items), selectinload(Invoice.contact))
        .where(Invoice.id == invoice_id, Invoice.tenant_id == ctx.tenant.id)
    )
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv

@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Modifies an existing invoice:
    - Allows updating invoice number, customer contact, issue/due dates, POS, and line items
    - Automatically re-balances General Ledger double-entry journal vouchers
    - Re-generates verified tax invoice PDF with database-driven seller and customer details
    """
    current_user = ctx.user
    tenant = ctx.tenant
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items), selectinload(Invoice.contact))
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant.id)
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice record not found")

    # Protection against closed financial years
    closed_fys = (tenant.statutory_profile or {}).get("closed_fiscal_years", {})
    from app.core.fiscal_year import get_financial_year
    check_date = payload.issue_date or inv.issue_date
    fy_str = get_financial_year(check_date)
    if closed_fys.get(fy_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify invoice #{inv.invoice_number} because Financial Year {fy_str} is legally locked and closed."
        )

    # Check duplicate invoice number if changed
    if payload.invoice_number and payload.invoice_number.strip() != inv.invoice_number:
        dup = await db.execute(
            select(Invoice).where(
                Invoice.tenant_id == tenant.id,
                Invoice.invoice_number == payload.invoice_number.strip(),
                Invoice.id != inv.id
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invoice number '{payload.invoice_number.strip()}' is already taken by another invoice."
            )
        inv.invoice_number = payload.invoice_number.strip()

    # Update Contact if changed
    contact = inv.contact
    if payload.contact_id and payload.contact_id != inv.contact_id:
        c_stmt = select(Contact).where(Contact.id == payload.contact_id, Contact.tenant_id == tenant.id)
        c_res = (await db.execute(c_stmt)).scalar_one_or_none()
        if not c_res:
            raise HTTPException(status_code=404, detail="Selected contact does not exist")
        inv.contact_id = c_res.id
        inv.contact = c_res
        contact = c_res

    if payload.issue_date:
        inv.issue_date = payload.issue_date
    if payload.due_date:
        inv.due_date = payload.due_date
    if payload.place_of_supply:
        inv.place_of_supply = payload.place_of_supply.strip()

    operating_state = tenant.state_code
    pos = inv.place_of_supply
    inv.is_interstate = (operating_state != pos)

    # Re-calculate line items if updated
    if payload.items is not None and len(payload.items) > 0:
        for old_it in list(inv.items):
            await db.delete(old_it)
        inv.items.clear()

        subtotal = Decimal("0.00")
        cgst_total = Decimal("0.00")
        sgst_total = Decimal("0.00")
        igst_total = Decimal("0.00")
        grand_total = Decimal("0.00")

        new_items = []
        for it_in in payload.items:
            taxable_val = round(it_in.quantity * it_in.unit_price, 2)
            calc = calculate_tax_breakdown(
                operating_state=operating_state,
                place_of_supply=pos,
                taxable_value=taxable_val,
                gst_rate_percent=it_in.gst_rate_percent
            )
            item = InvoiceItem(
                invoice_id=inv.id,
                item_description=it_in.item_description,
                hsn_sac_code=it_in.hsn_sac_code,
                quantity=it_in.quantity,
                unit_price=it_in.unit_price,
                taxable_value=taxable_val,
                gst_rate_percent=it_in.gst_rate_percent,
                cgst_amount=calc["cgst_amount"],
                sgst_amount=calc["sgst_amount"],
                igst_amount=calc["igst_amount"],
                total_amount=calc["total_amount"]
            )
            new_items.append(item)
            subtotal += taxable_val
            cgst_total += calc["cgst_amount"]
            sgst_total += calc["sgst_amount"]
            igst_total += calc["igst_amount"]
            grand_total += calc["total_amount"]

        inv.items = new_items
        inv.subtotal = subtotal
        inv.cgst_total = cgst_total
        inv.sgst_total = sgst_total
        inv.igst_total = igst_total
        inv.grand_total = grand_total

    if payload.status:
        inv.status = payload.status

    await db.flush()

    # Re-synchronize Double-Entry Journal Entry in General Ledger
    if inv.status != "cancelled":
        jv_stmt = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(
                JournalEntry.tenant_id == tenant.id,
                JournalEntry.reference_type == "invoice",
                JournalEntry.reference_id == inv.id
            )
        )
        existing_jv = (await db.execute(jv_stmt)).scalar_one_or_none()

        ar_acc = await LedgerService.ensure_account(db, tenant.id, "1020", "Trade Receivables (Sundry Debtors)", "asset", "accounts_receivable", "debit")
        rev_acc = await LedgerService.ensure_account(db, tenant.id, "3010", "Revenue from Operations (Sales / Services)", "revenue", "operating_revenue", "credit")
        cgst_acc = await LedgerService.ensure_account(db, tenant.id, "2050", "Output CGST Payable", "liability", "tax_payable", "credit")
        sgst_acc = await LedgerService.ensure_account(db, tenant.id, "2051", "Output SGST Payable", "liability", "tax_payable", "credit")
        igst_acc = await LedgerService.ensure_account(db, tenant.id, "2052", "Output IGST Payable", "liability", "tax_payable", "credit")

        if existing_jv:
            # Under Indian Accounting Standards and statutory immutability constraints,
            # a posted journal entry cannot be mutated. Post a formal Reversal JV.
            rev_jv_number = f"JV-INV-REVERSAL-{inv.invoice_number}-{uuid.uuid4().hex[:6].upper()}"
            reversal_entry = JournalEntry(
                tenant_id=tenant.id,
                entry_number=rev_jv_number,
                entry_date=inv.issue_date,
                reference_type="invoice_adjustment_reversal",
                reference_id=inv.id,
                narration=f"Reversal of original posted entry for modified invoice #{inv.invoice_number}",
                status="posted",
                is_posted=True,
                created_by=current_user.id
            )
            db.add(reversal_entry)
            await db.flush()

            rev_lines = []
            for old_line in existing_jv.lines:
                rev_lines.append(JournalLine(
                    journal_entry_id=reversal_entry.id,
                    tenant_id=tenant.id,
                    account_id=old_line.account_id,
                    debit_amount=old_line.credit_amount,
                    credit_amount=old_line.debit_amount,
                    description=f"Reversal: {old_line.description or 'Invoice adjustment'}"
                ))
            db.add_all(rev_lines)
            await db.flush()

        # Create the revised journal entry for the updated invoice amounts
        revised_jv_number = f"JV-INV-{inv.invoice_number}-{uuid.uuid4().hex[:6].upper()}"
        target_entry = JournalEntry(
            tenant_id=tenant.id,
            entry_number=revised_jv_number,
            entry_date=inv.issue_date,
            reference_type="invoice",
            reference_id=inv.id,
            narration=f"Revised Tax Invoice #{inv.invoice_number} issued to {contact.name if contact else 'contact'}",
            status="posted",
            is_posted=True,
            created_by=current_user.id
        )
        db.add(target_entry)
        await db.flush()

        jv_lines = [
            JournalLine(
                journal_entry_id=target_entry.id,
                tenant_id=tenant.id,
                account_id=ar_acc.id,
                debit_amount=inv.grand_total,
                credit_amount=Decimal("0.00"),
                description=f"Debtor claim for Inv #{inv.invoice_number}"
            ),
            JournalLine(
                journal_entry_id=target_entry.id,
                tenant_id=tenant.id,
                account_id=rev_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=inv.subtotal,
                description=f"Revenue recognition for Inv #{inv.invoice_number}"
            )
        ]
        if inv.cgst_total and inv.cgst_total > Decimal("0.00") and cgst_acc:
            jv_lines.append(JournalLine(
                journal_entry_id=target_entry.id,
                tenant_id=tenant.id,
                account_id=cgst_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=inv.cgst_total,
                description=f"Output CGST for Inv #{inv.invoice_number}"
            ))
        if inv.sgst_total and inv.sgst_total > Decimal("0.00") and sgst_acc:
            jv_lines.append(JournalLine(
                journal_entry_id=target_entry.id,
                tenant_id=tenant.id,
                account_id=sgst_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=inv.sgst_total,
                description=f"Output SGST for Inv #{inv.invoice_number}"
            ))
        if inv.igst_total and inv.igst_total > Decimal("0.00") and igst_acc:
            jv_lines.append(JournalLine(
                journal_entry_id=target_entry.id,
                tenant_id=tenant.id,
                account_id=igst_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=inv.igst_total,
                description=f"Output IGST for Inv #{inv.invoice_number}"
            ))
        db.add_all(jv_lines)

    # Re-generate and cache PDF
    try:
        primary_ac = (tenant.statutory_profile or {}).get("primary_bank_account") or {}
        pdf_bytes = PDFService.generate_simple_invoice_pdf({
            "invoice_number": inv.invoice_number,
            "seller_name": tenant.legal_name,
            "seller_cin": tenant.cin,
            "seller_gstin": tenant.gstin,
            "seller_pan": tenant.pan,
            "seller_address": tenant.registered_office,
            "seller_email": getattr(current_user, "email", "") or "",
            "seller_phone": getattr(current_user, "phone", "") or "",
            "logo_url": tenant.logo_url or (tenant.statutory_profile or {}).get("logo_url"),
            "logo_s3_key": tenant.logo_s3_key or (tenant.statutory_profile or {}).get("logo_s3_key"),
            "issue_date": str(inv.issue_date),
            "due_date": str(inv.due_date),
            "place_of_supply": inv.place_of_supply,
            "customer_name": contact.name if contact else "Valued Customer",
            "customer_gstin": contact.gstin if contact else "",
            "customer_address": contact.billing_address if contact else "",
            "customer_email": getattr(contact, "email", "") or "",
            "customer_phone": getattr(contact, "phone", "") or "",
            "status": inv.status,
            "is_paid": inv.status in ("paid", "settled"),
            "subtotal": float(inv.subtotal),
            "cgst_total": float(inv.cgst_total or 0),
            "sgst_total": float(inv.sgst_total or 0),
            "igst_total": float(inv.igst_total or 0),
            "grand_total": float(inv.grand_total),
            "items": [
                {
                    "description": getattr(it, "item_description", getattr(it, "description", "Services")),
                    "hsn_sac_code": getattr(it, "hsn_sac_code", "-"),
                    "quantity": float(it.quantity or 1),
                    "unit_price": float(it.unit_price or 0),
                    "taxable_amount": float(getattr(it, "taxable_value", getattr(it, "taxable_amount", 0)))
                }
                for it in inv.items
            ],
            "bank_details": primary_ac
        })
        s3_key = f"{tenant.id}/invoices/{inv.invoice_number}.pdf"
        upload_document(settings.BUCKET_INVOICES, pdf_bytes, s3_key, "application/pdf")
        inv.pdf_s3_key = s3_key
    except Exception:
        pass

    await db.commit()
    ref_stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items), selectinload(Invoice.contact))
        .where(Invoice.id == inv.id)
    )
    return (await db.execute(ref_stmt)).scalar_one()

@router.post("/scan-invoice")
async def scan_customer_invoice(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    current_user = ctx.user
    tenant = ctx.tenant
    """
    Ingests and OCR-extracts outward customer invoices (PDF/image):
    - Extracts invoice number, issue date, customer details, line items, taxes, totals
    - Saves original uploaded document to MinIO so Auditor Dossier exports the original invoice
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

    # Save original uploaded invoice file to MinIO
    from app.core.s3 import storage_manager
    raw_fname = file.filename or "invoice.pdf"
    safe_fname = "".join(c for c in raw_fname if c.isalnum() or c in (" ", "_", "-", ".")).strip() or "invoice.pdf"
    s3_key = f"{tenant.id}/invoices/{uuid.uuid4().hex[:8]}_{safe_fname}"
    try:
        storage_manager.save_document(
            bucket_name=getattr(settings, "BUCKET_INVOICES", settings.BUCKET_RECEIPTS),
            object_name=s3_key,
            file_bytes=file_bytes,
            content_type=file.content_type or "application/pdf"
        )
    except Exception:
        pass

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
        # Attach original uploaded PDF if existing invoice had no original PDF
        if not existing_inv.pdf_s3_key or existing_inv.pdf_s3_key.endswith(f"/{existing_inv.invoice_number}.pdf"):
            existing_inv.pdf_s3_key = s3_key
            await db.commit()

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
        await db.commit()

    return {
        **parsed,
        "pdf_s3_key": s3_key,
        "is_duplicate": is_duplicate,
        "duplicate_reason": duplicate_reason,
        "contact_id": str(contact.id)
    }


from pydantic import BaseModel, Field
from datetime import date, datetime
import csv
import io
import json
import re


class RazorpayItemImport(BaseModel):
    item_description: str = "Software / Consulting Services (Razorpay Invoice)"
    hsn_sac_code: str = "998314"
    quantity: Decimal = Decimal("1.00")
    unit_price: Decimal
    gst_rate_percent: Decimal = Decimal("0.00")


class RazorpaySingleInvoiceImport(BaseModel):
    invoice_number: str
    razorpay_invoice_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    issue_date: date = Field(default_factory=date.today)
    due_date: Optional[date] = None
    customer_name: str
    customer_gstin: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    place_of_supply: str = "29"
    payment_status: str = "paid"  # "paid" or "sent"
    gateway_fee: Decimal = Decimal("0.00")
    pdf_s3_key: Optional[str] = None
    items: List[RazorpayItemImport]


class RazorpayBatchImportRequest(BaseModel):
    invoices: List[RazorpaySingleInvoiceImport]


def _parse_razorpay_date(raw_val: Any) -> date:
    if not raw_val:
        return date.today()
    if isinstance(raw_val, date) and not isinstance(raw_val, datetime):
        return raw_val
    s = str(raw_val).strip()
    if s.isdigit():
        try:
            ts = int(s)
            if ts > 10_000_000_000:
                ts = ts // 1000
            return datetime.utcfromtimestamp(ts).date()
        except Exception:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d", "%d/%m/%y"):
        try:
            return datetime.strptime(s[:10] if "-" in s and len(s) > 10 and s[4] == "-" else s, fmt).date()
        except ValueError:
            pass
    return date.today()


@router.post("/razorpay/parse")
@router.post("/import/parse")
async def parse_razorpay_invoice_file(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    current_user = ctx.user
    tenant = ctx.tenant
    """
    Parses a Razorpay-generated Tax Invoice (PDF/Image) or a Razorpay Invoices CSV/JSON export.
    Extracts Razorpay Invoice ID (inv_...), Payment ID (pay_...), Invoice/Receipt #, Issue Date,
    Customer Name, Customer GSTIN, Place of Supply, Line Items, Tax Breakdown, and Paid Status.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    fname = (file.filename or "razorpay_invoice.pdf").lower()
    operating_state = tenant.state_code or "29"
    parsed_invoices = []

    # 1. CSV Export from Razorpay Dashboard
    if fname.endswith(".csv"):
        text = file_bytes.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        for idx, row in enumerate(reader):
            norm = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
            rzp_id = norm.get("id") or norm.get("invoice_id") or norm.get("razorpay_invoice_id") or ""
            inv_num = (
                norm.get("receipt")
                or norm.get("invoice_number")
                or norm.get("invoice_no")
                or rzp_id
                or f"RZP-INV-{idx + 1:03d}"
            )
            pay_id = norm.get("payment_id") or norm.get("razorpay_payment_id") or ""
            cust_name = (
                norm.get("customer_name")
                or norm.get("customer_details.name")
                or norm.get("billing_name")
                or norm.get("customer")
                or "Razorpay Customer"
            )
            cust_gstin = (
                norm.get("customer_gstin")
                or norm.get("customer_details.gstin")
                or norm.get("gstin")
                or ""
            ).upper()
            cust_email = norm.get("customer_email") or norm.get("customer_details.email") or norm.get("email") or ""
            cust_phone = norm.get("customer_contact") or norm.get("customer_details.contact") or norm.get("phone") or ""

            pos = norm.get("place_of_supply") or norm.get("state_code") or (cust_gstin[:2] if len(cust_gstin) >= 2 and cust_gstin[:2].isdigit() else operating_state)
            issue_dt = _parse_razorpay_date(norm.get("issued_at") or norm.get("date") or norm.get("created_at") or norm.get("issue_date"))

            raw_total = Decimal(str((norm.get("amount") or norm.get("grand_total") or norm.get("total") or "0").replace(",", "") or "0"))
            raw_tax = Decimal(str((norm.get("tax_amount") or norm.get("gst_amount") or "0").replace(",", "") or "0"))
            if raw_total > raw_tax and raw_tax > Decimal("0"):
                taxable_val = raw_total - raw_tax
                gst_rate = round((raw_tax / taxable_val) * Decimal("100"), 2) if taxable_val > 0 else Decimal("18.00")
                if abs(gst_rate - Decimal("18")) < Decimal("1.5"):
                    gst_rate = Decimal("18.00")
            else:
                taxable_val = raw_total
                gst_rate = Decimal("0.00")

            status_raw = (norm.get("status") or "paid").lower()
            pay_status = "paid" if status_raw in ("paid", "captured", "settled") or bool(pay_id) else "sent"
            desc = norm.get("description") or norm.get("item_description") or f"Razorpay Invoice {inv_num}"

            dup_q = await db.execute(select(Invoice).where(Invoice.tenant_id == tenant.id, Invoice.invoice_number == inv_num))
            is_dup = dup_q.scalars().first() is not None

            parsed_invoices.append({
                "invoice_number": inv_num,
                "razorpay_invoice_id": rzp_id,
                "razorpay_payment_id": pay_id,
                "issue_date": str(issue_dt),
                "customer_name": cust_name,
                "customer_gstin": cust_gstin or None,
                "customer_email": cust_email or None,
                "customer_phone": cust_phone or None,
                "place_of_supply": pos,
                "payment_status": pay_status,
                "is_duplicate": is_dup,
                "items": [
                    {
                        "item_description": desc,
                        "hsn_sac_code": norm.get("hsn_sac") or "998314",
                        "quantity": 1,
                        "unit_price": float(taxable_val),
                        "gst_rate_percent": float(gst_rate),
                    }
                ]
            })
        return {
            "success": True,
            "source_format": "csv",
            "invoices": parsed_invoices,
            **(parsed_invoices[0] if parsed_invoices else {})
        }

    # 2. JSON Export from Razorpay API / Dashboard
    if fname.endswith(".json"):
        data = json.loads(file_bytes.decode("utf-8", errors="ignore"))
        raw_list = data.get("items") if isinstance(data, dict) and "items" in data else (data if isinstance(data, list) else [data])
        for idx, item in enumerate(raw_list):
            if not isinstance(item, dict):
                continue
            rzp_id = item.get("id") or ""
            inv_num = item.get("invoice_number") or item.get("receipt") or rzp_id or f"RZP-INV-{idx + 1:03d}"
            pay_id = item.get("payment_id") or ""
            cust = item.get("customer_details") or {}
            cust_name = cust.get("name") or item.get("customer_name") or "Razorpay Customer"
            cust_gstin = (cust.get("gstin") or item.get("customer_gstin") or "").upper()
            cust_email = cust.get("email") or item.get("customer_email") or ""
            cust_phone = cust.get("contact") or item.get("customer_phone") or ""
            pos = item.get("place_of_supply") or (cust_gstin[:2] if len(cust_gstin) >= 2 and cust_gstin[:2].isdigit() else operating_state)
            issue_dt = _parse_razorpay_date(item.get("issued_at") or item.get("date") or item.get("created_at"))

            # Razorpay JSON amounts are in paise if integer and 'entity' == 'invoice'
            is_paise = item.get("entity") == "invoice" or (isinstance(item.get("amount"), int) and item.get("amount", 0) >= 10000)
            divisor = Decimal("100") if is_paise else Decimal("1")
            raw_amt = round(Decimal(str(item.get("amount") or 0)) / divisor, 2)
            tax_val = round(Decimal(str(item.get("tax_amount") or 0)) / divisor, 2)
            if item.get("taxable_amount") is not None:
                taxable_val = round(Decimal(str(item.get("taxable_amount") or 0)) / divisor, 2)
            elif tax_val > 0 and raw_amt > tax_val:
                taxable_val = raw_amt - tax_val
            else:
                taxable_val = raw_amt

            gst_rate_val = float(round((tax_val / taxable_val) * Decimal("100"), 2)) if (tax_val > 0 and taxable_val > 0) else 0.0
            if abs(gst_rate_val - 18.0) < 1.5 and tax_val > 0:
                gst_rate_val = 18.0

            status_raw = str(item.get("status") or "paid").lower()
            pay_status = "paid" if status_raw in ("paid", "captured", "settled") or bool(pay_id) else "sent"

            dup_q = await db.execute(select(Invoice).where(Invoice.tenant_id == tenant.id, Invoice.invoice_number == inv_num))
            is_dup = dup_q.scalars().first() is not None

            parsed_invoices.append({
                "invoice_number": inv_num,
                "razorpay_invoice_id": rzp_id,
                "razorpay_payment_id": pay_id,
                "issue_date": str(issue_dt),
                "customer_name": cust_name,
                "customer_gstin": cust_gstin or None,
                "customer_email": cust_email or None,
                "customer_phone": cust_phone or None,
                "place_of_supply": str(pos),
                "payment_status": pay_status,
                "is_duplicate": is_dup,
                "items": [
                    {
                        "item_description": item.get("description") or f"Razorpay Invoice {inv_num}",
                        "hsn_sac_code": "998314",
                        "quantity": 1,
                        "unit_price": float(taxable_val),
                        "gst_rate_percent": gst_rate_val,
                    }
                ]
            })
        return {
            "success": True,
            "source_format": "json",
            "invoices": parsed_invoices,
            **(parsed_invoices[0] if parsed_invoices else {})
        }

    # 3. PDF / Image Razorpay Invoice
    closed_fys = (tenant.statutory_profile or {}).get("closed_fiscal_years", {})
    parsed = BillInvoiceParser.parse_customer_invoice(
        file_bytes=file_bytes,
        filename=file.filename or "razorpay_invoice.pdf",
        password=password,
        company_gstin=tenant.gstin,
        closed_fiscal_years=closed_fys
    )
    if parsed.get("needs_password"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "needs_password": True,
                "message": parsed.get("message", "This Razorpay invoice PDF is encrypted. Please provide the password.")
            }
        )

    raw_text = parsed.get("raw_text") or ""
    rzp_inv_match = re.search(r'\b(inv_[A-Za-z0-9]{8,20})\b', raw_text)
    rzp_pay_match = re.search(r'\b(pay_[A-Za-z0-9]{8,20})\b', raw_text)
    rzp_inv_id = rzp_inv_match.group(1) if rzp_inv_match else None
    rzp_pay_id = rzp_pay_match.group(1) if rzp_pay_match else None

    inv_num = parsed.get("invoice_number") or rzp_inv_id or f"RZP-{uuid.uuid4().hex[:6].upper()}"
    is_paid = bool(
        rzp_pay_id
        or re.search(r'\b(?:STATUS\s*[:\-]?\s*PAID|AMOUNT\s*PAID|PAID\s*VIA\s*RAZORPAY)\b', raw_text, re.I)
    )
    pay_status = "paid" if is_paid else "sent"

    # Save original uploaded invoice file to MinIO so Auditor Dossier exports the exact original invoice
    from app.core.s3 import storage_manager
    raw_fname = file.filename or "razorpay_invoice.pdf"
    safe_fname = "".join(c for c in raw_fname if c.isalnum() or c in (" ", "_", "-", ".")).strip() or "razorpay_invoice.pdf"
    s3_key = f"{tenant.id}/invoices/{uuid.uuid4().hex[:8]}_{safe_fname}"
    try:
        storage_manager.save_document(
            bucket_name=getattr(settings, "BUCKET_INVOICES", settings.BUCKET_RECEIPTS),
            object_name=s3_key,
            file_bytes=file_bytes,
            content_type=file.content_type or "application/pdf"
        )
    except Exception:
        pass

    dup_q = await db.execute(select(Invoice).where(Invoice.tenant_id == tenant.id, Invoice.invoice_number == inv_num))
    existing_inv_obj = dup_q.scalars().first()
    is_dup = existing_inv_obj is not None
    if existing_inv_obj:
        existing_inv_obj.pdf_s3_key = s3_key
        await db.commit()

    extracted_tax_sum = (
        float(parsed.get("cgst_amount") or 0)
        + float(parsed.get("sgst_amount") or 0)
        + float(parsed.get("igst_amount") or 0)
    )
    raw_gst_rate = parsed.get("gst_rate") if parsed.get("gst_rate") is not None else parsed.get("inferred_gst_rate")
    detected_gst_rate = float(raw_gst_rate) if (raw_gst_rate is not None and extracted_tax_sum > 0) else 0.0
    unit_price_val = float(parsed.get("taxable_amount") or parsed.get("total_amount") or 0)

    single_entry = {
        "invoice_number": inv_num,
        "razorpay_invoice_id": rzp_inv_id,
        "razorpay_payment_id": rzp_pay_id,
        "issue_date": str(parsed.get("issue_date") or parsed.get("bill_date") or date.today()),
        "customer_name": parsed.get("customer_name") or parsed.get("supplier_name") or "Razorpay Customer",
        "customer_gstin": parsed.get("customer_gstin"),
        "place_of_supply": parsed.get("place_of_supply") or operating_state,
        "payment_status": pay_status,
        "pdf_s3_key": s3_key,
        "is_duplicate": is_dup,
        "subtotal": unit_price_val,
        "cgst_amount": float(parsed.get("cgst_amount") or 0),
        "sgst_amount": float(parsed.get("sgst_amount") or 0),
        "igst_amount": float(parsed.get("igst_amount") or 0),
        "grand_total": float(parsed.get("total_amount") or unit_price_val),
        "items": parsed.get("items") or [
            {
                "item_description": f"Razorpay Invoice {inv_num}",
                "hsn_sac_code": "998314",
                "quantity": 1,
                "unit_price": unit_price_val,
                "gst_rate_percent": detected_gst_rate,
            }
        ]
    }

    return {
        "success": True,
        "source_format": "pdf",
        "pdf_s3_key": s3_key,
        "invoices": [single_entry],
        **single_entry
    }


@router.post("/razorpay/import")
@router.post("/import")
async def import_razorpay_invoices(
    payload: RazorpayBatchImportRequest,
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    current_user = ctx.user
    tenant = ctx.tenant
    """
    Imports one or more Razorpay invoices into b00k5 and synchronizes them with:
    1. Contacts (auto-creates or links the Customer Contact)
    2. Dynamic Indian Fiscal Year (FY / AY) based on invoice issue_date
    3. Invoices & InvoiceItems table
    4. General Ledger Double-Entry Journal:
       - Posts Tax Invoice Journal (DR 1020 Trade Receivables, CR 3010 Operating Revenue, CR 2050/2051/2052 Output GST)
       - If payment_status == 'paid', also posts Razorpay Settlement Journal (DR 1010 Bank + DR 4030 Gateway Fee, CR 1020 Trade Receivables)
    """
    if not payload.invoices:
        raise HTTPException(status_code=400, detail="No Razorpay invoices provided for import.")

    operating_state = (tenant.state_code or "29").strip()
    imported = []
    skipped = []

    for inv_in in payload.invoices:
        inv_num = inv_in.invoice_number.strip()
        if not inv_num:
            continue

        # 1. Check for duplicate invoice number
        existing_q = await db.execute(
            select(Invoice).where(Invoice.tenant_id == tenant.id, Invoice.invoice_number == inv_num)
        )
        existing_inv = existing_q.scalars().first()
        if existing_inv:
            if inv_in.pdf_s3_key:
                existing_inv.pdf_s3_key = inv_in.pdf_s3_key
            skipped.append({
                "invoice_number": inv_num,
                "reason": f"Invoice '{inv_num}' already exists in your ledger.",
                "invoice_id": str(existing_inv.id)
            })
            continue

        # 2. Find or create Customer Contact
        cust_name = (inv_in.customer_name or "Razorpay Customer").strip()
        cust_gstin = inv_in.customer_gstin.strip().upper() if inv_in.customer_gstin else None
        pos = (inv_in.place_of_supply or (cust_gstin[:2] if cust_gstin and len(cust_gstin) >= 2 and cust_gstin[:2].isdigit() else operating_state)).strip()

        contact = None
        if cust_gstin:
            c_res = await db.execute(
                select(Contact).where(Contact.tenant_id == tenant.id, Contact.gstin == cust_gstin)
            )
            contact = c_res.scalars().first()
        if not contact:
            c_res = await db.execute(
                select(Contact).where(Contact.tenant_id == tenant.id, Contact.name == cust_name)
            )
            contact = c_res.scalars().first()
        if not contact:
            contact = Contact(
                tenant_id=tenant.id,
                name=cust_name,
                is_customer=True,
                is_vendor=False,
                gstin=cust_gstin,
                state_code=pos[:2] if len(pos) >= 2 else "29",
                email=inv_in.customer_email,
                phone=inv_in.customer_phone,
                billing_address="Imported via Razorpay Invoice Sync"
            )
            db.add(contact)
            await db.flush()

        # 3. Calculate GST breakdown across line items
        is_interstate = (operating_state != pos)
        subtotal = Decimal("0.00")
        cgst_total = Decimal("0.00")
        sgst_total = Decimal("0.00")
        igst_total = Decimal("0.00")
        grand_total = Decimal("0.00")
        calculated_items = []

        for item_in in inv_in.items:
            taxable_val = round(Decimal(str(item_in.quantity)) * Decimal(str(item_in.unit_price)), 2)
            calc = calculate_tax_breakdown(
                operating_state=operating_state,
                place_of_supply=pos,
                taxable_value=taxable_val,
                gst_rate_percent=Decimal(str(item_in.gst_rate_percent))
            )
            item_obj = InvoiceItem(
                item_description=item_in.item_description,
                hsn_sac_code=item_in.hsn_sac_code or "998314",
                quantity=item_in.quantity,
                unit_price=item_in.unit_price,
                taxable_value=taxable_val,
                gst_rate_percent=item_in.gst_rate_percent,
                cgst_amount=calc["cgst_amount"],
                sgst_amount=calc["sgst_amount"],
                igst_amount=calc["igst_amount"],
                total_amount=calc["total_amount"]
            )
            calculated_items.append(item_obj)
            subtotal += taxable_val
            cgst_total += calc["cgst_amount"]
            sgst_total += calc["sgst_amount"]
            igst_total += calc["igst_amount"]
            grand_total += calc["total_amount"]

        # 4. Resolve Dynamic Fiscal Year and create Invoice
        fy_record = await get_or_create_fiscal_year(db, tenant.id, inv_in.issue_date)
        is_paid = (inv_in.payment_status or "paid").lower() == "paid"

        invoice = Invoice(
            tenant_id=tenant.id,
            contact_id=contact.id,
            invoice_number=inv_num,
            type="tax_invoice",
            issue_date=inv_in.issue_date,
            due_date=inv_in.due_date or inv_in.issue_date,
            place_of_supply=pos[:2] if len(pos) >= 2 else "29",
            is_interstate=is_interstate,
            subtotal=subtotal,
            cgst_total=cgst_total,
            sgst_total=sgst_total,
            igst_total=igst_total,
            grand_total=grand_total,
            status="paid" if is_paid else "sent",
            pdf_s3_key=inv_in.pdf_s3_key,
            fiscal_year_id=fy_record.id,
            items=calculated_items
        )
        db.add(invoice)
        await db.flush()

        # 5. Post Double-Entry Tax Invoice Journal Entry (DR 1020 AR, CR 3010 Revenue, CR 2050/2051/2052 GST)
        inv_je = await LedgerService.post_invoice_journal(db, invoice, current_user.id)

        # 6. If Paid via Razorpay, post Settlement Journal Entry (DR 1010 Bank + DR 4030 Fee, CR 1020 AR)
        settle_je = None
        if is_paid:
            settle_je = await LedgerService.post_razorpay_settlement_journal(
                db,
                invoice=invoice,
                razorpay_payment_id=inv_in.razorpay_payment_id,
                gateway_fee=inv_in.gateway_fee or Decimal("0.00"),
                created_by_user_id=current_user.id
            )

        imported.append({
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "customer_name": contact.name,
            "issue_date": str(invoice.issue_date),
            "assigned_fy": fy_record.label,
            "subtotal": float(invoice.subtotal),
            "tax_total": float(invoice.cgst_total + invoice.sgst_total + invoice.igst_total),
            "grand_total": float(invoice.grand_total),
            "status": invoice.status,
            "invoice_journal_number": inv_je.entry_number,
            "settlement_journal_number": settle_je.entry_number if settle_je else None
        })

    # Auto-reconcile any open bank statements so newly imported invoices match existing statement lines
    try:
        from app.models.bank import BankStatement
        from app.services.reconciliation_engine import ReconciliationEngine
        stmts = (await db.execute(
            select(BankStatement).where(BankStatement.tenant_id == tenant.id)
        )).scalars().all()
        for s in stmts:
            await ReconciliationEngine.reconcile_statement(
                session=db, tenant_id=tenant.id, statement_id=s.id, user_id=current_user.id
            )
    except Exception:
        pass

    await db.commit()
    return {
        "success": True,
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped
    }


@router.post("/{invoice_id}/pdf")
async def upload_invoice_pdf(
    invoice_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    current_user = ctx.user
    tenant = ctx.tenant
    """
    Directly attaches/updates the original tax invoice PDF document for a sales invoice.
    Saves binary bytes directly to MinIO and updates the invoice record.
    """
    stmt = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant.id)
    inv = (await db.execute(stmt)).scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice record not found")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file payload")

    from app.services.bank_parser import validate_uploaded_document_safety
    safety = validate_uploaded_document_safety(file.filename or "invoice.pdf", file_bytes, file.content_type)
    if not safety.get("is_safe"):
        raise HTTPException(status_code=400, detail=f"File rejected by security scanner: {safety.get('reason')}")

    safe_fname = safety.get("sanitized_filename") or (file.filename or "invoice.pdf")
    s3_key = f"{tenant.id}/invoices/{uuid.uuid4().hex[:8]}_{safe_fname}"

    from app.core.s3 import storage_manager
    storage_manager.save_document(
        bucket_name=getattr(settings, "BUCKET_INVOICES", settings.BUCKET_RECEIPTS),
        object_name=s3_key,
        file_bytes=file_bytes,
        content_type=file.content_type or "application/pdf"
    )

    inv.pdf_s3_key = s3_key
    await db.commit()
    await db.refresh(inv)

    return {
        "success": True,
        "message": f"Original invoice PDF '{safe_fname}' successfully attached to invoice {inv.invoice_number}",
        "pdf_s3_key": s3_key,
        "invoice_id": str(inv.id)
    }


@router.get("/{invoice_id}/download")
@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    tenant = ctx.tenant
    """
    Downloads or streams the original or assembled Razorpay-style GST Tax Invoice PDF.
    If not yet generated or attached, creates the compliant PDF on the fly.
    """
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.contact), selectinload(Invoice.items))
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant.id)
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice record not found")

    from app.core.s3 import storage_manager
    content = None
    if inv.pdf_s3_key:
        try:
            content = storage_manager.get_document_bytes(
                getattr(settings, "BUCKET_INVOICES", settings.BUCKET_RECEIPTS),
                inv.pdf_s3_key
            )
            # If valid PDF content was retrieved, keep it intact without overwriting authentic records
            if content and not (b"%PDF" in content[:1024] or b"%%EOF" in content[-2048:]):
                content = None
        except Exception:
            content = None

    if not content:
        primary_ac = (tenant.statutory_profile or {}).get("primary_bank_account") or {}
        pos = inv.place_of_supply or tenant.state_code or "29"
        contact_name = inv.contact.name if inv.contact else "Valued Customer"
        contact_gstin = inv.contact.gstin if inv.contact else ""
        contact_addr = inv.contact.billing_address if inv.contact else ""
        contact_email = getattr(inv.contact, "email", "") or ""
        contact_phone = getattr(inv.contact, "phone", "") or ""

        # Fetch tenant seller email/phone
        seller_email = (tenant.statutory_profile or {}).get("email") or ""
        seller_phone = (tenant.statutory_profile or {}).get("phone") or ""

        content = PDFService.generate_simple_invoice_pdf({
            "invoice_number": inv.invoice_number,
            "seller_name": tenant.legal_name,
            "seller_cin": tenant.cin,
            "seller_gstin": tenant.gstin,
            "seller_pan": tenant.pan,
            "seller_address": tenant.registered_office,
            "seller_email": seller_email,
            "seller_phone": seller_phone,
            "logo_url": tenant.logo_url or (tenant.statutory_profile or {}).get("logo_url"),
            "logo_s3_key": tenant.logo_s3_key or (tenant.statutory_profile or {}).get("logo_s3_key"),
            "issue_date": str(inv.issue_date),
            "due_date": str(inv.due_date),
            "place_of_supply": pos,
            "customer_name": contact_name,
            "customer_gstin": contact_gstin,
            "customer_address": contact_addr,
            "customer_email": contact_email,
            "customer_phone": contact_phone,
            "status": inv.status,
            "is_paid": inv.status in ("paid", "settled"),
            "subtotal": float(inv.subtotal),
            "cgst_total": float(inv.cgst_total or 0),
            "sgst_total": float(inv.sgst_total or 0),
            "igst_total": float(inv.igst_total or 0),
            "grand_total": float(inv.grand_total),
            "items": [
                {
                    "description": getattr(it, "item_description", None) or getattr(it, "description", "Software Consulting Services"),
                    "hsn_sac_code": getattr(it, "hsn_sac_code", "-"),
                    "quantity": float(getattr(it, "quantity", 1)),
                    "unit_price": float(getattr(it, "unit_price", 0)),
                    "taxable_amount": float(getattr(it, "taxable_value", None) or getattr(it, "taxable_amount", 0))
                }
                for it in (inv.items or [])
            ],
            "bank_details": primary_ac
        })

        # Cache generated PDF in MinIO
        s3_key = f"{tenant.id}/invoices/{inv.invoice_number}.pdf"
        try:
            storage_manager.save_document(
                bucket_name=getattr(settings, "BUCKET_INVOICES", settings.BUCKET_RECEIPTS),
                object_name=s3_key,
                file_bytes=content,
                content_type="application/pdf"
            )
            inv.pdf_s3_key = s3_key
            await db.commit()
        except Exception:
            pass

    safe_num = str(inv.invoice_number).replace("/", "_")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="INV-{safe_num}.pdf"'
        }
    )


@router.post("/{invoice_id}/strike-off")
async def strike_off_invoice(
    invoice_id: uuid.UUID,
    reason: Optional[str] = Form(None),
    ctx: IAMContext = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    current_user = ctx.user
    tenant = ctx.tenant
    """
    Cancels / strikes off an invoice.
    Reverses the corresponding Double-Entry journal voucher in General Ledger:
    - Debits Revenue 3010 (reversing sales)
    - Credits Trade Receivables 1020 (reversing debtor balance)
    Marks invoice status as 'cancelled'.
    """
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.contact), selectinload(Invoice.items))
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant.id)
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice record not found")

    if inv.status == "cancelled":
        return {
            "success": True,
            "message": f"Invoice {inv.invoice_number} is already struck off / cancelled.",
            "status": "cancelled"
        }

    from datetime import date as dt_date
    reversal_jv_number = f"JV-INV-REVERSAL-{inv.invoice_number}-{uuid.uuid4().hex[:6].upper()}"
    rev_entry = JournalEntry(
        tenant_id=tenant.id,
        entry_number=reversal_jv_number,
        entry_date=inv.issue_date,  # Match original invoice issue date so period balance sheet reflects strike-off
        reference_type="invoice_strike_off",
        reference_id=inv.id,
        narration=f"Strike-off / Cancellation of Invoice {inv.invoice_number}: {reason or 'Voided by Administrator'}",
        status="posted",
        is_posted=True,
        created_by=current_user.id
    )
    db.add(rev_entry)
    await db.flush()

    ar_acc = await LedgerService.get_account_by_code(db, tenant.id, "1020")
    rev_acc = await LedgerService.get_account_by_code(db, tenant.id, "3010")
    cgst_acc = await LedgerService.get_account_by_code(db, tenant.id, "2050")
    sgst_acc = await LedgerService.get_account_by_code(db, tenant.id, "2051")
    igst_acc = await LedgerService.get_account_by_code(db, tenant.id, "2052")

    if ar_acc and rev_acc:
        rev_lines = [
            JournalLine(journal_entry_id=rev_entry.id, tenant_id=tenant.id, account_id=rev_acc.id, debit_amount=inv.subtotal, credit_amount=Decimal("0.00"), description=f"Reverse sales: Invoice {inv.invoice_number}")
        ]
        if inv.cgst_total and inv.cgst_total > Decimal("0.00") and cgst_acc:
            rev_lines.append(JournalLine(journal_entry_id=rev_entry.id, tenant_id=tenant.id, account_id=cgst_acc.id, debit_amount=inv.cgst_total, credit_amount=Decimal("0.00"), description=f"Reverse Output CGST: Invoice {inv.invoice_number}"))
        if inv.sgst_total and inv.sgst_total > Decimal("0.00") and sgst_acc:
            rev_lines.append(JournalLine(journal_entry_id=rev_entry.id, tenant_id=tenant.id, account_id=sgst_acc.id, debit_amount=inv.sgst_total, credit_amount=Decimal("0.00"), description=f"Reverse Output SGST: Invoice {inv.invoice_number}"))
        if inv.igst_total and inv.igst_total > Decimal("0.00") and igst_acc:
            rev_lines.append(JournalLine(journal_entry_id=rev_entry.id, tenant_id=tenant.id, account_id=igst_acc.id, debit_amount=inv.igst_total, credit_amount=Decimal("0.00"), description=f"Reverse Output IGST: Invoice {inv.invoice_number}"))
        rev_lines.append(
            JournalLine(journal_entry_id=rev_entry.id, tenant_id=tenant.id, account_id=ar_acc.id, debit_amount=Decimal("0.00"), credit_amount=inv.grand_total, description=f"Reverse receivable: Invoice {inv.invoice_number}")
        )
        db.add_all(rev_lines)

    inv.status = "cancelled"
    await db.commit()
    await db.refresh(inv)

    return {
        "success": True,
        "message": f"Invoice {inv.invoice_number} successfully struck off and reversed in ledger.",
        "invoice_id": str(inv.id),
        "status": "cancelled",
        "reversal_journal": reversal_jv_number
    }


@router.post("/{invoice_id}/generate-irn", response_model=EInvoiceResponse)
async def generate_invoice_irn(
    invoice_id: uuid.UUID,
    payload: Optional[EInvoiceGenerateRequest] = None,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates standard Indian E-Invoice IRN and B2B Signed QR code u/s 48(4) of CGST Rules, 2017.
    """
    try:
        res = await EInvoiceService.generate_einvoice(
            session=db,
            tenant_id=ctx.tenant.id,
            invoice_id=invoice_id,
            override_existing=payload.override_existing if payload else False
        )
        await db.commit()
        return EInvoiceResponse(**res)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"E-Invoice error: {str(e)}")


@router.get("/{invoice_id}/einvoice", response_model=EInvoiceResponse)
async def get_invoice_einvoice(
    invoice_id: uuid.UUID,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the generated E-Invoice IRN, Acknowledgement Number, and Signed QR Payload.
    """
    query = (
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == ctx.tenant.id)
        .options(selectinload(Invoice.contact), selectinload(Invoice.tenant))
    )
    inv = (await db.execute(query)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not inv.irn:
        raise HTTPException(status_code=400, detail="E-Invoice has not been generated for this invoice. Call /generate-irn first.")

    return EInvoiceResponse(
        invoice_id=str(inv.id),
        invoice_number=inv.invoice_number,
        irn=inv.irn,
        ack_no=inv.ack_no or "",
        ack_date=inv.ack_date or inv.created_at,
        signed_qr_code=inv.signed_qr_code or "",
        irn_status=inv.irn_status or "GENERATED",
        supplier_gstin=inv.tenant.gstin or "",
        recipient_gstin=inv.contact.gstin or "URP",
        document_type="INV",
        fiscal_year="2026-27",
        grand_total=inv.grand_total,
        einvoice_payload=inv.einvoice_payload or {}
    )


@router.get("/export/gstr-1")
async def export_gstr1_json(
    year: int = Query(..., description="Calendar year, e.g. 2026"),
    month: int = Query(..., ge=1, le=12, description="Calendar month (1-12)"),
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports official GSTN GSTR-1 offline tool JSON for direct upload to gst.gov.in.
    Includes B2B, B2CL, B2CS, CDNR, EXP, HSN Table 12, and Document Issue Table 13.
    """
    try:
        payload = await GSTR1ExportService.generate_gstr1_json(
            session=db,
            tenant_id=ctx.tenant.id,
            year=year,
            month=month
        )
        fp = f"{month:02d}{year}"
        gstin = ctx.tenant.gstin or "29AABCV1234F1Z5"
        filename = f"GSTR1_{gstin}_{fp}.json"
        return JSONResponse(
            content=payload,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to generate GSTR-1 JSON: {str(e)}")



