from typing import List, Optional, Any, Dict
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

    # 6. Preserve original uploaded Invoice PDF if provided; only generate simple PDF for manually typed invoices
    if getattr(payload, "pdf_s3_key", None):
        invoice.pdf_s3_key = payload.pdf_s3_key
    else:
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
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items), selectinload(Invoice.contact))
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
        .options(selectinload(Invoice.items), selectinload(Invoice.contact))
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
async def parse_razorpay_invoice_file(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
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
async def import_razorpay_invoices(
    payload: RazorpayBatchImportRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
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


