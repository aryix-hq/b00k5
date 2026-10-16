from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import date, datetime
import uuid


SCHEDULE_II_USEFUL_LIFE_MAP: Dict[str, Decimal] = {
    "COMPUTERS_END_USER": Decimal("3.0"),         # Laptops, Desktops, End-user devices
    "SERVERS_NETWORK": Decimal("6.0"),            # Servers and network equipment
    "OFFICE_EQUIPMENT": Decimal("5.0"),           # Printers, scanners, projectors, fax
    "FURNITURE": Decimal("10.0"),                 # Desks, chairs, partitions, fixtures
    "PLANT_MACHINERY": Decimal("15.0"),           # General industrial plant & machinery
    "ELECTRICAL_INSTALLATIONS": Decimal("10.0"),  # UPS, wiring, transformers, generators
}

SCHEDULE_II_CATEGORY_NAMES: Dict[str, str] = {
    "COMPUTERS_END_USER": "Computers & Data Processing Units (End User - 3 Yrs)",
    "SERVERS_NETWORK": "Servers & Network Equipment (6 Yrs)",
    "OFFICE_EQUIPMENT": "Office Equipment (5 Yrs)",
    "FURNITURE": "Furniture & Fixtures (10 Yrs)",
    "PLANT_MACHINERY": "Plant & Machinery (General - 15 Yrs)",
    "ELECTRICAL_INSTALLATIONS": "Electrical Installations & Equipment (10 Yrs)",
}


class FixedAssetCreate(BaseModel):
    asset_name: str
    category: str = Field(..., description="Schedule II Category: COMPUTERS_END_USER, SERVERS_NETWORK, etc.")
    purchase_date: date
    capitalization_date: Optional[date] = None
    gross_block: Decimal = Field(..., description="Original acquisition cost including freight and installation")
    salvage_value: Optional[Decimal] = Field(None, description="Default 5% of gross block under Schedule II")
    useful_life_years: Optional[Decimal] = Field(None, description="Default from Schedule II Part C")
    depreciation_method: str = Field("SLM", description="SLM or WDV")
    location: Optional[str] = None
    serial_number: Optional[str] = None
    auto_post_purchase_jv: bool = False
    payment_account_code: str = "1010"

    model_config = ConfigDict(from_attributes=True)


class FixedAssetResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    asset_code: str
    asset_name: str
    category: str
    category_display: str
    purchase_date: date
    capitalization_date: date
    gross_block: Decimal
    salvage_value: Decimal
    useful_life_years: Decimal
    depreciation_method: str
    accumulated_depreciation: Decimal
    net_block: Decimal
    location: Optional[str] = None
    serial_number: Optional[str] = None
    status: str
    purchase_journal_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepreciationRunCreate(BaseModel):
    fiscal_year: str
    period_start: date
    period_end: date
    run_date: Optional[date] = None
    auto_post_jv: bool = True

    model_config = ConfigDict(from_attributes=True)


class DepreciationRunResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    fiscal_year: str
    period_start: date
    period_end: date
    run_date: date
    total_depreciation_amount: Decimal
    journal_entry_id: Optional[uuid.UUID] = None
    journal_entry_number: Optional[str] = None
    status: str
    asset_count: int
    details: List[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleIISummaryResponse(BaseModel):
    fiscal_year: str
    as_of_date: date
    total_gross_block: Decimal
    total_accumulated_depreciation: Decimal
    total_net_block: Decimal
    categories: List[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)

