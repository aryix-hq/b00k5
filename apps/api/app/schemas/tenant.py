from typing import Optional, List
import uuid
from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    tenant_id: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: Optional[uuid.UUID] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

class TenantCreate(BaseModel):
    legal_name: str
    trade_name: Optional[str] = None
    cin: Optional[str] = None # e.g. U72900KA2026PTC123456
    pan: str
    gstin: Optional[str] = None
    state_code: str # e.g. 29 for Karnataka
    registered_office: str
    currency: str = "INR"

class TenantResponse(BaseModel):
    id: uuid.UUID
    legal_name: str
    trade_name: Optional[str]
    cin: Optional[str]
    pan: str
    gstin: Optional[str]
    state_code: str
    registered_office: str
    currency: str

    class Config:
        from_attributes = True

class FirstRunSetupRequest(BaseModel):
    # Admin User
    admin_email: str
    admin_password: str
    admin_first_name: str
    admin_last_name: str
    admin_din: Optional[str] = None

    # Company
    legal_name: str
    trade_name: Optional[str] = None
    cin: Optional[str] = None
    pan: str
    gstin: Optional[str] = None
    tan: Optional[str] = None
    state_code: str
    registered_office: str
    incorporation_date: Optional[str] = None # YYYY-MM-DD
