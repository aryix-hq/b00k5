import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, DateTime, Date, Numeric, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class FixedAsset(Base):
    __tablename__ = "fixed_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    asset_code = Column(String(50), nullable=False)
    asset_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)  # 'COMPUTERS_END_USER', 'SERVERS_NETWORK', etc.
    purchase_date = Column(Date, nullable=False)
    capitalization_date = Column(Date, nullable=False)
    gross_block = Column(Numeric(15, 2), nullable=False)
    salvage_value = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    useful_life_years = Column(Numeric(5, 2), nullable=False)
    depreciation_method = Column(String(20), default="SLM", nullable=False)  # 'SLM', 'WDV'
    accumulated_depreciation = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_block = Column(Numeric(15, 2), nullable=False)
    location = Column(String(255), nullable=True)
    serial_number = Column(String(100), nullable=True)
    status = Column(String(50), default="ACTIVE", nullable=False)  # 'ACTIVE', 'DISPOSED', 'WRITTEN_OFF'
    purchase_journal_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
    purchase_journal = relationship("JournalEntry")


class FixedAssetDepreciationRun(Base):
    __tablename__ = "fixed_asset_depreciation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    run_date = Column(Date, nullable=False)
    total_depreciation_amount = Column(Numeric(15, 2), nullable=False)
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="POSTED", nullable=False)
    details = Column(JSONB, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
    journal_entry = relationship("JournalEntry")

