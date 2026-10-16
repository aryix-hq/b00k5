from typing import Optional, List
from datetime import date, datetime
import uuid
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class AccountBase(BaseModel):
    code: str
    name: str
    type: str # asset, liability, equity, revenue, expense
    sub_type: Optional[str] = None
    normal_balance: str # debit, credit
    description: Optional[str] = None

class AccountCreate(AccountBase):
    pass

class AccountResponse(AccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime

class JournalLineCreate(BaseModel):
    account_id: uuid.UUID
    debit_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_mutually_exclusive(self) -> "JournalLineCreate":
        d = self.debit_amount
        c = self.credit_amount
        if (d > 0 and c > 0) or (d == 0 and c == 0):
            raise ValueError(f"Line must contain either a non-zero debit or credit, not both or neither (Debits: {d}, Credits: {c})")
        return self

class JournalLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    debit_amount: Decimal
    credit_amount: Decimal
    description: Optional[str]

class JournalEntryCreate(BaseModel):
    entry_number: str
    entry_date: date = Field(default_factory=date.today)
    narration: str
    reference_type: Optional[str] = "manual"
    reference_id: Optional[uuid.UUID] = None
    status: Optional[str] = "posted"
    lines: List[JournalLineCreate]

    @model_validator(mode="after")
    def validate_zero_sum_balance(self) -> "JournalEntryCreate":
        if not self.lines or len(self.lines) < 2:
            raise ValueError("Journal entry must have at least two lines for double-entry bookkeeping")
        total_debits = sum(line.debit_amount for line in self.lines)
        total_credits = sum(line.credit_amount for line in self.lines)
        discrepancy = abs(total_debits - total_credits)
        if discrepancy != Decimal("0.00"):
            raise ValueError(
                f"Ledger Imbalance Violation: Sum(Debits) [{total_debits}] != Sum(Credits) [{total_credits}]. "
                f"Discrepancy: {discrepancy}."
            )
        return self

class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entry_number: str
    entry_date: date
    narration: str
    reference_type: Optional[str]
    is_posted: bool
    lines: List[JournalLineResponse] = []
    created_at: datetime

class TrialBalanceItem(BaseModel):
    account_id: uuid.UUID
    code: str
    name: str
    type: str
    debit_balance: Decimal
    credit_balance: Decimal

class TrialBalanceReport(BaseModel):
    tenant_id: uuid.UUID
    as_of_date: date
    items: List[TrialBalanceItem]
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool
