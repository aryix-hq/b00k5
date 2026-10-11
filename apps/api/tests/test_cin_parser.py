from app.services.cin_service import parse_indian_cin

def test_valid_cin_lookup():
    res = parse_indian_cin("U72900KA2026PTC123456")
    assert res["is_valid"] is True
    assert res["listing_status"] == "Unlisted"
    assert res["industry_code"] == "72900"
    assert res["state_alpha"] == "KA"
    assert res["numeric_state_code"] == "29"
    assert res["state_name"] == "Karnataka"
    assert res["incorporation_year"] == 2026
    assert res["company_type"] == "Private Limited Company"
    assert res["registration_number"] == "123456"

def test_delhi_cin_lookup():
    res = parse_indian_cin("L74899DL1995PLC069876")
    assert res["is_valid"] is True
    assert res["listing_status"] == "Listed"
    assert res["state_alpha"] == "DL"
    assert res["numeric_state_code"] == "07"
    assert res["state_name"] == "Delhi"
    assert res["incorporation_year"] == 1995
    assert res["company_type"] == "Public Limited Company"
