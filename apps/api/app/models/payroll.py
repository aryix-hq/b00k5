import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, Boolean, DateTime, Date, Numeric, Integer, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_code = Column(String(32), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(20), nullable=True)
    date_of_joining = Column(Date, nullable=False)
    date_of_exit = Column(Date, nullable=True)
    status = Column(
        SQLEnum('active', 'on_notice', 'terminated', 'resigned', 'on_leave', name="employee_status_enum"),
        default='active',
        nullable=False
    )
    employment_type = Column(
        SQLEnum('full_time', 'part_time', 'intern', 'contractor', 'consultant', name="employment_type_enum"),
        default='full_time',
        nullable=False
    )
    department = Column(String(100), nullable=True)
    designation = Column(String(100), nullable=False)
    pan_number = Column(String(10), nullable=False)
    aadhaar_ref_id = Column(String(64), nullable=True)
    uan_number = Column(String(12), nullable=True)
    esic_number = Column(String(17), nullable=True)
    bank_account_number = Column(String(34), nullable=False)
    bank_ifsc_code = Column(String(11), nullable=False)
    bank_name = Column(String(100), nullable=False)
    tax_regime = Column(
        SQLEnum('new_115bac', 'old_regime', name="tax_regime_enum"),
        default='new_115bac',
        nullable=False
    )
    pt_state = Column(String(50), default='Karnataka', nullable=False)
    pf_opt_out = Column(Boolean, default=False, nullable=False)
    is_pf_capped = Column(Boolean, default=True, nullable=False)
    is_esi_eligible = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant")
    salary_structures = relationship("SalaryStructure", back_populates="employee", cascade="all, delete-orphan")
    payslips = relationship("Payslip", back_populates="employee")
    tax_declarations = relationship("EmployeeTaxDeclaration", back_populates="employee", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def active_salary_structure(self):
        for s in self.salary_structures:
            if s.is_active:
                return s
        return None


class SalaryStructure(Base):
    __tablename__ = "salary_structures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    annual_ctc = Column(Numeric(15, 2), nullable=False)
    monthly_basic = Column(Numeric(15, 2), nullable=False)
    monthly_hra = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    monthly_da = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    monthly_conveyance = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    monthly_medical_allowance = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    monthly_special_allowance = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    employer_pf_monthly = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    employer_esi_monthly = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="salary_structures")

    @property
    def monthly_gross(self) -> Decimal:
        return Decimal(str(self.monthly_basic or 0)) + \
               Decimal(str(self.monthly_hra or 0)) + \
               Decimal(str(self.monthly_da or 0)) + \
               Decimal(str(self.monthly_conveyance or 0)) + \
               Decimal(str(self.monthly_medical_allowance or 0)) + \
               Decimal(str(self.monthly_special_allowance or 0))


class PayrollRun(Base):
    __tablename__ = "payroll_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    run_number = Column(String(32), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    status = Column(
        SQLEnum('draft', 'calculated', 'approved', 'locked', 'disbursed', 'sealed', name="payroll_status_enum"),
        default='draft',
        nullable=False
    )
    total_employees = Column(Integer, default=0, nullable=False)
    total_gross_pay = Column(Numeric(15, 2), default=0.00, nullable=False)
    total_deductions = Column(Numeric(15, 2), default=0.00, nullable=False)
    total_net_pay = Column(Numeric(15, 2), default=0.00, nullable=False)
    total_employer_pf = Column(Numeric(15, 2), default=0.00, nullable=False)
    total_employer_esi = Column(Numeric(15, 2), default=0.00, nullable=False)
    total_tds_192 = Column(Numeric(15, 2), default=0.00, nullable=False)
    total_pt = Column(Numeric(15, 2), default=0.00, nullable=False)
    accrual_journal_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    disbursement_journal_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    sealed_at = Column(DateTime(timezone=True), nullable=True)
    sealed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    sha256_audit_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    payslips = relationship("Payslip", back_populates="payroll_run", cascade="all, delete-orphan")
    accrual_journal = relationship("JournalEntry", foreign_keys=[accrual_journal_id])
    disbursement_journal = relationship("JournalEntry", foreign_keys=[disbursement_journal_id])


class Payslip(Base):
    __tablename__ = "payslips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    payroll_run_id = Column(UUID(as_uuid=True), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False)
    payslip_number = Column(String(64), nullable=False)
    total_days = Column(Integer, default=30, nullable=False)
    paid_days = Column(Numeric(5, 2), default=30.00, nullable=False)
    loss_of_pay_days = Column(Numeric(5, 2), default=0.00, nullable=False)
    
    # Earnings
    basic_earned = Column(Numeric(15, 2), default=0.00, nullable=False)
    hra_earned = Column(Numeric(15, 2), default=0.00, nullable=False)
    da_earned = Column(Numeric(15, 2), default=0.00, nullable=False)
    conveyance_earned = Column(Numeric(15, 2), default=0.00, nullable=False)
    special_allowance_earned = Column(Numeric(15, 2), default=0.00, nullable=False)
    bonus_or_arrears = Column(Numeric(15, 2), default=0.00, nullable=False)
    gross_earnings = Column(Numeric(15, 2), default=0.00, nullable=False)

    # Deductions
    employee_pf = Column(Numeric(15, 2), default=0.00, nullable=False)
    employee_esi = Column(Numeric(15, 2), default=0.00, nullable=False)
    professional_tax = Column(Numeric(15, 2), default=0.00, nullable=False)
    tds_deducted = Column(Numeric(15, 2), default=0.00, nullable=False)
    lwf_deducted = Column(Numeric(15, 2), default=0.00, nullable=False)
    other_deductions = Column(Numeric(15, 2), default=0.00, nullable=False)
    total_deductions = Column(Numeric(15, 2), default=0.00, nullable=False)
    net_salary = Column(Numeric(15, 2), default=0.00, nullable=False)

    # Employer Contributions
    employer_pf = Column(Numeric(15, 2), default=0.00, nullable=False)
    employer_eps = Column(Numeric(15, 2), default=0.00, nullable=False)
    employer_esi = Column(Numeric(15, 2), default=0.00, nullable=False)
    employer_edli = Column(Numeric(15, 2), default=0.00, nullable=False)

    # Disbursement
    payout_status = Column(String(20), default='unpaid', nullable=False)
    payout_utr = Column(String(64), nullable=True)
    payout_date = Column(Date, nullable=True)
    pdf_vault_path = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    payroll_run = relationship("PayrollRun", back_populates="payslips")
    employee = relationship("Employee", back_populates="payslips")


class EmployeeTaxDeclaration(Base):
    __tablename__ = "employee_tax_declarations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    fiscal_year = Column(String(32), nullable=False)
    regime = Column(
        SQLEnum('new_115bac', 'old_regime', name="tax_regime_enum"),
        default='new_115bac',
        nullable=False
    )
    sec_80c_lic = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_80c_ppf = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_80c_elss = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_80c_home_loan_principal = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_80c_tuition_fees = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_80c_total_claimed = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_80c_total_verified = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_80d_self_family = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_80d_parents = Column(Numeric(15, 2), default=0.00, nullable=False)
    sec_24b_home_loan_interest = Column(Numeric(15, 2), default=0.00, nullable=False)
    lender_pan = Column(String(10), nullable=True)
    annual_rent_paid = Column(Numeric(15, 2), default=0.00, nullable=False)
    landlord_pan = Column(String(10), nullable=True)
    rental_address = Column(Text, nullable=True)
    is_metro_city = Column(Boolean, default=False, nullable=False)
    verification_status = Column(String(20), default='submitted', nullable=False)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="tax_declarations")

