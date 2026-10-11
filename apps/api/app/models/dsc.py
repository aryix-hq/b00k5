import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship
from app.core.database import Base

class DSCSignatureAudit(Base):
    __tablename__ = "dsc_signature_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(64), nullable=False) # 'board_minutes', 'invoice', 'aoc4', 'mgt7'
    document_id = Column(UUID(as_uuid=True), nullable=False)
    signer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    signer_din = Column(String(8), nullable=True)
    signer_name = Column(String(255), nullable=False)
    token_model = Column(String(128), default="HyperPKI HYP2003")
    token_serial_number = Column(String(128), nullable=True)
    certificate_issuer = Column(Text, nullable=False)
    certificate_valid_to = Column(DateTime(timezone=True), nullable=False)
    sha256_document_hash = Column(String(64), nullable=False)
    signed_cms_signature_s3_key = Column(Text, nullable=False)
    signed_pdf_s3_key = Column(Text, nullable=False)
    ip_address = Column(INET, nullable=False)
    signed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
    signer = relationship("User")
