from datetime import date, timedelta
from decimal import Decimal
import uuid
from types import SimpleNamespace
from app.services.compliance_watchdog import ComplianceWatchdogService

def test_overdue_penalty_calculation():
    today = date(2026, 4, 15)
    # Event was due 10 days ago (April 5) with ₹100/day MCA fine
    ev = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        category="aoc_4",
        title="Form AOC-4 Financial Statements",
        description="Filing of audited Balance Sheet and P&L.",
        statutory_reference="Sec 137",
        completed_at=None,
        document_id=None,
        created_at=today,
        due_date=date(2026, 4, 5),
        fine_per_day_inr=Decimal("100.00"),
        status="upcoming"
    )

    metrics = ComplianceWatchdogService.calculate_event_metrics(ev, today)
    assert metrics["status"] == "overdue"
    assert metrics["days_remaining"] == -10
    # 10 days * ₹100 = ₹1,000 fine
    assert metrics["accumulated_penalty_inr"] == Decimal("1000.00")

def test_due_soon_status():
    today = date(2026, 4, 15)
    # Event is due in 8 days (April 23)
    ev = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        category="board_meeting_120d",
        title="Statutory Board Meeting (120-Day Rule)",
        description="120 day interval check.",
        statutory_reference="Sec 173(1)",
        completed_at=None,
        document_id=None,
        created_at=today,
        due_date=date(2026, 4, 23),
        fine_per_day_inr=Decimal("100.00"),
        status="upcoming"
    )

    metrics = ComplianceWatchdogService.calculate_event_metrics(ev, today)
    assert metrics["status"] == "due_soon"
    assert metrics["days_remaining"] == 8
    assert metrics["accumulated_penalty_inr"] == Decimal("0.00")


def test_advance_tax_corporate_regime_115baa():
    from app.services.advance_tax_service import AdvanceTaxService

    # Section 115BAA corporate regime: 22% base + 10% surcharge + 4% cess = 25.168% effective
    breakdown = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="PVT_LTD",
        projected_profit=Decimal("1000000.00"),  # 10 Lakhs profit
        annualized_turnover=Decimal("5000000.00"),
        selected_regime="sec_115baa_22"
    )

    assert breakdown["base_rate_pct"] == 22.0
    assert breakdown["surcharge_pct"] == 10.0
    assert breakdown["cess_pct"] == 4.0
    assert breakdown["effective_rate_pct"] == 25.168
    # Gross tax: 1,000,000 * 25.168% = 251,680.00
    assert Decimal(str(breakdown["gross_tax_amount"])) == Decimal("251680.00")


def test_advance_tax_llp_regime():
    from app.services.advance_tax_service import AdvanceTaxService

    # LLP flat 30% + 4% cess = 31.2% (under 1 Cr profit)
    breakdown = AdvanceTaxService.calculate_corporate_tax_breakdown(
        entity_type="LLP",
        projected_profit=Decimal("500000.00"),
        annualized_turnover=Decimal("2000000.00")
    )

    assert breakdown["base_rate_pct"] == 30.0
    assert breakdown["surcharge_pct"] == 0.0
    assert breakdown["effective_rate_pct"] == 31.2
    assert Decimal(str(breakdown["gross_tax_amount"])) == Decimal("156000.00")

