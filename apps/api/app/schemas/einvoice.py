from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class EInvoiceItemDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_index: int = 1
    description: str
    hsn_code: str
    quantity: Decimal
    unit_price: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    cgst_amount: Decimal = Decimal("0.00")
    sgst_amount: Decimal = Decimal("0.00")
    igst_amount: Decimal = Decimal("0.00")
    total_amount: Decimal

class EInvoiceGenerateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: str
    override_existing: bool = False

class EInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: str
    invoice_number: str
    irn: str
    ack_no: str
    ack_date: datetime
    signed_qr_code: str
    irn_status: str
    supplier_gstin: str
    recipient_gstin: str
    document_type: str = "INV"
    fiscal_year: str
    grand_total: Decimal
    einvoice_payload: Dict[str, Any]
    qr_code_svg: Optional[str] = None

