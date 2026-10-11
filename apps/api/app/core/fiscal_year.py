"""
b00k5 - Dynamic Date-Driven Fiscal Year (FY) and Assessment Year (AY) Engine
Compliant with the Income Tax Act, 1961 and Companies Act, 2013 (Section 2(41)).

Statutory Rules:
- Indian Financial Year (FY) strictly runs April 1 of Year Y to March 31 of Year Y+1.
- Assessment Year (AY) is strictly FY + 1 year.
  - FY 2025-26 -> AY 2026-27
  - FY 2026-27 -> AY 2027-28
"""

import re
import uuid
from datetime import date, datetime
from typing import Tuple, Optional, Dict, Any, List
from dateutil import parser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


def parse_indian_date(date_str: str) -> date:
    """
    Parses Indian statutory dates using strict dayfirst=True logic.
    Ensures 01/10/2026 resolves to October 1, 2026, never January 10.
    """
    return parser.parse(date_str, dayfirst=True).date()


import calendar
from decimal import Decimal

INCOME_TAX_ACT_2025_EFFECTIVE_DATE = date(2026, 4, 1)


def calculate_indian_fy_ay(txn_date: date) -> Dict[str, Any]:
    """
    Dynamically computes Indian Financial Year (FY), Assessment Year (AY),
    and Tax Year (TY under the Income-tax Act, 2025 effective 1 April 2026)
    for ANY date without hardcoded year boundaries.
    """
    year = txn_date.year
    month = txn_date.month

    if month >= 4:
        fy_start_year = year
        fy_end_year = year + 1
    else:
        fy_start_year = year - 1
        fy_end_year = year

    ay_start_year = fy_start_year + 1
    ay_end_year = fy_end_year + 1

    fy_label = f"{fy_start_year}-{fy_end_year}"
    ay_label = f"{ay_start_year}-{ay_end_year}"
    ty_label = f"TY {fy_start_year}-{str(fy_end_year)[-2:]}" if txn_date >= INCOME_TAX_ACT_2025_EFFECTIVE_DATE else None
    fy_start = date(fy_start_year, 4, 1)
    fy_end = date(fy_end_year, 3, 31)

    is_it_act_2025 = txn_date >= INCOME_TAX_ACT_2025_EFFECTIVE_DATE
    governing_act = "Income-tax Act, 2025" if is_it_act_2025 else "Income-tax Act, 1961"

    return {
        "fy_label": fy_label,
        "ay_label": ay_label,
        "tax_year_label": ty_label,
        "governing_direct_tax_act": governing_act,
        "is_income_tax_act_2025": is_it_act_2025,
        "is_leap_year_period": calendar.isleap(fy_end_year),
        "fy_start": fy_start,
        "fy_end": fy_end,
        "fy_start_year": fy_start_year,
        "fy_end_year": fy_end_year,
        "ay_start_year": ay_start_year,
        "ay_end_year": ay_end_year
    }


def evaluate_cross_period_tds_transition(
    accrual_date: date,
    payment_date: date,
    remittance_date: date,
    section: str = "194J",
    gross_amount: Decimal = Decimal("100000.00"),
    tds_rate_percent: Decimal = Decimal("10.00")
) -> Dict[str, Any]:
    """
    UAT-11 & Section 4 Direct Tax Transition Evaluator:
    Handles transactions spanning the 31 March 2026 (Income-tax Act, 1961) to
    1 April 2026 (Income-tax Act, 2025) statutory boundary.
    """
    accrual_meta = calculate_indian_fy_ay(accrual_date)
    payment_meta = calculate_indian_fy_ay(payment_date)
    tds_trigger_date = min(accrual_date, payment_date)
    trigger_meta = calculate_indian_fy_ay(tds_trigger_date)

    tds_amount = (gross_amount * tds_rate_percent / Decimal("100.00")).quantize(Decimal("0.01"))
    crosses_2025_act_boundary = (
        accrual_date < INCOME_TAX_ACT_2025_EFFECTIVE_DATE <= payment_date
    ) or (
        accrual_date < INCOME_TAX_ACT_2025_EFFECTIVE_DATE <= remittance_date
    )

    # Under Sec 40(a)(ia) of IT Act 1961 (and transitional savings under IT Act 2025),
    # TDS deducted in FY 2025-26 is allowable in FY 2025-26 if deposited on or before ITR due date (Oct 31, 2026).
    itr_due_for_accrual_fy = date(accrual_meta["fy_end_year"], 10, 31)
    allowable_in_accrual_period = remittance_date <= itr_due_for_accrual_fy

    return {
        "accrual_date": accrual_date,
        "payment_date": payment_date,
        "remittance_date": remittance_date,
        "tds_trigger_date": tds_trigger_date,
        "accrual_governing_act": accrual_meta["governing_direct_tax_act"],
        "payment_governing_act": payment_meta["governing_direct_tax_act"],
        "crosses_act_2025_transition": crosses_2025_act_boundary,
        "deduction_period_fy": trigger_meta["fy_label"],
        "deduction_period_ay": trigger_meta["ay_label"],
        "deduction_tax_year": trigger_meta["tax_year_label"],
        "tds_amount": tds_amount,
        "allowable_in_accrual_fy": allowable_in_accrual_period,
        "disallowance_30_percent_triggered": not allowable_in_accrual_period,
        "transitional_provision_applied": (
            "Income-tax Act, 2025 Transitional Savings: Liability accrued up to 31-Mar-2026 is assessed under AY 2026-27 (IT Act 1961) with TDS remittance credit tracked across transition."
            if crosses_2025_act_boundary
            else f"Single-regime evaluation under {trigger_meta['governing_direct_tax_act']}."
        )
    }


async def get_or_create_fiscal_year(db: AsyncSession, tenant_id: uuid.UUID, txn_date: date):
    """
    Resolves the exact FiscalYear database record for a given transaction date.
    Automatically provisions the fiscal year record if it does not yet exist.
    """
    from app.models.ledger import FiscalYear
    fy_data = calculate_indian_fy_ay(txn_date)
    
    query = select(FiscalYear).where(
        FiscalYear.tenant_id == tenant_id,
        FiscalYear.label == fy_data["fy_label"]
    )
    result = await db.execute(query)
    fy_record = result.scalar_one_or_none()

    if not fy_record:
        fy_record = FiscalYear(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            label=fy_data["fy_label"],
            assessment_year=fy_data["ay_label"],
            start_date=fy_data["fy_start"],
            end_date=fy_data["fy_end"],
            is_closed=False
        )
        db.add(fy_record)
        await db.flush()

    return fy_record


def parse_fy_start_year(fy_str: str) -> int:
    """
    Parses start year from formats like '2025-26', '2025-2026', 'FY 2025-26', 'FY 2025-2026'.
    """
    clean = fy_str.strip().upper().replace("FY", "").strip()
    match = re.search(r"(\d{4})[-/](\d{2,4})", clean)
    if match:
        return int(match.group(1))
    # Fallback if just 4 digits
    match_yr = re.search(r"(\d{4})", clean)
    if match_yr:
        return int(match_yr.group(1))
    raise ValueError(f"Invalid Indian Financial Year format: '{fy_str}'")


def format_fy(start_year: int, full_year: bool = False) -> str:
    end_year = start_year + 1
    if full_year:
        return f"{start_year}-{end_year}"
    return f"{start_year}-{str(end_year)[-2:]}"


def format_ay(start_year: int, full_year: bool = False) -> str:
    ay_start = start_year + 1
    ay_end = ay_start + 1
    if full_year:
        return f"{ay_start}-{ay_end}"
    return f"{ay_start}-{str(ay_end)[-2:]}"


def get_financial_year(dt: Optional[date] = None, full_year: bool = False) -> str:
    """
    Returns the Indian Financial Year (FY) for a given date.
    If dt is None, uses today's date.
    """
    target = dt or date.today()
    start_year = target.year if target.month >= 4 else target.year - 1
    return format_fy(start_year, full_year=full_year)


def get_assessment_year(dt: Optional[date] = None, full_year: bool = False) -> str:
    """
    Returns the Indian Assessment Year (AY) for a given date.
    AY is strictly FY + 1 year.
    """
    target = dt or date.today()
    start_year = target.year if target.month >= 4 else target.year - 1
    return format_ay(start_year, full_year=full_year)


def get_fy_date_bounds(fy_str: str) -> Tuple[date, date]:
    """
    Returns (start_date, end_date) for a given Financial Year string.
    Example: '2025-26' -> (date(2025, 4, 1), date(2026, 3, 31))
    """
    start_year = parse_fy_start_year(fy_str)
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def is_date_in_fy(tx_date: date, fy_str: str) -> bool:
    """
    Checks if a given date falls within the financial year bounds.
    """
    start_date, end_date = get_fy_date_bounds(fy_str)
    return start_date <= tx_date <= end_date


def validate_date_in_fy(tx_date: date, active_fy: str) -> bool:
    """
    Validates that a transaction date falls strictly within the active Financial Year.
    Raises ValueError with standard regulatory text if outside bounds.
    """
    if not is_date_in_fy(tx_date, active_fy):
        start_year = parse_fy_start_year(active_fy)
        short_fy = f"{start_year}-{str(start_year + 1)[-2:]}"
        raise ValueError(
            f"Invoice date does not fall within the selected Financial Year ({short_fy})"
        )
    return True


def is_prior_period(active_fy: str, current_date: Optional[date] = None) -> bool:
    """
    Determines if the selected FY is prior to the current system date's active FY.
    """
    now = current_date or date.today()
    current_fy_start = now.year if now.month >= 4 else now.year - 1
    selected_fy_start = parse_fy_start_year(active_fy)
    return selected_fy_start < current_fy_start


def resolve_fiscal_calendar(current_date: Optional[date] = None, selected_fy: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns a comprehensive fiscal calendar metadata dictionary:
    - current system date
    - system active FY and AY
    - selected FY and AY
    - is_prior_period
    - date bounds
    - available FY choices
    """
    now = current_date or date.today()
    system_start_yr = now.year if now.month >= 4 else now.year - 1
    
    current_fy_short = format_fy(system_start_yr, full_year=False)
    current_fy_full = format_fy(system_start_yr, full_year=True)
    current_ay_short = format_ay(system_start_yr, full_year=False)
    current_ay_full = format_ay(system_start_yr, full_year=True)
    
    sel_start_yr = parse_fy_start_year(selected_fy) if selected_fy else system_start_yr
    sel_fy_short = format_fy(sel_start_yr, full_year=False)
    sel_fy_full = format_fy(sel_start_yr, full_year=True)
    sel_ay_short = format_ay(sel_start_yr, full_year=False)
    sel_ay_full = format_ay(sel_start_yr, full_year=True)
    
    start_dt, end_dt = get_fy_date_bounds(sel_fy_short)
    prior_mode = sel_start_yr < system_start_yr
    
    # Available FYs: 2 prior, current, 1 future
    available_fys: List[Dict[str, Any]] = []
    for yr in range(system_start_yr - 2, system_start_yr + 2):
        available_fys.append({
            "start_year": yr,
            "end_year": yr + 1,
            "fy_code": format_fy(yr, full_year=False),
            "fy_label": f"FY {format_fy(yr, full_year=False)}",
            "fy_full": f"FY {format_fy(yr, full_year=True)}",
            "ay_code": format_ay(yr, full_year=False),
            "ay_label": f"AY {format_ay(yr, full_year=False)}",
            "is_current": (yr == system_start_yr),
            "is_prior": (yr < system_start_yr)
        })
        
    return {
        "current_date": now.isoformat(),
        "system_fy": current_fy_short,
        "system_fy_full": current_fy_full,
        "system_ay": current_ay_short,
        "system_ay_full": current_ay_full,
        "active_fy": sel_fy_short,
        "active_fy_full": sel_fy_full,
        "active_ay": sel_ay_short,
        "active_ay_full": sel_ay_full,
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "is_prior_period": prior_mode,
        "warning_banner": (
            f"Prior Period Active (FY {sel_fy_short} | AY {sel_ay_short}). Books are in Closing Mode."
            if prior_mode else None
        ),
        "available_fys": available_fys
    }
