import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, SmallInteger, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=True)
    entity_type = Column(String(64), default="Private Limited Company", nullable=True)
    cin = Column(String(21), unique=True, nullable=True)
    pan = Column(String(10), unique=True, nullable=False)
    gstin = Column(String(15), unique=True, nullable=True)
    state_code = Column(String(2), nullable=False)
    registered_office = Column(String, nullable=False)
    currency = Column(String(3), default="INR")
    fy_start_month = Column(SmallInteger, default=4)
    logo_url = Column(String, nullable=True)
    logo_s3_key = Column(String(255), nullable=True)
    statutory_profile = Column("statutory_profile", JSONB, default=dict)
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant_users = relationship("TenantUser", back_populates="tenant", cascade="all, delete-orphan")
    invitations = relationship("TenantInvitation", back_populates="tenant", cascade="all, delete-orphan")
    accounts = relationship("ChartOfAccounts", back_populates="tenant", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="tenant", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="tenant", cascade="all, delete-orphan")
    documents = relationship("DocumentVault", back_populates="tenant", cascade="all, delete-orphan")
    compliance_events = relationship("ComplianceEvent", back_populates="tenant", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    is_super_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant_memberships = relationship("TenantUser", back_populates="user", cascade="all, delete-orphan")

class TenantUser(Base):
    __tablename__ = "tenant_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(
        SQLEnum(
            'owner', 'company_owner', 'ca_auditor', 'auditor_ca', 'finance_manager', 'employee',
            name="user_role_enum",
            create_type=False
        ),
        default='employee',
        nullable=False
    )
    din = Column(String(8), nullable=True)
    icai_membership_no = Column(String(16), nullable=True)
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="tenant_users")
    user = relationship("User", back_populates="tenant_memberships")

class TenantInvitation(Base):
    __tablename__ = "tenant_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(64), default='employee', nullable=False)
    token = Column(String(128), unique=True, nullable=False, index=True)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_accepted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="invitations")
    inviter = relationship("User")
