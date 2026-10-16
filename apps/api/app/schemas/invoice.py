from typing import Optional, List
from datetime import date, datetime
import uuid
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

class ContactBase(BaseModel):
    name: str
    is_customer: bool = True
    is_vendor: bool = False
    gstin: Optional[str] = None
    pan: Optional[str] = None
    state_code: str
    billing_address: str
    shipping_address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactResponse(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime

class InvoiceItemBase(BaseModel):
    item_description: str
    hsn_sac_code: str
    quantity: Decimal = Field(default=Decimal("1.000"))
    unit_price: Decimal
    gst_rate_percent: Decimal = Field(default=Decimal("18.00")) # 0, 5, 12, 18, 28

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemResponse(InvoiceItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    total_amount: Decimal

class InvoiceCreate(BaseModel):
    contact_id: uuid.UUID
    invoice_number: str
    type: str = "tax_invoice" # tax_invoice, proforma, credit_note, debit_note
    issue_date: date = Field(default_factory=date.today)
    due_date: date
    place_of_supply: str # 2-digit Indian State code
    pdf_s3_key: Optional[str] = None
    items: List[InvoiceItemCreate]

class InvoiceUpdate(BaseModel):
    contact_id: Optional[uuid.UUID] = None
    invoice_number: Optional[str] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    place_of_supply: Optional[str] = None
    items: Optional[List[InvoiceItemCreate]] = None
    status: Optional[str] = None

class InvoiceResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    contact_id: uuid.UUID
    contact: Optional[ContactResponse] = None
    invoice_number: str
    type: str
    issue_date: date
    due_date: date
    place_of_supply: str
    is_interstate: bool
    subtotal: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    grand_total: Decimal
    status: str
    pdf_s3_key: Optional[str] = None
    items: List[InvoiceItemResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
