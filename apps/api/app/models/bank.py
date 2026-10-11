import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, DateTime, Date, Numeric, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    bank_name = Column(
        SQLEnum('HDFC', 'ICICI', 'SBI', 'AXIS', 'KOTAK', 'OTHER', name="bank_name_enum"),
        default='HDFC',
        nullable=False
    )
    account_number = Column(String(64), nullable=False)
    statement_from = Column(Date, nullable=True)
    statement_to = Column(Date, nullable=True)
    opening_balance = Column(Numeric(15, 2), default=0.00)
    closing_balance = Column(Numeric(15, 2), default=0.00)
    total_withdrawals = Column(Numeric(15, 2), default=0.00)
    total_deposits = Column(Numeric(15, 2), default=0.00)
    file_name = Column(String(255), nullable=False)
    file_sha256 = Column(String(64), nullable=True)
    s3_key = Column(Text, nullable=False)
    fiscal_year_id = Column(UUID(as_uuid=True), ForeignKey("fiscal_years.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), default="parsed") # 'uploaded', 'parsed', 'partially_reconciled', 'reconciled'
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
    uploader = relationship("User")
    fiscal_year = relationship("FiscalYear")
    lines = relationship("BankStatementLine", back_populates="statement", cascade="all, delete-orphan", order_by="BankStatementLine.line_number")

class BankStatementLine(Base):
    __tablename__ = "bank_statement_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_id = Column(UUID(as_uuid=True), ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    line_number = Column(Integer, nullable=False)
    fingerprint = Column(String(64), nullable=True)
    transaction_date = Column(Date, nullable=False)
    value_date = Column(Date, nullable=True)
    description = Column(Text, nullable=False)
    reference_number = Column(String(128), nullable=True)
    payment_channel = Column(String(32), default="OTHER") # 'UPI', 'NEFT', 'RTGS', 'IMPS', 'CHEQUE', 'CHARGES'
    counterparty_name = Column(String(255), nullable=True)
    withdrawal_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    deposit_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    running_balance = Column(Numeric(15, 2), nullable=False)
    reconciliation_tier = Column(
        SQLEnum('unreconciled', 'tier1_exact', 'tier2_heuristic', 'tier3_suspense', name="reconciliation_tier_enum"),
        default='unreconciled',
        nullable=False
    )
    reconciliation_status = Column(
        SQLEnum('pending', 'probable_match', 'reconciled', 'suspense_posted', name="reconciliation_status_enum"),
        default='pending',
        nullable=False
    )
    confidence_score = Column(Numeric(5, 2), default=0.00)
    matched_journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    matched_journal_line_id = Column(UUID(as_uuid=True), ForeignKey("journal_lines.id", ondelete="SET NULL"), nullable=True)
    suspense_journal_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    statement = relationship("BankStatement", back_populates="lines")
    matched_journal = relationship("JournalEntry", foreign_keys=[matched_journal_entry_id])
    suspense_journal = relationship("JournalEntry", foreign_keys=[suspense_journal_id])
