import uuid
from datetime import datetime
try:
    from sqlalchemy import Column, String, Integer, DateTime, BigInteger, Text, ForeignKey, Enum as SQLEnum
    from sqlalchemy.dialects.postgresql import UUID
    from sqlalchemy.orm import relationship
    from app.core.database import Base
    HAVE_SQLALCHEMY = True
except ImportError:
    HAVE_SQLALCHEMY = False
    Base = object
    Column = String = Integer = DateTime = BigInteger = Text = ForeignKey = SQLEnum = UUID = relationship = lambda *a, **k: None

class CloudSyncLedger(Base):
    __tablename__ = "cloud_sync_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False) # 'statements', 'receipts', 'statutory', 'invoices'
    fiscal_year = Column(String(32), nullable=False) # e.g. 'FY_2025-2026'
    s3_bucket = Column(String(128), nullable=False)
    s3_key = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    sha256_checksum = Column(String(64), nullable=False)
    gdrive_file_id = Column(String(255), nullable=True)
    gdrive_folder_path = Column(Text, nullable=False)
    gdrive_md5_checksum = Column(String(64), nullable=True)
    status = Column(
        SQLEnum('pending', 'syncing', 'synced', 'failed', name="sync_status_enum"),
        default='pending',
        nullable=False
    )
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=5, nullable=False)
    last_error = Column(Text, nullable=True)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")
