import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, BigInteger, Numeric, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class StatutoryMember(Base):
    """
    Form MGT-1: Register of Members pursuant to Section 88(1)(a) of the Companies Act, 2013
    and Rule 3(1) of the Companies (Management and Administration) Rules, 2014.
    """
    __tablename__ = "statutory_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    folio_number = Column(String(64), nullable=False)
    member_name = Column(String(255), nullable=False)
    father_or_spouse_name = Column(String(255), nullable=True)
    pan = Column(String(10), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    date_of_becoming_member = Column(Date, nullable=False, default=date.today)
    date_of_cessation = Column(Date, nullable=True)
    number_of_shares = Column(Numeric(15, 2), nullable=False)
    distinctive_from = Column(BigInteger, nullable=False)
    distinctive_to = Column(BigInteger, nullable=False)
    nominal_value_per_share = Column(Numeric(10, 2), default=10.00)
    amount_paid_per_share = Column(Numeric(10, 2), default=10.00)
    certificate_number = Column(String(64), nullable=True)
    status = Column(String(32), default="ACTIVE")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
    certificates = relationship("ShareCertificate", back_populates="member")


class StatutoryLoanGuarantee(Base):
    """
    Form MBP-2: Register of Loans, Guarantees, Security and Acquisition made by the Company
    pursuant to Section 186(9) of the Companies Act, 2013 and Rule 12(1) of Companies (Meetings of Board and its Powers) Rules, 2014.
    """
    __tablename__ = "statutory_loans_guarantees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    transaction_type = Column(String(32), nullable=False) # 'LOAN_GIVEN', 'GUARANTEE', 'SECURITY', 'INVESTMENT'
    body_corporate_name = Column(String(255), nullable=False)
    cin_or_pan = Column(String(32), nullable=True)
    amount = Column(Numeric(15, 2), nullable=False)
    interest_rate_pct = Column(Numeric(5, 2), nullable=True)
    tenure_months = Column(Integer, nullable=True)
    board_resolution_date = Column(Date, nullable=False)
    special_resolution_date = Column(Date, nullable=True)
    status = Column(String(32), default="ACTIVE") # 'ACTIVE', 'REPAID', 'DISCHARGED'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")


class StatutoryContractInterestedDirector(Base):
    """
    Form MBP-4: Register of Contracts & Arrangements in which Directors are Interested
    pursuant to Section 189(1) of the Companies Act, 2013 and Rule 16(1) of Companies (Meetings of Board and its Powers) Rules, 2014.
    """
    __tablename__ = "statutory_contracts_interested_directors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    contract_date = Column(Date, nullable=False)
    party_name = Column(String(255), nullable=False)
    nature_of_contract = Column(Text, nullable=False)
    contract_value = Column(Numeric(15, 2), nullable=True)
    director_name = Column(String(255), nullable=False)
    director_din = Column(String(8), nullable=True)
    nature_of_interest = Column(Text, nullable=False)
    board_meeting_date = Column(Date, nullable=False)
    voting_status = Column(String(64), default="ABSTAINED")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")


class DirectorAnnualDisclosure(Base):
    """
    Annual Statutory Director Disclosures:
    - Form MBP-1: Notice of Interest by Director (Sec 184(1) & Rule 9(1))
    - Form DIR-8: Intimation of Non-Disqualification by Director (Sec 164(2) & Rule 14(1))
    """
    __tablename__ = "director_annual_disclosures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    fiscal_year = Column(String(10), nullable=False) # e.g. '2026-27'
    form_type = Column(String(16), nullable=False)   # 'MBP_1', 'DIR_8'
    director_name = Column(String(255), nullable=False)
    director_din = Column(String(8), nullable=False)
    filing_date = Column(Date, nullable=False, default=date.today)
    disclosure_payload = Column(JSONB, nullable=False, default=dict)
    is_digitally_signed = Column(Boolean, default=False)
    signed_hash = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")


class ShareCertificate(Base):
    """
    Form SH-1: Share Certificate pursuant to Section 46 of the Companies Act, 2013
    and Rule 5(2) of the Companies (Share Capital and Debentures) Rules, 2014.
    """
    __tablename__ = "share_certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    certificate_number = Column(String(64), nullable=False)
    member_id = Column(UUID(as_uuid=True), ForeignKey("statutory_members.id", ondelete="RESTRICT"), nullable=False)
    number_of_shares = Column(Integer, nullable=False)
    distinctive_from = Column(BigInteger, nullable=False)
    distinctive_to = Column(BigInteger, nullable=False)
    face_value = Column(Numeric(10, 2), default=10.00)
    issue_date = Column(Date, nullable=False, default=date.today)
    signatory_director_1 = Column(String(255), nullable=True)
    signatory_director_2 = Column(String(255), nullable=True)
    signatory_secretary_or_authorized = Column(String(255), nullable=True)
    status = Column(String(32), default="ISSUED")
    pdf_s3_key = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
    member = relationship("StatutoryMember", back_populates="certificates")

