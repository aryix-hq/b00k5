import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Numeric, Text, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class ComplianceEvent(Base):
    __tablename__ = "compliance_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    category = Column(
        SQLEnum(
            'board_meeting_120d',
            'partner_meeting',
            'dir3_kyc',
            'aoc_4',
            'mgt_7',
            'llp_form_11',
            'llp_form_8',
            'inc_20a',
            'advance_tax',
            'gstr_1',
            'gstr_3b',
            'itr_filing',
            name="compliance_category_enum"
        ),
        nullable=False
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=False)
    statutory_reference = Column(String(128), nullable=True)
    fine_per_day_inr = Column(Numeric(10, 2), default=0.00)
    status = Column(
        SQLEnum('upcoming', 'due_soon', 'overdue', 'completed', 'waived', name="compliance_status_enum"),
        default='upcoming'
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document_vault.id"), nullable=True)
    metadata_json = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="compliance_events")
    document = relationship("DocumentVault")

class CorporateMeeting(Base):
    __tablename__ = "corporate_meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    meeting_type = Column(String(50), default="board_meeting", nullable=False)
    meeting_number = Column(String(50), nullable=False)
    meeting_date = Column(Date, nullable=False)
    meeting_time = Column(String(50), nullable=False)
    venue = Column(Text, nullable=False)
    directors_present = Column(JSONB, default=list, nullable=False)
    agenda_items = Column(JSONB, default=list, nullable=False)
    resolutions = Column(JSONB, default=list, nullable=False)
    signed_document_key = Column(String(255), nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")

class StatutoryFilingAnchor(Base):
    __tablename__ = "statutory_filing_anchors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    assessment_year = Column(String(32), nullable=False)
    form_type = Column(String(50), nullable=False) # 'aoc_4', 'itr_6', 'mgt_7', 'audit_report'
    srn_or_ack_number = Column(String(100), nullable=False)
    filing_date = Column(Date, nullable=False)
    signatory_din = Column(String(8), nullable=True)
    auditor_udin = Column(String(18), nullable=True)
    s3_document_key = Column(String(500), nullable=True)
    document_sha256 = Column(String(64), nullable=True)
    schedule_iii_payload = Column(JSONB, default=dict, nullable=False)
    is_locked = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")

class AdvanceTaxForecast(Base):
    __tablename__ = "advance_tax_forecasts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    assessment_year = Column(String(32), nullable=False)
    calculation_date = Column(Date, nullable=False)
    tax_regime = Column(String(50), nullable=False) # 'sec_115baa_22', 'normal_25', 'llp_30'
    ytd_revenue = Column(Numeric(15, 2), default=0.00, nullable=False)
    ytd_expenses = Column(Numeric(15, 2), default=0.00, nullable=False)
    ytd_net_profit = Column(Numeric(15, 2), default=0.00, nullable=False)
    projected_annual_profit = Column(Numeric(15, 2), default=0.00, nullable=False)
    effective_tax_rate = Column(Numeric(6, 3), nullable=False)
    gross_projected_tax = Column(Numeric(15, 2), default=0.00, nullable=False)
    tds_tcs_credits_claimed = Column(Numeric(15, 2), default=0.00, nullable=False)
    net_advance_tax_payable = Column(Numeric(15, 2), default=0.00, nullable=False)
    q1_due = Column(Numeric(15, 2), default=0.00, nullable=False)
    q2_due = Column(Numeric(15, 2), default=0.00, nullable=False)
    q3_due = Column(Numeric(15, 2), default=0.00, nullable=False)
    q4_due = Column(Numeric(15, 2), default=0.00, nullable=False)
    q1_paid = Column(Numeric(15, 2), default=0.00, nullable=False)
    q2_paid = Column(Numeric(15, 2), default=0.00, nullable=False)
    q3_paid = Column(Numeric(15, 2), default=0.00, nullable=False)
    q4_paid = Column(Numeric(15, 2), default=0.00, nullable=False)
    interest_234c_projected = Column(Numeric(15, 2), default=0.00, nullable=False)
    interest_234b_projected = Column(Numeric(15, 2), default=0.00, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")

class AdvanceTaxChallan(Base):
    __tablename__ = "advance_tax_challans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    quarter = Column(String(2), nullable=False) # 'Q1', 'Q2', 'Q3', 'Q4'
    payment_date = Column(Date, nullable=False)
    bsr_code = Column(String(7), nullable=False)
    challan_serial_no = Column(String(10), nullable=False)
    cin_number = Column(String(30), nullable=True)
    amount_paid = Column(Numeric(15, 2), nullable=False)
    s3_challan_receipt_key = Column(String(500), nullable=True)
    bank_statement_line_id = Column(UUID(as_uuid=True), ForeignKey("bank_statement_lines.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")

class GSTChallan(Base):
    __tablename__ = "gst_challans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    period = Column(String(32), nullable=False) # '2026-04' or '2026-Q1'
    frequency = Column(String(32), nullable=False) # 'monthly', 'quarterly_qrmp', 'composition', 'annual'
    challan_type = Column(String(32), nullable=False) # 'PMT-06', 'PMT-01', 'CMP-08', 'DRC-03'
    cpin = Column(String(20), nullable=False)
    cin = Column(String(30), nullable=True)
    payment_date = Column(Date, nullable=False)
    bank_ref_no = Column(String(50), nullable=True)
    cgst_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    sgst_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    igst_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    cess_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    interest_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    penalty_amount = Column(Numeric(15, 2), default=0.00, nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    s3_challan_receipt_key = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant")
