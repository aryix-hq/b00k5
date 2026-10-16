from typing import Optional, List
from datetime import date, datetime
import uuid
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

class BankStatementLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    statement_id: uuid.UUID
    line_number: int
    transaction_date: date
    value_date: Optional[date] = None
    description: str
    reference_number: Optional[str] = None
    payment_channel: str
    counterparty_name: Optional[str] = None
    withdrawal_amount: Decimal
    deposit_amount: Decimal
    running_balance: Decimal
    reconciliation_tier: str
    reconciliation_status: str
    confidence_score: Decimal
    matched_journal_entry_id: Optional[uuid.UUID] = None
    matched_journal_line_id: Optional[uuid.UUID] = None
    suspense_journal_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    created_at: datetime

class BankStatementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    bank_name: str
    account_number: str
    statement_from: Optional[date] = None
    statement_to: Optional[date] = None
    opening_balance: Decimal
    closing_balance: Decimal
    total_withdrawals: Decimal
    total_deposits: Decimal
    file_name: str
    status: str
    lines: List[BankStatementLineResponse] = []
    created_at: datetime

class ConfirmMatchRequest(BaseModel):
    journal_line_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    matched_invoice_id: Optional[uuid.UUID] = None
    expense_id: Optional[uuid.UUID] = None
    matched_expense_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None

class AllocateSuspenseRequest(BaseModel):
    target_account_id: uuid.UUID
    narration: Optional[str] = None

class ReconciliationSummaryResponse(BaseModel):
    statement_id: uuid.UUID
    total_lines: int
    reconciled_tier1_count: int
    probable_tier2_count: int
    suspense_tier3_count: int
    unreconciled_count: int
    opening_balance: Decimal
    closing_balance: Decimal
    calculated_closing_balance: Decimal
    is_balance_verified: bool
