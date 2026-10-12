import io
import re
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

GSTIN_REGEX = re.compile(r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b')
INVOICE_NUM_REGEX = re.compile(r'(?:Invoice\s*No|Invoice\s*#|Bill\s*No|Bill\s*#|Inv\s*No|Inv\s*#|Tax\s*Invoice\s*No)[.:\s]*([A-Z0-9\-\/]+)', re.IGNORECASE)
DATE_REGEX_1 = re.compile(r'\b(\d{4}[-/]\d{2}[-/]\d{2})\b')
DATE_REGEX_2 = re.compile(r'\b(\d{2}[-/]\d{2}[-/]\d{4})\b')
AMOUNT_REGEX = re.compile(r'(?:Grand\s*Total|Total\s*Amount|Net\s*Payable|Invoice\s*Total|Total)[^\d\n]*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{2})?)', re.IGNORECASE)

class BillInvoiceParser:
    """
    Parser for vendor bills and customer outward invoices:
    - Extracts Merchant/Customer, Dates, Invoice/Bill Numbers, Line Items, Taxes (CGST, SGST, IGST)
    - Determines ITC eligibility based on company GSTIN
    - Decrypts password-protected PDFs (HDFC/ICICI/SBI/Axis/corporate style)
    - Checks for duplicate records in the ledger
    """

    @staticmethod
    def extract_text_from_pdf(file_bytes: bytes, password: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            if reader.is_encrypted:
                if not password:
                    return "", {
                        "needs_password": True,
                        "message": "This PDF document is password-protected. Please enter your password to unlock."
                    }
                try:
                    dec = reader.decrypt(password)
                    if dec == 0:
                        return "", {
                            "needs_password": True,
                            "message": "Incorrect password. Please verify and re-enter."
                        }
                except Exception:
                    return "", {
                        "needs_password": True,
                        "message": "Failed to decrypt PDF with the provided password."
                    }

            full_text = ""
            for page in reader.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"

            return full_text, None
        except Exception as e:
            # Fallback for plain text or ASCII
            try:
                decoded = file_bytes.decode("utf-8", errors="ignore")
                return decoded, None
            except Exception:
                return "", None

    @staticmethod
    def parse_vendor_bill(
        file_bytes: bytes,
        filename: str,
        password: Optional[str] = None,
        company_gstin: Optional[str] = None,
        closed_fiscal_years: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parses inward vendor bill (PDF or image) using the StatutoryBillAnalyzer model.
        Extracts merchant, bill #, date, amounts, taxes, validates Indian FY & Year Book.
        """
        from app.services.bill_analyzer import StatutoryBillAnalyzer
        return StatutoryBillAnalyzer.parse_bill_or_invoice(
            file_bytes=file_bytes,
            filename=filename,
            password=password,
            company_gstin=company_gstin,
            closed_fiscal_years=closed_fiscal_years,
            is_customer_invoice=False
        )

    @staticmethod
    def parse_customer_invoice(
        file_bytes: bytes,
        filename: str,
        password: Optional[str] = None,
        company_gstin: Optional[str] = None,
        closed_fiscal_years: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parses outward customer invoice (PDF/image) using the StatutoryBillAnalyzer model.
        Extracts invoice #, issue date, customer name, GSTIN, place of supply, taxable amount, tax, and total.
        """
        from app.services.bill_analyzer import StatutoryBillAnalyzer
        return StatutoryBillAnalyzer.parse_bill_or_invoice(
            file_bytes=file_bytes,
            filename=filename,
            password=password,
            company_gstin=company_gstin,
            closed_fiscal_years=closed_fiscal_years,
            is_customer_invoice=True
        )

    @staticmethod
    async def check_expense_duplicate(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        merchant_name: str,
        total_amount: Decimal,
        expense_date: Optional[Any] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Deduplication check against existing active expenses in the ledger.
        Normalizes vendor names (e.g. discarding 'Regd Office:' / 'M/s') and matches amount + date.
        """
        from app.models.expense import Expense
        if not merchant_name or total_amount <= Decimal("0.00"):
            return False, None

        exp_d = None
        if isinstance(expense_date, str):
            try:
                exp_d = datetime.strptime(expense_date, "%Y-%m-%d").date()
            except Exception:
                pass
        elif isinstance(expense_date, date):
            exp_d = expense_date

        conditions = [
            Expense.tenant_id == tenant_id,
            Expense.status != "struck_off",
            Expense.total_amount == total_amount
        ]
        if exp_d:
            conditions.append(Expense.expense_date == exp_d)

        stmt = select(Expense).where(and_(*conditions))
        res = await session.execute(stmt)
        existing_candidates = res.scalars().all()

        clean_new = re.sub(r'^(regd\s*office:?|m/s\.?)\s*', '', merchant_name.strip().lower())
        for existing in existing_candidates:
            clean_exist = re.sub(r'^(regd\s*office:?|m/s\.?)\s*', '', (existing.merchant_name or "").strip().lower())
            if clean_new == clean_exist or (len(clean_new) > 4 and clean_new in clean_exist) or (len(clean_exist) > 4 and clean_exist in clean_new):
                return True, f"Duplicate bill detected: An active expense for '{existing.merchant_name}' amounting to ₹{total_amount:,.2f} on {existing.expense_date} already exists in your sovereign ledger."

        return False, None
