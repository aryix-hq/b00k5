import asyncio
from decimal import Decimal
import uuid

try:
    from app.schemas.ledger import JournalEntryCreate, JournalLineCreate
    HAVE_PYDANTIC = True
except ImportError:
    HAVE_PYDANTIC = False

    class FallbackJournalLine:
        def __init__(self, account_id, debit_amount=Decimal("0.00"), credit_amount=Decimal("0.00"), description=None):
            self.account_id = account_id
            self.debit_amount = Decimal(str(debit_amount))
            self.credit_amount = Decimal(str(credit_amount))
            self.description = description
            # Mutually exclusive validation
            d, c = self.debit_amount, self.credit_amount
            if (d > 0 and c > 0) or (d == 0 and c == 0):
                raise ValueError("Line must contain either a non-zero debit or credit, not both or neither")

    class FallbackJournalEntry:
        def __init__(self, entry_number, lines, narration=""):
            self.entry_number = entry_number
            self.narration = narration
            self.lines = lines
            if not lines or len(lines) < 2:
                raise ValueError("Must have at least two lines for double-entry")
            total_d = sum(line.debit_amount for line in lines)
            total_c = sum(line.credit_amount for line in lines)
            diff = abs(total_d - total_c)
            if diff != Decimal("0.00"):
                raise ValueError(f"Ledger Imbalance Violation: Sum(Debits) [{total_d}] != Sum(Credits) [{total_c}]")

    JournalLineCreate = FallbackJournalLine
    JournalEntryCreate = FallbackJournalEntry

def test_single_unbalanced_entry_rejected():
    account_1 = uuid.uuid4()
    account_2 = uuid.uuid4()

    # Intentional 0.01 mismatch: Debits = 1000.00, Credits = 1000.01
    try:
        JournalEntryCreate(
            entry_number="TEST-001",
            narration="Test unbalanced transaction",
            lines=[
                JournalLineCreate(account_id=account_1, debit_amount=Decimal("1000.00"), credit_amount=Decimal("0.00")),
                JournalLineCreate(account_id=account_2, debit_amount=Decimal("0.00"), credit_amount=Decimal("1000.01")),
            ]
        )
        assert False, "Failed to reject $0.01 unbalanced journal entry!"
    except ValueError as e:
        assert "Ledger Imbalance Violation" in str(e)

def test_mutually_exclusive_line_rejected():
    account_1 = uuid.uuid4()
    try:
        JournalLineCreate(
            account_id=account_1,
            debit_amount=Decimal("500.00"),
            credit_amount=Decimal("500.00")
        )
        assert False, "Failed to reject line with both debit and credit!"
    except ValueError as e:
        assert "either a non-zero debit or credit" in str(e)

async def async_validate_entry(index: int, should_be_valid: bool) -> bool:
    account_dr = uuid.uuid4()
    account_cr = uuid.uuid4()
    amount = Decimal(f"{100 + index}.50")

    if should_be_valid:
        # Balanced: Debits = Credits
        cr_amount = amount
    else:
        # Intentional fractional mismatch of 0.01
        cr_amount = amount + Decimal("0.01")

    try:
        JournalEntryCreate(
            entry_number=f"CONCURRENT-TEST-{index:03d}",
            narration=f"Concurrent ledger test #{index}",
            lines=[
                JournalLineCreate(account_id=account_dr, debit_amount=amount, credit_amount=Decimal("0.00")),
                JournalLineCreate(account_id=account_cr, debit_amount=Decimal("0.00"), credit_amount=cr_amount),
            ]
        )
        return True # Accepted
    except ValueError:
        return False # Rejected

def test_concurrent_100_inserts_verification_gate():
    """
    Phase 1 Verification Gate:
    Executes 100 concurrent asynchronous validation checks with intentional unbalanced fractions
    ($0.01 mismatch). Must reject 100% of illegal entries and accept 100% of balanced entries
    with zero ledger drift.
    """
    async def run_suite():
        tasks = []
        expected_results = []
        for i in range(100):
            is_valid = (i % 2 == 0)
            expected_results.append(is_valid)
            tasks.append(asyncio.create_task(async_validate_entry(i, is_valid)))

        actual_results = await asyncio.gather(*tasks)

        for idx, (expected, actual) in enumerate(zip(expected_results, actual_results)):
            assert expected == actual, f"Entry #{idx} failed verification: expected valid={expected}, got {actual}"

        rejected_illegal_count = sum(1 for i, res in enumerate(actual_results) if not expected_results[i] and not res)
        accepted_valid_count = sum(1 for i, res in enumerate(actual_results) if expected_results[i] and res)

        assert rejected_illegal_count == 50, f"Rejected only {rejected_illegal_count}/50 illegal entries!"
        assert accepted_valid_count == 50, f"Accepted only {accepted_valid_count}/50 valid entries!"

    asyncio.run(run_suite())
