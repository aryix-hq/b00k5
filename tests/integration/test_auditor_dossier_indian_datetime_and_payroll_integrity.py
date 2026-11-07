import io
import csv
import zipfile
import re
import pytest
from decimal import Decimal
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.services.auditor_dossier_service import AuditorDossierService
from app.core.fiscal_year import format_indian_date, format_indian_datetime


@pytest.mark.asyncio
async def test_payroll_personnel_summary_zero_synthetic_data():
    """
    Financial & Statutory Integrity Invariant Test:
    Guarantees that AuditorDossierService Section 7 queries actual primary ledger
    records and NEVER fabricates synthetic payroll amounts (e.g. 35% of expenses / 11,730.89).
    """
    async with AsyncSessionLocal() as session:
        t_res = await session.execute(select(Tenant).where(Tenant.legal_name.ilike("%ARYIX%")))
        tenant = t_res.scalars().first()
        assert tenant is not None, "Tenant ARYIX not found in database"

        zip_bytes, filename = await AuditorDossierService.generate_auditor_dossier(
            db=session,
            tenant=tenant,
            fy="2026-27"
        )
        assert zip_bytes is not None
        assert filename == "Auditor_Dossier_ARYIX_OPC_PRIVATE_FY2026-27.zip"

        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        payroll_arc_name = "07_PAYROLL_PERSONNEL_AND_LABOR_LAW_COMPLIANCE/Payroll_And_Personnel_Summary_FY2026-27.csv"
        assert payroll_arc_name in zf.namelist(), f"{payroll_arc_name} missing from zip archive"

        payroll_csv_text = zf.read(payroll_arc_name).decode("utf-8-sig")

        # Absolute prohibition against synthetic 35% estimation
        assert "11730.89" not in payroll_csv_text, "CRITICAL DEFECT: Synthetic 11,730.89 payroll detected!"
        assert "1173.09" not in payroll_csv_text, "CRITICAL DEFECT: Synthetic 1,173.09 TDS detected!"

        reader = csv.DictReader(io.StringIO(payroll_csv_text))
        rows = list(reader)
        assert len(rows) >= 3, "Expected at least 3 categories: Salaried, Contractors, Directors"

        # Row 1: Salaried Personnel
        salaried_row = next(r for r in rows if "Salaried" in r["Category"])
        assert salaried_row["Head_Count"] == "0", "Headcount for salaried must be 0 for ARYIX OPC"
        assert salaried_row["Total_Gross_Disbursed_INR"] == "0.00", "Gross salaried must be 0.00"
        assert salaried_row["EPFO_PF_Deposited_INR"] == "0.00"
        assert salaried_row["ESIC_Deposited_INR"] == "0.00"
        assert salaried_row["PT_Deposited_INR"] == "0.00"
        assert salaried_row["TDS_Withheld_INR"] == "0.00"
        assert "NIL APPLICABILITY" in salaried_row["Compliance_Status"]

        # Row 2: Contractors
        contractor_row = next(r for r in rows if "Contractors" in r["Category"])
        assert contractor_row["Head_Count"] == "0", "Active contractor headcount must be 0 (struck-off payment)"
        assert contractor_row["Total_Gross_Disbursed_INR"] == "0.00"
        assert "NIL RETURN" in contractor_row["Compliance_Status"]

        # Row 3: Directors
        director_row = next(r for r in rows if "Directors" in r["Category"])
        assert director_row["Total_Gross_Disbursed_INR"] == "0.00"
        assert "NIL REMUNERATION DRAWN" in director_row["Compliance_Status"]


@pytest.mark.asyncio
async def test_statutory_labor_declaration_invariants():
    """
    Verifies Section 7 Statutory Labor Law & Payroll Applicability Declaration.
    Checks EPF (20 employee) and ESI (10 employee) statutory thresholds.
    """
    async with AsyncSessionLocal() as session:
        t_res = await session.execute(select(Tenant).where(Tenant.legal_name.ilike("%ARYIX%")))
        tenant = t_res.scalars().first()

        zip_bytes, _ = await AuditorDossierService.generate_auditor_dossier(
            db=session,
            tenant=tenant,
            fy="2026-27"
        )
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        decl_path = "07_PAYROLL_PERSONNEL_AND_LABOR_LAW_COMPLIANCE/Statutory_Labor_And_Payroll_Declaration.txt"
        assert decl_path in zf.namelist()

        decl_text = zf.read(decl_path).decode("utf-8")
        assert "STATUTORY LABOR LAW & PAYROLL APPLICABILITY DECLARATION" in decl_text
        assert "EMPLOYEES' PROVIDENT FUNDS AND MISCELLANEOUS PROVISIONS ACT, 1952" in decl_text
        assert "20 or more employees" in decl_text
        assert "EMPLOYEES' STATE INSURANCE ACT, 1948" in decl_text
        assert "10 or more employees" in decl_text
        assert "Zero synthetic, heuristic, or arbitrary estimations" in decl_text


@pytest.mark.asyncio
async def test_indian_date_and_time_formatting():
    """
    Statutory Standard Formatting Invariant Test:
    Verifies that dates across manifests, executive briefings, checklists,
    and CSV summaries strictly use Indian standard format (DD/MM/YYYY and IST).
    """
    async with AsyncSessionLocal() as session:
        t_res = await session.execute(select(Tenant).where(Tenant.legal_name.ilike("%ARYIX%")))
        tenant = t_res.scalars().first()

        zip_bytes, _ = await AuditorDossierService.generate_auditor_dossier(
            db=session,
            tenant=tenant,
            fy="2026-27"
        )
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

        # 1. Manifest
        manifest = zf.read("AUDIT_AUTHENTICITY_MANIFEST_SHA256.txt").decode("utf-8")
        assert "PERIOD COVERED: 01/04/2026 to 31/03/2027" in manifest
        assert re.search(r"GENERATION TIMESTAMP: \d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} (AM|PM) IST", manifest)

        # 2. Executive Briefing
        briefing = zf.read("00_EXECUTIVE_SUMMARY_AND_LEGAL_IDENTITY/01_Executive_Financial_And_Compliance_Briefing.txt").decode("utf-8")
        assert "Period Covered    : 01/04/2026 to 31/03/2027" in briefing
        assert re.search(r"As on Date        : \d{2}/\d{2}/\d{4}", briefing)

        # 3. Statutory Checklist
        checklist = zf.read("08_AUDIT_TRAIL_AND_CRYPTOGRAPHIC_INTEGRITY/STATUTORY_CLOSE_AND_MCA_CHECKLIST.txt").decode("utf-8")
        assert re.search(r"Export Timestamp  : \d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} (AM|PM) IST", checklist)

        # 4. Invoices CSV
        inv_csv = zf.read("05_OPERATIONS_REVENUE_AND_TRADE_RECEIVABLES/Invoices_Summary_FY2026-27.csv").decode("utf-8-sig")
        inv_reader = csv.DictReader(io.StringIO(inv_csv))
        for row in inv_reader:
            if row["Issue_Date"] and row["Issue_Date"] != "N/A":
                assert re.match(r"^\d{2}/\d{2}/\d{4}$", row["Issue_Date"]), f"Invoice Issue_Date not Indian format: {row['Issue_Date']}"
            if row["Due_Date"] and row["Due_Date"] != "N/A":
                assert re.match(r"^\d{2}/\d{2}/\d{4}$", row["Due_Date"]), f"Invoice Due_Date not Indian format: {row['Due_Date']}"

        # 5. Expenses CSV
        exp_csv = zf.read("06_OPERATIONS_EXPENSES_AND_TRADE_PAYABLES/Bills_Expenses_Summary_FY2026-27.csv").decode("utf-8-sig")
        exp_reader = csv.DictReader(io.StringIO(exp_csv))
        for row in exp_reader:
            if row["Expense_Date"] and row["Expense_Date"] != "N/A":
                assert re.match(r"^\d{2}/\d{2}/\d{4}$", row["Expense_Date"]), f"Expense Expense_Date not Indian format: {row['Expense_Date']}"

        # 6. Bank Statements CSV
        bank_csv = zf.read("04_BANKING_CASH_AND_TREASURY_RECONCILIATION/Bank_Statements_Register_FY2026-27.csv").decode("utf-8-sig")
        bank_reader = csv.DictReader(io.StringIO(bank_csv))
        for row in bank_reader:
            if row["Period_From"] and row["Period_From"] != "N/A":
                assert re.match(r"^\d{2}/\d{2}/\d{4}$", row["Period_From"]), f"Bank Period_From not Indian format: {row['Period_From']}"
            if row["Period_To"] and row["Period_To"] != "N/A":
                assert re.match(r"^\d{2}/\d{2}/\d{4}$", row["Period_To"]), f"Bank Period_To not Indian format: {row['Period_To']}"
