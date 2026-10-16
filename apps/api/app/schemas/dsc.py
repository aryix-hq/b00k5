from typing import Optional
from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict

class DSCDigestRequest(BaseModel):
    document_type: str # 'board_minutes', 'invoice', 'aoc4', 'mgt7'
    document_id: uuid.UUID

class DSCDigestResponse(BaseModel):
    document_type: str
    document_id: uuid.UUID
    sha256_hash: str
    document_title: str

class DSCSignatureSubmit(BaseModel):
    document_type: str
    document_id: uuid.UUID
    sha256_hash: str
    signature_hex: str
    certificate_der_hex: Optional[str] = None
    signer_din: Optional[str] = None
    signer_name: str
    token_model: Optional[str] = "HyperPKI HYP2003"
    token_serial_number: Optional[str] = None

class DSCSignatureAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_type: str
    document_id: uuid.UUID
    signer_name: str
    signer_din: Optional[str]
    token_model: str
    certificate_issuer: str
    sha256_document_hash: str
    signed_pdf_s3_key: str
    signed_at: datetime
