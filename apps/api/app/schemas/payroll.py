from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
import uuid


class SalaryStructureBase(BaseModel):
    effective_from: date
    effective_to: Optional[date] = None
    annual_ctc: Decimal = Field(..., ge=0)
    monthly_basic: Decimal = Field(..., ge=0)
    monthly_hra: Decimal = Field(default=Decimal("0.00"), ge=0)
    monthly_da: Decimal = Field(default=Decimal("0.00"), ge=0)
    monthly_conveyance: Decimal = Field(default=Decimal("0.00"), ge=0)
    monthly_medical_allowance: Decimal = Field(default=Decimal("0.00"), ge=0)
    monthly_special_allowance: Decimal = Field(default=Decimal("0.00"), ge=0)
    employer_pf_monthly: Decimal = Field(default=Decimal("0.00"), ge=0)
    employer_esi_monthly: Decimal = Field(default=Decimal("0.00"), ge=0)


class SalaryStructureCreate(SalaryStructureBase):
    employee_id: Optional[uuid.UUID] = None


class SalaryStructureResponse(SalaryStructureBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    monthly_gross: Decimal
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeBase(BaseModel):
    employee_code: str = Field(..., max_length=32)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    date_of_birth: date
    gender: Optional[str] = None
    date_of_joining: date
    date_of_exit: Optional[date] = None
    status: str = "active"
    employment_type: str = "full_time"
    department: Optional[str] = None
    designation: str = Field(..., max_length=100)
    pan_number: str = Field(..., min_length=10, max_length=10)
    aadhaar_ref_id: Optional[str] = None
    uan_number: Optional[str] = None
    esic_number: Optional[str] = None
    bank_account_number: str = Field(..., max_length=34)
    bank_ifsc_code: str = Field(..., max_length=11)
    bank_name: str = Field(..., max_length=100)
    tax_regime: str = "new_115bac"
    pt_state: str = "Karnataka"
    pf_opt_out: bool = False
    is_pf_capped: bool = True
    is_esi_eligible: bool = False


class EmployeeCreate(EmployeeBase):
    initial_salary_structure: Optional[SalaryStructureCreate] = None


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    status: Optional[str] = None
    date_of_exit: Optional[date] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    tax_regime: Optional[str] = None
    pt_state: Optional[str] = None
    pf_opt_out: Optional[bool] = None
    is_pf_capped: Optional[bool] = None
    is_esi_eligible: Optional[bool] = None


class EmployeeResponse(EmployeeBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    full_name: str
    salary_structures: List[SalaryStructureResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayslipResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
    payslip_number: str
    total_days: int
    paid_days: Decimal
    loss_of_pay_days: Decimal

    basic_earned: Decimal
    hra_earned: Decimal
    da_earned: Decimal
    conveyance_earned: Decimal
    special_allowance_earned: Decimal
    bonus_or_arrears: Decimal
    gross_earnings: Decimal

    employee_pf: Decimal
    employee_esi: Decimal
    professional_tax: Decimal
    tds_deducted: Decimal
    lwf_deducted: Decimal
    other_deductions: Decimal
    total_deductions: Decimal
    net_salary: Decimal

    employer_pf: Decimal
    employer_eps: Decimal
    employer_esi: Decimal
    employer_edli: Decimal

    payout_status: str
    payout_utr: Optional[str] = None
    payout_date: Optional[date] = None
    pdf_vault_path: Optional[str] = None
    created_at: datetime

    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    fiscal_year: Optional[str] = None
    month: Optional[int] = None
    year: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PayrollRunCreate(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020)
    fiscal_year: Optional[str] = None


class PayrollRunResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    run_number: str
    month: int
    year: int
    fiscal_year: str
    status: str
    total_employees: int
    total_gross_pay: Decimal
    total_deductions: Decimal
    total_net_pay: Decimal
    total_employer_pf: Decimal
    total_employer_esi: Decimal
    total_tds_192: Decimal
    total_pt: Decimal
    accrual_journal_id: Optional[uuid.UUID] = None
    disbursement_journal_id: Optional[uuid.UUID] = None
    sealed_at: Optional[datetime] = None
    sha256_audit_hash: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollRunDetailResponse(PayrollRunResponse):
    payslips: List[PayslipResponse] = []


class EmployeeTaxDeclarationBase(BaseModel):
    fiscal_year: str
    regime: str = "new_115bac"
    sec_80c_lic: Decimal = Decimal("0.00")
    sec_80c_ppf: Decimal = Decimal("0.00")
    sec_80c_elss: Decimal = Decimal("0.00")
    sec_80c_home_loan_principal: Decimal = Decimal("0.00")
    sec_80c_tuition_fees: Decimal = Decimal("0.00")
    sec_80c_total_claimed: Decimal = Decimal("0.00")
    sec_80d_self_family: Decimal = Decimal("0.00")
    sec_80d_parents: Decimal = Decimal("0.00")
    sec_24b_home_loan_interest: Decimal = Decimal("0.00")
    lender_pan: Optional[str] = None
    annual_rent_paid: Decimal = Decimal("0.00")
    landlord_pan: Optional[str] = None
    rental_address: Optional[str] = None
    is_metro_city: bool = False


class EmployeeTaxDeclarationCreate(EmployeeTaxDeclarationBase):
    employee_id: uuid.UUID


class EmployeeTaxDeclarationResponse(EmployeeTaxDeclarationBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    sec_80c_total_verified: Decimal
    verification_status: str
    verified_by: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Form16Response(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    employee_code: str
    pan_number: str
    designation: str
    tenant_name: str
    tenant_pan: Optional[str] = None
    tenant_tan: Optional[str] = None
    tenant_address: Optional[str] = None
    fiscal_year: str
    assessment_year: str
    tax_regime: str
    gross_salary: Decimal
    standard_deduction: Decimal
    professional_tax: Decimal
    net_salary_under_sec_16: Decimal
    deductions_chapter_vi_a: Decimal
    total_taxable_income: Decimal
    tax_on_total_income: Decimal
    rebate_87a: Decimal
    health_and_education_cess: Decimal
    total_tax_payable: Decimal
    total_tax_deducted: Decimal
    quarterly_tds_summary: List[dict] = []


class ContractorBase(BaseModel):
    contractor_code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=150)
    contractor_type: str = "individual_huf"  # individual_huf, company_firm
    pan_number: str = Field(..., min_length=10, max_length=10)
    gstin: Optional[str] = Field(None, max_length=15)
    tds_section: str = "194J_TECH"  # 194C, 194J_TECH, 194J_PROF
    tds_rate: Decimal = Field(default=Decimal("2.00"), ge=0, le=100)
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    bank_name: str = Field(..., max_length=100)
    bank_account_number: str = Field(..., max_length=34)
    bank_ifsc_code: str = Field(..., max_length=11)
    status: str = "active"


class ContractorCreate(ContractorBase):
    pass


class ContractorUpdate(BaseModel):
    name: Optional[str] = None
    contractor_type: Optional[str] = None
    pan_number: Optional[str] = None
    gstin: Optional[str] = None
    tds_section: Optional[str] = None
    tds_rate: Optional[Decimal] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    status: Optional[str] = None


class ContractorResponse(ContractorBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractorPaymentBase(BaseModel):
    contractor_id: uuid.UUID
    invoice_number: str = Field(..., max_length=64)
    invoice_date: date
    payment_date: date
    description: str
    gross_amount: Decimal = Field(..., gt=0)
    gst_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    gst_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    tds_section: Optional[str] = None
    tds_rate: Optional[Decimal] = None


class ContractorPaymentCreate(ContractorPaymentBase):
    pass


class ContractorPaymentResponse(ContractorPaymentBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    payment_number: str
    tds_section: str
    tds_rate: Decimal
    tds_amount: Decimal
    net_payable: Decimal
    status: str
    accrual_journal_id: Optional[uuid.UUID] = None
    disbursement_journal_id: Optional[uuid.UUID] = None
    payout_utr: Optional[str] = None
    payout_date: Optional[date] = None
    contractor_name: Optional[str] = None
    contractor_pan: Optional[str] = None
    contractor_code: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Form16AResponse(BaseModel):
    contractor_id: uuid.UUID
    contractor_name: str
    contractor_pan: str
    contractor_address: Optional[str] = None
    deductor_name: str
    deductor_pan: Optional[str] = None
    deductor_tan: Optional[str] = None
    deductor_address: Optional[str] = None
    assessment_year: str
    financial_year: str
    quarter: str
    nature_of_payment: str
    total_gross_amount: Decimal
    total_tds_deducted: Decimal
    payments_breakdown: List[dict] = []


class QuickContractorPaymentRequest(BaseModel):
    freelancer_name: str = Field(..., min_length=2, max_length=150)
    pan_number: Optional[str] = Field(None, max_length=10)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    service_type: str = Field(default="194J_TECH")  # 194J_TECH (2%), 194J_PROF (10%), 194C (1%), NO_TDS (0%)
    amount: Decimal = Field(..., gt=0)
    amount_type: str = Field(default="gross")  # 'gross' or 'net'
    description: str = Field(default="Freelance Professional / Technical Services")
    invoice_number: Optional[str] = None
    payment_date: Optional[date] = None
    bank_reference_or_utr: Optional[str] = None
    bank_name: Optional[str] = "HDFC Bank"
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    disburse_immediately: bool = True
    contra_bank_account_code: str = "1010"




