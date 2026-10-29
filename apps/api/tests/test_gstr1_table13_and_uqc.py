import pytest
from datetime import date
from decimal import Decimal
import uuid
from unittest.mock import MagicMock

from app.core.uqc import (
    GSTN_UQC_CATALOG,
    is_service_hsn,
    resolve_uqc,
    validate_uqc
)
from app.services.gstr1_service import (
    parse_doc_series,
    compile_gstr1_table_13,
    DOC_NATURE_MAP
)


class MockInvoice:
    def __init__(self, invoice_number, inv_type="tax_invoice", status="posted", issue_date=None):
        self.id = uuid.uuid4()
        self.invoice_number = invoice_number
        self.type = inv_type
        self.status = status
        self.issue_date = issue_date or date(2026, 9, 15)


def test_uqc_catalog_and_service_invariants():
    """Validates GSTN UQC catalog rules: Chapter 99 must be NA, goods cannot be NA."""
    # 1. 44+ valid codes
    assert len(GSTN_UQC_CATALOG) >= 40
    assert "NA" in GSTN_UQC_CATALOG
    assert "NOS" in GSTN_UQC_CATALOG
    assert "BOX" in GSTN_UQC_CATALOG

    # 2. Service detection
    assert is_service_hsn("998314") is True
    assert is_service_hsn("996812") is True
    assert is_service_hsn("847130") is False
    assert is_service_hsn("1001") is False

    # 3. UQC resolution
    assert resolve_uqc("998314", "BOX") == "NA"
    assert resolve_uqc("998314", None) == "NA"
    assert resolve_uqc("847130", "BOX") == "BOX"
    assert resolve_uqc("847130", "NA") == "NOS" # Goods cannot be NA
    assert resolve_uqc("847130", None) == "NOS" # Defaults to NOS

    # 4. Strict validation
    ok, err = validate_uqc("998314", "NA")
    assert ok is True

    ok, err = validate_uqc("998314", "NOS")
    assert ok is False
    assert "must strictly report UQC as 'NA'" in err

    ok, err = validate_uqc("847130", "NA")
    assert ok is False
    assert "cannot have UQC as 'NA'" in err

    ok, err = validate_uqc("847130", "KGS")
    assert ok is True


def test_doc_series_decomposition():
    """Validates regex decomposition of complex Indian invoice numbering formats."""
    p, v, s = parse_doc_series("INV/2026-27/0042")
    assert p == "INV/2026-27/"
    assert v == 42
    assert s == ""

    p, v, s = parse_doc_series("CN-2026-005-B")
    assert p == "CN-2026-"
    assert v == 5
    assert s == "-B"

    p, v, s = parse_doc_series("EST101")
    assert p == "EST"
    assert v == 101
    assert s == ""

    p, v, s = parse_doc_series("NO_NUMBER")
    assert p == "NO_NUMBER"
    assert v == 0
    assert s == ""


def test_gstr1_table13_multi_series_and_cancellations():
    """Validates Table 13 range grouping, cancellation math, and multi-series isolation."""
    invoices = [
        # Series 1: Standard Inward Supply (INV/2026/001 to 004, with 003 cancelled)
        MockInvoice("INV/2026/001", "tax_invoice", "posted", date(2026, 9, 1)),
        MockInvoice("INV/2026/002", "tax_invoice", "posted", date(2026, 9, 2)),
        MockInvoice("INV/2026/003", "tax_invoice", "cancelled", date(2026, 9, 3)),
        MockInvoice("INV/2026/004", "tax_invoice", "posted", date(2026, 9, 4)),

        # Series 2: Export Invoices (EXP/2026/001 to 002)
        MockInvoice("EXP/2026/001", "export_invoice", "posted", date(2026, 9, 5)),
        MockInvoice("EXP/2026/002", "export_invoice", "posted", date(2026, 9, 6)),

        # Credit Notes (doc_num 5)
        MockInvoice("CN/2026/001", "credit_note", "posted", date(2026, 9, 7)),
        MockInvoice("CN/2026/002", "credit_note", "posted", date(2026, 9, 8)),

        # Debit Note (doc_num 4)
        MockInvoice("DN/2026/001", "debit_note", "posted", date(2026, 9, 9)),

        # Delivery Challan (doc_num 12)
        MockInvoice("DC/2026/001", "delivery_challan", "posted", date(2026, 9, 10)),
    ]

    table13 = compile_gstr1_table_13(invoices)
    doc_det = table13["doc_det"]

    # Must contain doc_num: 1, 4, 5, 12
    doc_nums = [d["doc_num"] for d in doc_det]
    assert doc_nums == [1, 4, 5, 12]

    # Inspect doc_num 1 (Invoices for outward supply)
    inv_group = next(d for d in doc_det if d["doc_num"] == 1)
    assert inv_group["doc_typ"] == "Invoices for outward supply"
    assert len(inv_group["docs"]) == 2 # 2 distinct series: INV and EXP

    docs_by_prefix = {r["from"][:3]: r for r in inv_group["docs"]}
    row_inv = docs_by_prefix["INV"]
    assert row_inv["from"] == "INV/2026/001"
    assert row_inv["to"] == "INV/2026/004"
    assert row_inv["totnum"] == 4
    assert row_inv["canc"] == 1
    assert row_inv["net_issue"] == 3

    row_exp = docs_by_prefix["EXP"]
    assert row_exp["from"] == "EXP/2026/001"
    assert row_exp["to"] == "EXP/2026/002"
    assert row_exp["totnum"] == 2
    assert row_exp["canc"] == 0
    assert row_exp["net_issue"] == 2

    # Inspect doc_num 4 (Debit Note)
    dn_group = next(d for d in doc_det if d["doc_num"] == 4)
    assert dn_group["doc_typ"] == "Debit Note"
    assert len(dn_group["docs"]) == 1
    assert dn_group["docs"][0]["from"] == "DN/2026/001"
    assert dn_group["docs"][0]["to"] == "DN/2026/001"
    assert dn_group["docs"][0]["totnum"] == 1
    assert dn_group["docs"][0]["canc"] == 0
    assert dn_group["docs"][0]["net_issue"] == 1

    # Inspect doc_num 5 (Credit Note)
    cn_group = next(d for d in doc_det if d["doc_num"] == 5)
    assert cn_group["doc_typ"] == "Credit Note"
    assert len(cn_group["docs"]) == 1
    assert cn_group["docs"][0]["from"] == "CN/2026/001"
    assert cn_group["docs"][0]["to"] == "CN/2026/002"
    assert cn_group["docs"][0]["totnum"] == 2
    assert cn_group["docs"][0]["canc"] == 0
    assert cn_group["docs"][0]["net_issue"] == 2

    # Inspect doc_num 12 (Delivery Challan)
    dc_group = next(d for d in doc_det if d["doc_num"] == 12)
    assert dc_group["doc_typ"] == "Delivery Challan in cases other than by way of supply"
    assert len(dc_group["docs"]) == 1
    assert dc_group["docs"][0]["from"] == "DC/2026/001"
    assert dc_group["docs"][0]["to"] == "DC/2026/001"
    assert dc_group["docs"][0]["totnum"] == 1


def test_gstr1_table13_sequence_gap_splitting():
    """Validates that a non-contiguous jump in invoice numbering spawns separate range entries."""
    invoices = [
        MockInvoice("INV/001", "tax_invoice", "posted"),
        MockInvoice("INV/002", "tax_invoice", "posted"),
        MockInvoice("INV/003", "tax_invoice", "posted"),
        # Big gap to 050
        MockInvoice("INV/050", "tax_invoice", "posted"),
        MockInvoice("INV/051", "tax_invoice", "posted"),
    ]

    table13 = compile_gstr1_table_13(invoices)
    docs = table13["doc_det"][0]["docs"]
    assert len(docs) == 2

    assert docs[0]["from"] == "INV/001"
    assert docs[0]["to"] == "INV/003"
    assert docs[0]["totnum"] == 3
    assert docs[0]["net_issue"] == 3

    assert docs[1]["from"] == "INV/050"
    assert docs[1]["to"] == "INV/051"
    assert docs[1]["totnum"] == 2
    assert docs[1]["net_issue"] == 2
