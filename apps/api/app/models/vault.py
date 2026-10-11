import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Boolean, DateTime, Date, BigInteger, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class DocumentVault(Base):
    __tablename__ = "document_vault"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    category = Column(
        SQLEnum(
            'corporate_legal',
            'tax_registration',
            'operational_license',
            'equity_governance',
            'statutory_filing',
            name="document_category_enum"
        ),
        nullable=False
    )
    document_name = Column(String(255), nullable=False)
    document_number = Column(String(128), nullable=True)
    issue_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    minio_s3_key = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(64), nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    is_confidential = Column(Boolean, default=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    metadata_json = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="documents")
    uploader = relationship("User")
