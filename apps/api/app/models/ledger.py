import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Boolean, DateTime, Date, Numeric, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class ChartOfAccounts(Base):
    __tablename__ = "chart_of_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(
        SQLEnum('asset', 'liability', 'equity', 'revenue', 'expense', name="account_type_enum"),
        nullable=False
    )
    sub_type = Column(String(64), nullable=True)
    normal_balance = Column(
        SQLEnum('debit', 'credit', name="balance_nature_enum"),
        nullable=False
    )
    is_reconciliation = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=True)
    is_leaf = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="accounts")
    parent = relationship("ChartOfAccounts", remote_side=[id], backref="children")
    journal_lines = relationship("JournalLine", back_populates="account")

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    entry_number = Column(String(64), nullable=False)
    entry_date = Column(Date, default=date.today, nullable=False)
    reference_type = Column(String(64), nullable=True)
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    narration = Column(Text, nullable=False)
    status = Column(String(20), default="posted", nullable=False) # 'draft', 'posted', 'voided'
    is_posted = Column(Boolean, default=True)
    posted_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    lines = relationship("JournalLine", back_populates="journal_entry", cascade="all, delete-orphan")

class JournalLine(Base):
    __tablename__ = "journal_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=False)
    debit_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    credit_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("ChartOfAccounts", back_populates="journal_lines")

class FiscalYear(Base):
    __tablename__ = "fiscal_years"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(32), nullable=False) # e.g. '2025-2026'
    assessment_year = Column(String(32), nullable=False) # e.g. '2026-2027'
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")

