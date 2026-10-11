import asyncio
import os
import sys
import uuid
from pathlib import Path
from decimal import Decimal
try:
    import pytest
except ImportError:
    class _PytestShim:
        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(fn):
                return fn
            if len(args) == 1 and callable(args[0]):
                return args[0]
            return decorator

        class raises:
            def __init__(self, expected_exception):
                self.expected_exception = expected_exception
                self.value = None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    raise AssertionError(f"Expected exception {self.expected_exception}, but nothing was raised")
                if not issubclass(exc_type, self.expected_exception):
                    return False
                self.value = exc_val
                return True

    pytest = _PytestShim()

# Add apps/api and project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "apps/api"))
sys.path.insert(0, str(ROOT_DIR))

@pytest.fixture(autouse=True)
def cleanup_db_connections():
    yield
    try:
        from app.core.database import engine
        engine.sync_engine.dispose()
    except Exception:
        pass

@pytest.fixture
def fixtures_dir() -> Path:
    return ROOT_DIR / "tests/fixtures"

@pytest.fixture
def sample_statement_path(fixtures_dir) -> Path:
    return fixtures_dir / "sample_bank_statement.pdf"

@pytest.fixture
def sample_board_minutes_path(fixtures_dir) -> Path:
    return fixtures_dir / "sample_board_minutes.pdf"

@pytest.fixture
def sample_tax_invoice_path(fixtures_dir) -> Path:
    return fixtures_dir / "sample_tax_invoice.png"

@pytest.fixture
def tenant_1_data():
    return {
        "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "legal_name": "Acme Labs Pvt Ltd",
        "trade_name": "Acme Tech",
        "cin": "U72900KA2026PTC123456",
        "gstin": "29AABCA1234F1Z5",
        "pan": "AABCA1234F",
        "state_code": "29",
        "registered_office": "Indiranagar, 100 Feet Road, Bengaluru, Karnataka 560038",
        "directors": [
            {"name": "Vikram Sharma", "din": "09876541", "designation": "Director"},
            {"name": "Rohit Verma", "din": "09876542", "designation": "Managing Director"}
        ]
    }

@pytest.fixture
def tenant_2_data():
    return {
        "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
        "legal_name": "Zenith Commerce LLP",
        "trade_name": "Zenith Commerce",
        "cin": "U72900DL2024PTC199888",
        "gstin": "07AABCS9999K1ZE",
        "pan": "AABCS9999K",
        "state_code": "07",
        "registered_office": "Barakhamba Road, Connaught Place, New Delhi 110001",
        "directors": [
            {"name": "Siddharth Rao", "din": "09876544", "designation": "Partner"}
        ]
    }

@pytest.fixture
def schedule_iii_coa_fixture():
    from seed_data import SCHEDULE_III_COA
    return SCHEDULE_III_COA
