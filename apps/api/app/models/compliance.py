import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Numeric, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class ComplianceEvent(Base):
    __tablename__ = "compliance_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    category = Column(
        SQLEnum(
            'board_meeting_120d',
            'dir3_kyc',
            'aoc_4',
            'mgt_7',
            'inc_20a',
            'advance_tax',
            'gstr_1',
            'gstr_3b',
            'itr_filing',
            name="compliance_category_enum"
        ),
        nullable=False
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=False)
    statutory_reference = Column(String(128), nullable=True)
    fine_per_day_inr = Column(Numeric(10, 2), default=0.00)
    status = Column(
        SQLEnum('upcoming', 'due_soon', 'overdue', 'completed', 'waived', name="compliance_status_enum"),
        default='upcoming'
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document_vault.id"), nullable=True)
    metadata_json = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="compliance_events")
    document = relationship("DocumentVault")

class CorporateMeeting(Base):
    __tablename__ = "corporate_meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    meeting_type = Column(String(50), default="board_meeting", nullable=False)
    meeting_number = Column(String(50), nullable=False)
    meeting_date = Column(Date, nullable=False)
    meeting_time = Column(String(50), nullable=False)
    venue = Column(Text, nullable=False)
    directors_present = Column(JSONB, default=list, nullable=False)
    agenda_items = Column(JSONB, default=list, nullable=False)
    resolutions = Column(JSONB, default=list, nullable=False)
    signed_document_key = Column(String(255), nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")
