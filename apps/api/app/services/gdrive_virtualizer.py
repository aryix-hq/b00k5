from datetime import date, datetime
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

CATEGORY_MAPPING = {
    "statements": "04_BANKING_CASH_AND_TREASURY_RECONCILIATION/Statements",
    "bank_statements": "04_BANKING_CASH_AND_TREASURY_RECONCILIATION/Statements",
    "receipts": "06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/Vendor_Bills",
    "expenses": "06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/Vendor_Bills",
    "statutory": "02_CORPORATE_GOVERNANCE_AND_SECRETARIAL_MCA/MCA_Annual_Filings",
    "invoices": "05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/Monthly_Sales_Invoices",
    "sales": "05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/Monthly_Sales_Invoices",
    "vault": "00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/Permanent_Records",
    "governance": "02_CORPORATE_GOVERNANCE_AND_SECRETARIAL_MCA/Board_Meetings_SS1",
    "tax": "03_TAX_COMPLIANCE_AND_STATUTORY_RETURNS/GST_And_Income_Tax",
    "payroll": "07_PAYROLL_PERSONNEL_AND_LABOR_LAW_COMPLIANCE/Payroll_Registers",
    "checkpoints": "checkpoints"
}

# Legacy mapping for backwards-compatibility
LEGACY_CATEGORY_MAPPING = {
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


def get_indian_fy_ay_label(target_date: Optional[date] = None) -> Tuple[str, str, str]:
    """
    Returns canonical Indian Financial Year and Assessment Year:
    - fy_label: '2025-26'
    - ay_label: '2026-27'
    - folder_name: 'FY 2025-26 (AY 2026-27)'
    """
    d = target_date or date.today()
    if isinstance(d, datetime):
        d = d.date()

    if d.month >= 4:
        start_year = d.year
        end_year = d.year + 1
    else:
        start_year = d.year - 1
        end_year = d.year

    fy_label = f"{start_year}-{str(end_year)[-2:]}"
    ay_label = f"{start_year + 1}-{str(end_year + 1)[-2:]}"
    folder_name = f"FY {fy_label} (AY {ay_label})"
    return fy_label, ay_label, folder_name


class DirectoryVirtualizer:
    """
    Directory virtualization engine mirroring local fiscal years and document categories
    into structured Google Drive and Cloudflare R2 / AWS S3 hierarchy:
        LedgerFree_Archive / FY_YYYY-YYYY / [Category] / [File.pdf]
    Also provides stakeholder-aligned dossier paths per MCA & ICAI rules.
    """

    ROOT_FOLDER = "LedgerFree_Archive"

    @classmethod
    def sanitize_category(cls, category: str, legacy: bool = True) -> str:
        key = category.lower().strip()
        if legacy:
            return LEGACY_CATEGORY_MAPPING.get(key, category.replace(" ", "_").capitalize())
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
        Builds canonical Google Drive virtual path (legacy format preserved for tests).
        Example: LedgerFree_Archive/FY_2025-2026/Bank_Statements/HDFC_Statement_Jan2026.pdf
        """
        root = root_folder or cls.ROOT_FOLDER
        fy = get_indian_fiscal_year(doc_date)
        clean_cat = cls.sanitize_category(category, legacy=True)
        clean_file = Path(file_name).name
        return f"{root}/{fy}/{clean_cat}/{clean_file}"

    @classmethod
    def build_statutory_dossier_path(
        cls,
        category: str,
        file_name: str,
        doc_date: Optional[date] = None,
        root_folder: Optional[str] = None
    ) -> str:
        """
        Builds stakeholder-aligned canonical FY/AY path for Cloud Backups and Google Drive:
        Example: b00k5_ARYIX/FY 2025-26 (AY 2026-27)/05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/Monthly_Sales_Invoices/INV_001.pdf
        """
        root = root_folder or cls.ROOT_FOLDER
        _, _, fy_folder = get_indian_fy_ay_label(doc_date)
        clean_cat = cls.sanitize_category(category, legacy=False)
        clean_file = Path(file_name).name

        if clean_cat.startswith("00_"):
            # Permanent records are stored at root level outside annual FY
            return f"{root}/{clean_cat}/{clean_file}"
        if clean_cat == "checkpoints":
            return f"{root}/checkpoints/{clean_file}"

        return f"{root}/{fy_folder}/{clean_cat}/{clean_file}"

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
