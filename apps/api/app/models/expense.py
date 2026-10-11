import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Numeric, Text, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    merchant_name = Column(String(255), nullable=False)
    merchant_gstin = Column(String(15), nullable=True)
    expense_date = Column(Date, default=date.today, nullable=False)
    currency = Column(String(3), default="INR")
    total_amount = Column(Numeric(15, 2), nullable=False)
    cgst_amount = Column(Numeric(15, 2), default=0.00)
    sgst_amount = Column(Numeric(15, 2), default=0.00)
    igst_amount = Column(Numeric(15, 2), default=0.00)
    
    # Indian Withholding Tax (TDS)
    tds_section = Column(
        SQLEnum('none', '194C', '194J', '194I', '194Q', '194H', name="tds_section_enum"),
        default='none'
    )
    tds_rate = Column(Numeric(5, 2), default=0.00)
    tds_amount = Column(Numeric(15, 2), default=0.00)
    
    category = Column(String(64), nullable=False)
    receipt_s3_key = Column(Text, nullable=True)
    receipt_sha256 = Column(String(64), nullable=True)
    fiscal_year_id = Column(UUID(as_uuid=True), ForeignKey("fiscal_years.id", ondelete="SET NULL"), nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    status = Column(
        SQLEnum('draft', 'submitted', 'approved', 'reimbursed', 'rejected', 'struck_off', name="expense_status_enum"),
        default='draft'
    )
    paid_personally = Column(Boolean, default=False)
    director_name = Column(String(128), nullable=True)
    payment_mode = Column(String(64), default='company_bank')
    journal_entry_number = Column(String(64), nullable=True)
    has_company_gstin = Column(Boolean, default=False)
    itc_eligible = Column(Boolean, default=False)
    settlement_status = Column(String(32), default='pending')
    notes = Column(Text, nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reimbursed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="expenses")
    employee = relationship("User", foreign_keys=[employee_id])
    approver = relationship("User", foreign_keys=[approved_by])
    fiscal_year = relationship("FiscalYear")
    audit_logs = relationship("ExpenseAuditLog", back_populates="expense", cascade="all, delete-orphan")

class ExpenseAuditLog(Base):
    __tablename__ = "expense_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    expense_id = Column(UUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(32), nullable=False) # CREATED, UPDATED, VOIDED, SETTLED
    field_changes = Column(JSONB, nullable=False, default=dict)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    expense = relationship("Expense", back_populates="audit_logs")
    user = relationship("User", foreign_keys=[changed_by])
