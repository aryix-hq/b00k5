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
