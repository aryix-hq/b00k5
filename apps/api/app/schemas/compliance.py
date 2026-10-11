from typing import Optional, Dict, Any, List
from datetime import date, datetime
import uuid
from decimal import Decimal
from pydantic import BaseModel

class ComplianceEventCreate(BaseModel):
    category: str # board_meeting_120d, dir3_kyc, aoc_4, mgt_7, inc_20a, advance_tax, gstr_1, gstr_3b
    title: str
    description: Optional[str] = None
    due_date: date
    statutory_reference: Optional[str] = None
    fine_per_day_inr: Decimal = Decimal("0.00")
    metadata_json: Optional[Dict[str, Any]] = None

class ComplianceEventResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    category: str
    title: str
    description: Optional[str]
    due_date: date
    days_remaining: int
    statutory_reference: Optional[str]
    fine_per_day_inr: Decimal
    accumulated_penalty_inr: Decimal
    status: str # upcoming, due_soon, overdue, completed, waived
    completed_at: Optional[datetime] = None
    document_id: Optional[uuid.UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ComplianceSummaryResponse(BaseModel):
    total_events: int
    overdue_count: int
    due_soon_count: int
    total_penalty_accruing_inr: Decimal
    upcoming_events: List[ComplianceEventResponse]
