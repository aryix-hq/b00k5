from typing import Optional
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
    email: str
    password: str
    tenant_id: Optional[uuid.UUID] = None

class GoogleLoginRequest(BaseModel):
    email: str
    name: Optional[str] = None
    id_token: Optional[str] = None
    google_id: Optional[str] = None
    tenant_id: Optional[uuid.UUID] = None

class UserCreate(BaseModel):
    email: str
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
