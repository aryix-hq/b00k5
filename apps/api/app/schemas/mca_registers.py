import uuid
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

# --- Form MGT-1: Register of Members ---
class MemberCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    folio_number: str
    member_name: str
    father_or_spouse_name: Optional[str] = None
    pan: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    date_of_becoming_member: date = Field(default_factory=date.today)
    number_of_shares: Decimal
    distinctive_from: int
    distinctive_to: int
    nominal_value_per_share: Decimal = Decimal("10.00")
    amount_paid_per_share: Decimal = Decimal("10.00")
    certificate_number: Optional[str] = None

class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    folio_number: str
    member_name: str
    father_or_spouse_name: Optional[str] = None
    pan: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    date_of_becoming_member: date
    date_of_cessation: Optional[date] = None
    number_of_shares: Decimal
    distinctive_from: int
    distinctive_to: int
    nominal_value_per_share: Decimal
    amount_paid_per_share: Decimal
    certificate_number: Optional[str] = None
    status: str
    created_at: datetime


# --- Form MBP-2: Register of Loans & Guarantees ---
class LoanGuaranteeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_type: str # 'LOAN_GIVEN', 'GUARANTEE', 'SECURITY', 'INVESTMENT'
    body_corporate_name: str
    cin_or_pan: Optional[str] = None
    amount: Decimal
    interest_rate_pct: Optional[Decimal] = None
    tenure_months: Optional[int] = None
    board_resolution_date: date
    special_resolution_date: Optional[date] = None
    notes: Optional[str] = None

class LoanGuaranteeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    transaction_type: str
    body_corporate_name: str
    cin_or_pan: Optional[str] = None
    amount: Decimal
    interest_rate_pct: Optional[Decimal] = None
    tenure_months: Optional[int] = None
    board_resolution_date: date
    special_resolution_date: Optional[date] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime


# --- Form MBP-4: Register of Contracts with Interested Directors ---
class ContractInterestedDirectorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contract_date: date
    party_name: str
    nature_of_contract: str
    contract_value: Optional[Decimal] = None
    director_name: str
    director_din: Optional[str] = None
    nature_of_interest: str
    board_meeting_date: date
    voting_status: str = "ABSTAINED"

class ContractInterestedDirectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    contract_date: date
    party_name: str
    nature_of_contract: str
    contract_value: Optional[Decimal] = None
    director_name: str
    director_din: Optional[str] = None
    nature_of_interest: str
    board_meeting_date: date
    voting_status: str
    created_at: datetime


# --- Annual Director Disclosures (MBP-1 & DIR-8) ---
class DirectorDisclosureCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fiscal_year: str # '2026-27'
    form_type: str   # 'MBP_1' or 'DIR_8'
    director_name: str
    director_din: str
    filing_date: date = Field(default_factory=date.today)
    disclosure_payload: Dict[str, Any] = Field(default_factory=dict)
    is_digitally_signed: bool = False
    signed_hash: Optional[str] = None

class DirectorDisclosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    fiscal_year: str
    form_type: str
    director_name: str
    director_din: str
    filing_date: date
    disclosure_payload: Dict[str, Any]
    is_digitally_signed: bool
    signed_hash: Optional[str] = None
    created_at: datetime


# --- Form SH-1: Share Certificate ---
class ShareCertificateCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: uuid.UUID
    certificate_number: str
    number_of_shares: int
    distinctive_from: int
    distinctive_to: int
    face_value: Decimal = Decimal("10.00")
    issue_date: date = Field(default_factory=date.today)
    signatory_director_1: Optional[str] = None
    signatory_director_2: Optional[str] = None
    signatory_secretary_or_authorized: Optional[str] = None

class ShareCertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    certificate_number: str
    member_id: uuid.UUID
    member_name: Optional[str] = None
    number_of_shares: int
    distinctive_from: int
    distinctive_to: int
    face_value: Decimal
    issue_date: date
    signatory_director_1: Optional[str] = None
    signatory_director_2: Optional[str] = None
    signatory_secretary_or_authorized: Optional[str] = None
    status: str
    pdf_s3_key: Optional[str] = None
    created_at: datetime

