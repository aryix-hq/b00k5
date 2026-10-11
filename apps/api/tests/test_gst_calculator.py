from decimal import Decimal
from app.services.gst_calculator import (
    calculate_tax_breakdown,
    validate_gstin_checksum,
    COMMON_HSN_SAC
)

def test_gstin_checksum_validation():
    # Valid Indian GSTIN format with valid Modulus 36 checksum
    # Format: 29 (KA) + AABCA1234A (PAN) + 1 + Z + F (Check Digit)
    assert validate_gstin_checksum("29AABCA1234A1ZF") is True
    # Invalid length
    assert validate_gstin_checksum("29AABCA1234A") is False
    # Invalid characters
    assert validate_gstin_checksum("INVALIDGSTIN123") is False

def test_intrastate_gst_calculation():
    # Company operating state: 29 (Karnataka), Place of Supply: 29 (Karnataka)
    # Intra-state: 18% should split into CGST 9% + SGST 9%
    res = calculate_tax_breakdown(
        operating_state="29",
        place_of_supply="29",
        taxable_value=Decimal("100000.00"),
        gst_rate_percent=Decimal("18.00")
    )
    assert res["is_interstate"] is False
    assert res["cgst_rate"] == Decimal("9.00")
    assert res["sgst_rate"] == Decimal("9.00")
    assert res["igst_rate"] == Decimal("0.00")
    assert res["cgst_amount"] == Decimal("9000.00")
    assert res["sgst_amount"] == Decimal("9000.00")
    assert res["igst_amount"] == Decimal("0.00")
    assert res["total_tax"] == Decimal("18000.00")
    assert res["total_amount"] == Decimal("118000.00")

def test_interstate_gst_calculation():
    # Company operating state: 29 (Karnataka), Place of Supply: 07 (Delhi)
    # Inter-state: 18% should be IGST 18%
    res = calculate_tax_breakdown(
        operating_state="29",
        place_of_supply="07",
        taxable_value=Decimal("200000.00"),
        gst_rate_percent=Decimal("18.00")
    )
    assert res["is_interstate"] is True
    assert res["cgst_rate"] == Decimal("0.00")
    assert res["sgst_rate"] == Decimal("0.00")
    assert res["igst_rate"] == Decimal("18.00")
    assert res["cgst_amount"] == Decimal("0.00")
    assert res["sgst_amount"] == Decimal("0.00")
    assert res["igst_amount"] == Decimal("36000.00")
    assert res["total_tax"] == Decimal("36000.00")
    assert res["total_amount"] == Decimal("236000.00")
