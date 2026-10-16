from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import date, datetime
import uuid


class TDSCalculateRequest(BaseModel):
    gross_amount: Decimal
    section: str = Field(..., description="194C, 194J, 194I, 194Q")
    deductee_type: str = Field("COMPANY", description="COMPANY or NON_COMPANY")
    pan: Optional[str] = None
    is_lower_deduction: bool = False
    lower_deduction_rate: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class TDSCalculateResponse(BaseModel):
    gross_amount: Decimal
    section: str
    applicable_rate_pct: Decimal
    tds_amount: Decimal
    net_payable_amount: Decimal
    pan_valid: bool
    threshold_exceeded: bool
    statutory_notes: str

    model_config = ConfigDict(from_attributes=True)


class TDSDeductionCreate(BaseModel):
    expense_id: Optional[uuid.UUID] = None
    deductee_name: str
    deductee_pan: str
    deductee_type: str = "COMPANY"
    section: str
    gross_amount: Decimal
    rate_percentage: Optional[Decimal] = None
    tds_amount: Optional[Decimal] = None
    deduction_date: Optional[date] = None
    fiscal_year: Optional[str] = None
    quarter: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TDSDeductionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    expense_id: Optional[uuid.UUID] = None
    journal_entry_id: Optional[uuid.UUID] = None
    deductee_name: str
    deductee_pan: str
    deductee_type: str
    section: str
    rate_percentage: Decimal
    gross_amount: Decimal
    tds_amount: Decimal
    net_payable: Decimal
    deduction_date: date
    fiscal_year: str
    quarter: str
    tds_challan_id: Optional[uuid.UUID] = None
    status: str
    certificate_number: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TDSChallanCreate(BaseModel):
    fiscal_year: str
    quarter: str
    section: str
    bsr_code: str
    challan_serial_no: str
    payment_date: date
    tds_amount: Decimal
    surcharge_amount: Decimal = Decimal("0.00")
    cess_amount: Decimal = Decimal("0.00")
    interest_amount: Decimal = Decimal("0.00")
    fee_amount: Decimal = Decimal("0.00")
    total_amount: Optional[Decimal] = None
    cin: Optional[str] = None
    minor_head: str = "200"
    deduction_ids: Optional[List[uuid.UUID]] = None

    model_config = ConfigDict(from_attributes=True)


class TDSChallanResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    fiscal_year: str
    quarter: str
    section: str
    bsr_code: str
    challan_serial_no: str
    payment_date: date
    tds_amount: Decimal
    total_amount: Decimal
    cin: Optional[str] = None
    minor_head: str
    created_at: datetime
    deductions_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TDSSummaryResponse(BaseModel):
    fiscal_year: str
    total_deducted: Decimal
    total_deposited: Decimal
    total_pending_deposit: Decimal
    next_due_date: date
    days_until_due: int
    quarter_summaries: List[Dict[str, Any]]
    section_breakdown: List[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)

