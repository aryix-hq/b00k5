import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Boolean, DateTime, Date, Numeric, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    is_customer = Column(Boolean, default=True)
    is_vendor = Column(Boolean, default=False)
    gstin = Column(String(15), nullable=True)
    pan = Column(String(10), nullable=True)
    state_code = Column(String(2), nullable=False)
    billing_address = Column(Text, nullable=False)
    shipping_address = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    invoices = relationship("Invoice", back_populates="contact")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False)
    invoice_number = Column(String(64), nullable=False)
    type = Column(
        SQLEnum('tax_invoice', 'proforma', 'credit_note', 'debit_note', name="invoice_type_enum"),
        default='tax_invoice',
        nullable=False
    )
    issue_date = Column(Date, default=date.today, nullable=False)
    due_date = Column(Date, nullable=False)
    place_of_supply = Column(String(2), nullable=False)
    is_interstate = Column(Boolean, default=False, nullable=False)
    subtotal = Column(Numeric(15, 2), nullable=False)
    cgst_total = Column(Numeric(15, 2), default=0.00)
    sgst_total = Column(Numeric(15, 2), default=0.00)
    igst_total = Column(Numeric(15, 2), default=0.00)
    grand_total = Column(Numeric(15, 2), nullable=False)
    tds_amount = Column(Numeric(15, 2), default=0.00)
    status = Column(
        SQLEnum('draft', 'sent', 'paid', 'partially_paid', 'cancelled', name="invoice_status_enum"),
        default='draft',
        nullable=False
    )
    pdf_s3_key = Column(Text, nullable=True)
    fiscal_year_id = Column(UUID(as_uuid=True), ForeignKey("fiscal_years.id", ondelete="SET NULL"), nullable=True)
    irn = Column(String(64), nullable=True)
    ack_no = Column(String(32), nullable=True)
    ack_date = Column(DateTime(timezone=True), nullable=True)
    signed_qr_code = Column(Text, nullable=True)
    irn_status = Column(String(32), default='PENDING')
    einvoice_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="invoices")
    contact = relationship("Contact", back_populates="invoices")
    fiscal_year = relationship("FiscalYear")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    item_description = Column(Text, nullable=False)
    hsn_sac_code = Column(String(10), nullable=False)
    uqc = Column(String(10), default="OTH", nullable=True)
    quantity = Column(Numeric(12, 3), default=1.000, nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=False)
    taxable_value = Column(Numeric(15, 2), nullable=False)
    gst_rate_percent = Column(Numeric(5, 2), nullable=False)
    cgst_amount = Column(Numeric(15, 2), default=0.00)
    sgst_amount = Column(Numeric(15, 2), default=0.00)
    igst_amount = Column(Numeric(15, 2), default=0.00)
    total_amount = Column(Numeric(15, 2), nullable=False)

    invoice = relationship("Invoice", back_populates="items")
