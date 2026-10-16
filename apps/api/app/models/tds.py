import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, DateTime, Date, Numeric, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class TDSChallan(Base):
    __tablename__ = "tds_challans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    quarter = Column(String(2), nullable=False)  # 'Q1', 'Q2', 'Q3', 'Q4'
    section = Column(String(32), nullable=False)  # '194C', '194J', '194I', '194Q'
    bsr_code = Column(String(7), nullable=False)
    challan_serial_no = Column(String(10), nullable=False)
    payment_date = Column(Date, nullable=False)
    tds_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    surcharge_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    cess_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    interest_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    fee_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    cin = Column(String(30), nullable=True)
    minor_head = Column(String(10), default="200", nullable=True)
    s3_challan_receipt_key = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
    deductions = relationship("TDSDeduction", back_populates="challan")


class TDSDeduction(Base):
    __tablename__ = "tds_deductions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    expense_id = Column(UUID(as_uuid=True), ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True)
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    deductee_name = Column(String(255), nullable=False)
    deductee_pan = Column(String(10), nullable=False)
    deductee_type = Column(String(20), default="COMPANY", nullable=False)  # 'COMPANY', 'NON_COMPANY'
    section = Column(String(32), nullable=False)  # '194C', '194J', '194I', '194Q'
    rate_percentage = Column(Numeric(5, 2), nullable=False)
    gross_amount = Column(Numeric(15, 2), nullable=False)
    tds_amount = Column(Numeric(15, 2), nullable=False)
    net_payable = Column(Numeric(15, 2), nullable=False)
    deduction_date = Column(Date, nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    quarter = Column(String(2), nullable=False)
    tds_challan_id = Column(UUID(as_uuid=True), ForeignKey("tds_challans.id", ondelete="SET NULL"), nullable=True)
    certificate_number = Column(String(50), nullable=True)
    status = Column(String(32), default="PENDING_DEPOSIT", nullable=False)  # 'PENDING_DEPOSIT', 'DEPOSITED'
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
    expense = relationship("Expense")
    journal_entry = relationship("JournalEntry")
    challan = relationship("TDSChallan", back_populates="deductions")

