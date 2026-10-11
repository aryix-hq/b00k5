import uuid
from datetime import datetime
from sqlalchemy import Column, String, BigInteger, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class DatabaseBackupLog(Base):
    __tablename__ = "database_backup_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    sha256_checksum = Column(String(64), nullable=False)
    encryption_algorithm = Column(String(32), default="AES-256-GCM")
    gdrive_file_id = Column(String(128), nullable=True)
    gdrive_folder_path = Column(Text, nullable=True)
    status = Column(String(32), default="completed")
    duration_seconds = Column(Numeric(6, 2), default=0.00)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
