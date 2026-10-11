from datetime import date, datetime
from typing import Optional, Dict, Any
from pathlib import Path

CATEGORY_MAPPING = {
    "statements": "Bank_Statements",
    "bank_statements": "Bank_Statements",
    "receipts": "Receipts_and_Vouchers",
    "expenses": "Receipts_and_Vouchers",
    "statutory": "Statutory_and_Governance",
    "invoices": "Customer_Invoices",
    "sales": "Customer_Invoices",
    "vault": "Corporate_Records"
}

def get_indian_fiscal_year(target_date: Optional[date] = None) -> str:
    """
    Computes the Indian Financial Year (FY) for a given date.
    The Indian FY runs from April 1 to March 31.
    Examples:
        - 2026-01-15 -> 'FY_2025-2026'
        - 2026-03-31 -> 'FY_2025-2026'
        - 2026-04-01 -> 'FY_2026-2027'
        - 2026-10-10 -> 'FY_2026-2027'
    """
    d = target_date or date.today()
    if isinstance(d, datetime):
        d = d.date()

    if d.month >= 4:
        # April through December: current year to next year
        return f"FY_{d.year}-{d.year + 1}"
    else:
        # January through March: previous year to current year
        return f"FY_{d.year - 1}-{d.year}"

class DirectoryVirtualizer:
    """
    Directory virtualization engine mirroring local fiscal years and document categories
    into structured Google Drive hierarchy:
        LedgerFree_Archive / FY_YYYY-YYYY / [Category] / [File.pdf]
    """

    ROOT_FOLDER = "LedgerFree_Archive"

    @classmethod
    def sanitize_category(cls, category: str) -> str:
        key = category.lower().strip()
        return CATEGORY_MAPPING.get(key, category.replace(" ", "_").capitalize())

    @classmethod
    def build_virtual_path(
        cls,
        category: str,
        file_name: str,
        doc_date: Optional[date] = None,
        root_folder: Optional[str] = None
    ) -> str:
        """
        Builds canonical Google Drive virtual path.
        Example: LedgerFree_Archive/FY_2025-2026/Bank_Statements/HDFC_Statement_Jan2026.pdf
        """
        root = root_folder or cls.ROOT_FOLDER
        fy = get_indian_fiscal_year(doc_date)
        clean_cat = cls.sanitize_category(category)
        clean_file = Path(file_name).name
        return f"{root}/{fy}/{clean_cat}/{clean_file}"

    @classmethod
    def parse_virtual_path(cls, virtual_path: str) -> Dict[str, str]:
        """
        Parses a canonical virtual path into components:
        root, fiscal_year, category, file_name.
        """
        parts = [p for p in virtual_path.replace("\\", "/").split("/") if p]
        if len(parts) < 4:
            raise ValueError(f"Invalid virtual path format: {virtual_path}. Expected root/fy/category/filename")

        return {
            "root": parts[0],
            "fiscal_year": parts[1],
            "category": parts[2],
            "file_name": parts[3]
        }
