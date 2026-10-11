import uuid
from datetime import datetime
from typing import Optional
try:
    from pydantic import BaseModel, Field
    HAVE_PYDANTIC = True
except ImportError:
    HAVE_PYDANTIC = False
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def dict(self):
            return self.__dict__
    def Field(*args, **kwargs):
        return None

class CloudSyncCreate(BaseModel):
    file_name: str
    category: str
    fiscal_year: str
    s3_bucket: str
    s3_key: str
    file_size_bytes: int
    sha256_checksum: str
    gdrive_folder_path: str

class CloudSyncResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    file_name: str
    category: str
    fiscal_year: str
    s3_bucket: str
    s3_key: str
    file_size_bytes: int
    sha256_checksum: str
    gdrive_file_id: Optional[str] = None
    gdrive_folder_path: str
    gdrive_md5_checksum: Optional[str] = None
    status: str
    retry_count: int = 0
    max_retries: int = 5
    last_error: Optional[str] = None
    synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class StorageUploadResponse(BaseModel):
    sync_id: uuid.UUID
    file_name: str
    s3_bucket: str
    s3_key: str
    file_size_bytes: int
    sha256_checksum: str
    fiscal_year: str
    gdrive_target_path: str
    presigned_url: Optional[str] = None
    status: str = "queued"

class PresignedUrlResponse(BaseModel):
    file_name: str
    s3_bucket: str
    s3_key: str
    presigned_url: str
    expires_in_seconds: int = 3600
