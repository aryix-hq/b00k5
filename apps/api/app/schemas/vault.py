from typing import Optional, Dict, Any
from datetime import date, datetime
import uuid
from pydantic import BaseModel

class DocumentVaultResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    category: str
    document_name: str
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    is_confidential: bool
    metadata_json: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentUploadMetadata(BaseModel):
    category: str # corporate_legal, tax_registration, operational_license, equity_governance, statutory_filing
    document_name: str
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_confidential: bool = False
    metadata_json: Optional[Dict[str, Any]] = None
