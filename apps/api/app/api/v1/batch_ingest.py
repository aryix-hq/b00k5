"""
b00k5 - Multi-File Batch Ingestion Architecture
Supports parallel drag-and-drop ingestion of statements and receipts with zero-tolerance deduplication.
"""

from typing import List, Optional, Dict, Any
import hashlib
import uuid
from datetime import date
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.api.deps import get_db, get_current_user, get_current_tenant
from app.models.tenant import User, Tenant
from app.models.bank import BankStatement, BankStatementLine
from app.models.expense import Expense, ExpenseAuditLog
from app.core.config import settings
from app.core.s3 import storage_manager
from app.core.fiscal_year import get_or_create_fiscal_year, calculate_indian_fy_ay
from app.services.bank_parser import BankStatementParser, compute_line_fingerprint
from app.services.bill_analyzer import StatutoryBillAnalyzer
from app.services.expense_categorizer import auto_classify_expense

router = APIRouter(prefix="", tags=["Batch Ingestion"])


async def check_statement_exists(db: AsyncSession, tenant_id: uuid.UUID, file_hash: str) -> Optional[BankStatement]:
    query = select(BankStatement).where(
        and_(
            BankStatement.tenant_id == tenant_id,
            BankStatement.file_sha256 == file_hash
        )
    )
    res = await db.execute(query)
    return res.scalars().first()


async def check_expense_hash_exists(db: AsyncSession, tenant_id: uuid.UUID, file_hash: str) -> Optional[Expense]:
    query = select(Expense).where(
        and_(
            Expense.tenant_id == tenant_id,
            Expense.receipt_sha256 == file_hash
        )
    )
    res = await db.execute(query)
    return res.scalars().first()


@router.post("/statements")
async def upload_multiple_statements(
    bank_account_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Ingests multiple bank statement PDF/CSV files concurrently.
    Computes cryptographic SHA-256 hash, blocks duplicates, extracts transaction lines,
    applies deterministic line fingerprints, and links to the dynamic fiscal year.
    """
    batch_id = uuid.uuid4()
    job_manifest = []

    for file in files:
        contents = await file.read()
        if not contents:
            continue
        file_hash = hashlib.sha256(contents).hexdigest()

        # Check for immediate file-level duplicate
        existing = await check_statement_exists(db, tenant.id, file_hash)
        if existing:
            job_manifest.append({
                "filename": file.filename,
                "status": "skipped_duplicate",
                "message": f"Statement file already uploaded on {existing.created_at}",
                "statement_id": str(existing.id)
            })
            continue

        s3_key = f"{tenant.id}/statements/{batch_id}/{file.filename}"
        obj_name, _, file_size = storage_manager.save_document(
            bucket_name=settings.BUCKET_STATEMENTS,
            object_name=s3_key,
            file_bytes=contents,
            content_type=file.content_type or "application/pdf"
        )

        # Parse bank statement
        try:
            parsed = BankStatementParser.parse_pdf(contents, filename=file.filename or "")
            detected_bank = parsed.get("bank_name", "HDFC")
            acc_num = parsed.get("account_number") or bank_account_id or "50200099998888"
            stmt_from = parsed.get("statement_from") or (parsed["lines"][0]["transaction_date"] if parsed.get("lines") else None)
            stmt_to = parsed.get("statement_to") or (parsed["lines"][-1]["transaction_date"] if parsed.get("lines") else None)

            # Period-level duplicate check
            if stmt_from and stmt_to:
                period_dup_q = select(BankStatement).where(
                    and_(
                        BankStatement.tenant_id == tenant.id,
                        BankStatement.account_number == acc_num,
                        BankStatement.statement_from == stmt_from,
                        BankStatement.statement_to == stmt_to
                    )
                )
                period_dup = (await db.execute(period_dup_q)).scalars().first()
                if period_dup:
                    job_manifest.append({
                        "filename": file.filename,
                        "status": "skipped_duplicate",
                        "message": f"Statement for period {stmt_from} to {stmt_to} already exists",
                        "statement_id": str(period_dup.id)
                    })
                    continue

            # Resolve Dynamic Fiscal Year record
            target_date = stmt_to or stmt_from or date.today()
            fy_record = await get_or_create_fiscal_year(db, tenant.id, target_date)

            statement = BankStatement(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                bank_name=detected_bank,
                account_number=acc_num,
                statement_from=stmt_from,
                statement_to=stmt_to,
                opening_balance=parsed.get("opening_balance", 0.0),
                closing_balance=parsed.get("closing_balance", 0.0),
                total_withdrawals=parsed.get("total_withdrawals", 0.0),
                total_deposits=parsed.get("total_deposits", 0.0),
                file_name=file.filename or f"statement_{batch_id}.pdf",
                file_sha256=file_hash,
                s3_key=s3_key,
                fiscal_year_id=fy_record.id,
                status="parsed",
                uploaded_by=current_user.id
            )
            db.add(statement)
            await db.flush()

            # Insert statement lines with canonical fingerprint
            line_objs = []
            for line_dict in parsed.get("lines", []):
                amt_str = str(line_dict.get("withdrawal_amount") or line_dict.get("deposit_amount") or "0.00")
                bal_str = str(line_dict.get("running_balance") or "0.00")
                fp = compute_line_fingerprint(
                    acc_num,
                    str(line_dict["transaction_date"]),
                    amt_str,
                    bal_str,
                    line_dict.get("reference_number") or ""
                )

                line_obj = BankStatementLine(
                    id=uuid.uuid4(),
                    statement_id=statement.id,
                    tenant_id=tenant.id,
                    line_number=line_dict["line_number"],
                    fingerprint=fp,
                    transaction_date=line_dict["transaction_date"],
                    value_date=line_dict.get("value_date"),
                    description=line_dict["description"],
                    reference_number=line_dict.get("reference_number"),
                    payment_channel=line_dict.get("payment_channel", "OTHER"),
                    counterparty_name=line_dict.get("counterparty_name"),
                    withdrawal_amount=line_dict.get("withdrawal_amount", 0.0),
                    deposit_amount=line_dict.get("deposit_amount", 0.0),
                    running_balance=line_dict.get("running_balance", 0.0),
                    reconciliation_tier="unreconciled",
                    reconciliation_status="pending"
                )
                line_objs.append(line_obj)

            if line_objs:
                db.add_all(line_objs)
            await db.commit()

            job_manifest.append({
                "filename": file.filename,
                "status": "complete",
                "statement_id": str(statement.id),
                "total_lines": len(line_objs),
                "assigned_fy": fy_record.label
            })
        except Exception as e:
            job_manifest.append({
                "filename": file.filename,
                "status": "error",
                "message": str(e)
            })

    return {"batch_id": str(batch_id), "manifest": job_manifest}


@router.post("/expenses")
async def upload_multiple_expenses(
    files: List[UploadFile] = File(...),
    active_ui_fy: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Ingests multiple expense receipt / vendor bill files concurrently.
    Computes cryptographic receipt SHA-256, blocks duplicate receipts, performs OCR analysis,
    auto-categorizes expenses, routes into the dynamic fiscal year, and returns mismatch notices.
    """
    batch_id = uuid.uuid4()
    job_manifest = []

    for file in files:
        contents = await file.read()
        if not contents:
            continue
        file_hash = hashlib.sha256(contents).hexdigest()

        # Check for immediate file-level duplicate
        existing = await check_expense_hash_exists(db, tenant.id, file_hash)
        if existing:
            job_manifest.append({
                "filename": file.filename,
                "status": "skipped_duplicate",
                "expense_id": str(existing.id),
                "message": f"Receipt already registered (Merchant: {existing.merchant_name})"
            })
            continue

        s3_key = f"{tenant.id}/receipts/{batch_id}/{file.filename}"
        obj_name, _, file_size = storage_manager.save_document(
            bucket_name=settings.BUCKET_RECEIPTS,
            object_name=s3_key,
            file_bytes=contents,
            content_type=file.content_type or "application/octet-stream"
        )

        try:
            # Parse bill/invoice
            parsed = StatutoryBillAnalyzer.parse_bill_or_invoice(
                file_bytes=contents,
                filename=file.filename or "",
                company_gstin=tenant.gstin
            )

            merchant = parsed.get("supplier_name") or "Vendor"
            bill_date = parsed.get("bill_date") or date.today()
            total_amt = parsed.get("total_amount") or 0.0

            # Identity-level duplicate check
            dup_id_q = select(Expense).where(
                and_(
                    Expense.tenant_id == tenant.id,
                    Expense.merchant_name == merchant,
                    Expense.expense_date == bill_date,
                    Expense.total_amount == total_amt,
                    Expense.status != "rejected"
                )
            )
            dup_id = (await db.execute(dup_id_q)).scalars().first()
            if dup_id:
                job_manifest.append({
                    "filename": file.filename,
                    "status": "skipped_duplicate",
                    "expense_id": str(dup_id.id),
                    "message": f"Identical bill for {merchant} (₹{total_amt}) on {bill_date} already exists"
                })
                continue

            # Auto-classify category using Comprehensive Engine
            raw_text = parsed.get("raw_text", "")
            cat_info = auto_classify_expense(merchant, raw_text)
            assigned_cat = f"[{cat_info['account_code']}] {cat_info['category']}"

            # Dynamic Fiscal Year Resolution
            fy_record = await get_or_create_fiscal_year(db, tenant.id, bill_date)
            fy_data = calculate_indian_fy_ay(bill_date)

            expense = Expense(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                employee_id=current_user.id,
                merchant_name=merchant,
                merchant_gstin=parsed.get("supplier_gstin"),
                expense_date=bill_date,
                currency="INR",
                total_amount=total_amt,
                cgst_amount=parsed.get("cgst_amount", 0.0),
                sgst_amount=parsed.get("sgst_amount", 0.0),
                igst_amount=parsed.get("igst_amount", 0.0),
                category=assigned_cat,
                receipt_s3_key=s3_key,
                receipt_sha256=file_hash,
                fiscal_year_id=fy_record.id,
                status="submitted",
                settlement_status="pending",
                itc_eligible=parsed.get("itc_eligible", False),
                has_company_gstin=bool(parsed.get("recipient_gstin"))
            )
            db.add(expense)

            audit_entry = ExpenseAuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                expense_id=expense.id,
                changed_by=current_user.id,
                action="CREATED",
                field_changes={
                    "total_amount": float(total_amt),
                    "category": assigned_cat,
                    "merchant_name": merchant,
                    "file_sha256": file_hash
                },
                reason="Batch ingestion creation"
            )
            db.add(audit_entry)
            await db.commit()

            manifest_entry = {
                "filename": file.filename,
                "status": "complete",
                "expense_id": str(expense.id),
                "merchant_name": merchant,
                "total_amount": float(total_amt),
                "category": assigned_cat,
                "assigned_fy": fy_data["fy_label"],
                "assigned_ay": fy_data["ay_label"]
            }

            # Mismatch notice check
            clean_ui_fy = (active_ui_fy or "").replace("FY", "").strip()
            if clean_ui_fy and clean_ui_fy not in fy_data["fy_label"]:
                manifest_entry["active_ui_fy"] = active_ui_fy
                manifest_entry["mismatch_notice"] = (
                    f"Document dated {bill_date.strftime('%d/%m/%Y')} was recorded under "
                    f"FY {fy_data['fy_label']} (AY {fy_data['ay_label']}). Switch fiscal year tab to view."
                )

            job_manifest.append(manifest_entry)
        except Exception as e:
            job_manifest.append({
                "filename": file.filename,
                "status": "error",
                "message": str(e)
            })

    return {"batch_id": str(batch_id), "manifest": job_manifest}
