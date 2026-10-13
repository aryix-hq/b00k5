from typing import List, Optional, Dict, Any
import uuid
import hashlib
from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user, get_current_tenant
from app.models.tenant import User, Tenant
from app.models.bank import BankStatement, BankStatementLine
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.schemas.bank import (
    BankStatementResponse, BankStatementLineResponse,
    ConfirmMatchRequest, AllocateSuspenseRequest, ReconciliationSummaryResponse
)
from app.services.bank_parser import IndianBankPDFParser, compute_line_fingerprint
from app.services.reconciliation_engine import ReconciliationEngine
from app.services.ledger_service import LedgerService
from app.core.fiscal_year import get_or_create_fiscal_year, calculate_indian_fy_ay
from app.core.s3 import upload_document
from app.core.config import settings

router = APIRouter()

@router.post("/upload")
@router.post("/upload-statement")
async def upload_bank_statement(
    file: UploadFile = File(...),
    bank_name: str = Form("HDFC"),
    account_number: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests an Indian bank statement PDF, saves to MinIO 'b00k5-statements',
    extracts lines with IndianBankPDFParser (supporting encrypted/password-protected PDFs),
    and registers for 3-tier reconciliation.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty statement file uploaded")
    from app.services.bank_parser import validate_uploaded_document_safety
    safety = validate_uploaded_document_safety(file.filename or "statement.pdf", file_bytes, file.content_type)
    if not safety.get("is_safe"):
        raise HTTPException(status_code=400, detail=f"Statement rejected by security scanner: {safety.get('reason')}")
    safe_filename = safety.get("sanitized_filename") or (file.filename or "statement.pdf")

    # Check for encryption / parse lines (handles PDF and image formats)
    parsed = IndianBankPDFParser.parse_file_bytes(file_bytes, filename=safe_filename, password=password)
    if parsed.get("needs_password"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "needs_password": True,
                "message": parsed.get("error", "Bank statement PDF is password-protected. Please enter your account password to unlock.")
            }
        )

    s3_key = f"{tenant.id}/statements/{safe_filename}"

    # 1. Upload to isolated statements bucket
    try:
        upload_document(
            bucket_name=settings.BUCKET_STATEMENTS,
            file_bytes=file_bytes,
            object_name=s3_key,
            content_type=file.content_type or "application/pdf"
        )
    except Exception:
        pass

    detected_bank = bank_name if bank_name != "OTHER" else (parsed.get("bank_name") or "HDFC")
    acc_num = account_number or parsed.get("account_number") or "XXXX001"

    # 2. Update tenant statutory profile & Chart of Accounts with recognized bank info
    try:
        profile = dict(tenant.statutory_profile or {})
        primary_bank = dict(profile.get("primary_bank_account", {}))
        primary_bank["bank_name"] = detected_bank
        primary_bank["account_number"] = acc_num
        if parsed.get("ifsc"):
            primary_bank["ifsc"] = parsed["ifsc"]
        if parsed.get("micr"):
            primary_bank["micr"] = parsed["micr"]
        if parsed.get("branch"):
            primary_bank["branch"] = parsed["branch"]
        if parsed.get("customer_id"):
            primary_bank["customer_id"] = parsed["customer_id"]
        if parsed.get("account_name"):
            primary_bank["account_holder_name"] = parsed["account_name"]
        profile["primary_bank_account"] = primary_bank
        tenant.statutory_profile = profile

        # Synchronize Chart of Accounts Code 1010
        coa_stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.tenant_id == tenant.id,
            ChartOfAccounts.code == "1010"
        )
        coa_res = await db.execute(coa_stmt)
        bank_coa = coa_res.scalar_one_or_none()
        if bank_coa:
            short_acc = acc_num[-4:] if len(acc_num) > 4 else acc_num
            bank_coa.name = f"Bank Current Account ({detected_bank} - {short_acc})"
            bank_coa.description = f"Primary business checking account: {detected_bank} A/C {acc_num} (IFSC: {parsed.get('ifsc', 'N/A')})"
    except Exception as e:
        pass

    # 3. Compute Cryptographic File Hash and Check Deduplication
    file_sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Inviolable Deduplication Check: Block duplicate bank statements by hash or period
    hash_dup_stmt = select(BankStatement).where(
        and_(
            BankStatement.tenant_id == tenant.id,
            BankStatement.file_sha256 == file_sha256
        )
    )
    if (await db.execute(hash_dup_stmt)).scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate statement file detected: File '{file.filename}' with identical hash has already been uploaded."
        )

    stmt_from = parsed.get("statement_from") or (parsed["lines"][0]["transaction_date"] if parsed.get("lines") else None)
    stmt_to = parsed.get("statement_to") or (parsed["lines"][-1]["transaction_date"] if parsed.get("lines") else None)

    dup_stmt_conds = [BankStatement.tenant_id == tenant.id]
    if stmt_from and stmt_to:
        dup_stmt_conds.append(
            and_(
                BankStatement.account_number == acc_num,
                BankStatement.statement_from == stmt_from,
                BankStatement.statement_to == stmt_to
            )
        )
    else:
        dup_stmt_conds.append(BankStatement.file_name == file.filename)

    dup_stmt = select(BankStatement).where(and_(*dup_stmt_conds))
    existing_stmt = (await db.execute(dup_stmt)).scalars().first()
    if existing_stmt:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate statement detected: A bank statement for account '{acc_num}' covering period {stmt_from or 'N/A'} to {stmt_to or 'N/A'} has already been uploaded."
        )

    # Resolve Dynamic Fiscal Year record
    target_date = stmt_to or stmt_from or date.today()
    fy_record = await get_or_create_fiscal_year(db, tenant.id, target_date)
    fy_data = calculate_indian_fy_ay(target_date)

    statement = BankStatement(
        tenant_id=tenant.id,
        bank_name=detected_bank,
        account_number=acc_num,
        statement_from=stmt_from,
        statement_to=stmt_to,
        opening_balance=parsed.get("opening_balance", Decimal("0.00")),
        closing_balance=parsed.get("closing_balance", Decimal("0.00")),
        total_withdrawals=parsed.get("total_withdrawals", Decimal("0.00")),
        total_deposits=parsed.get("total_deposits", Decimal("0.00")),
        file_name=file.filename,
        file_sha256=file_sha256,
        s3_key=s3_key,
        fiscal_year_id=fy_record.id,
        status="parsed",
        uploaded_by=current_user.id
    )
    db.add(statement)
    await db.flush()

    # 4. Insert Statement Lines with Deterministic Canonical Fingerprints
    lines = []
    parsed_transactions = []
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
            withdrawal_amount=line_dict.get("withdrawal_amount", Decimal("0.00")),
            deposit_amount=line_dict.get("deposit_amount", Decimal("0.00")),
            running_balance=line_dict.get("running_balance", Decimal("0.00")),
            reconciliation_tier="unreconciled",
            reconciliation_status="pending"
        )
        lines.append(line_obj)
        parsed_transactions.append({
            "id": str(uuid.uuid4()),
            "line_number": line_dict["line_number"],
            "date": str(line_dict["transaction_date"]),
            "description": line_dict["description"],
            "reference_number": line_dict.get("reference_number") or "",
            "payment_channel": line_dict.get("payment_channel", "OTHER"),
            "counterparty": line_dict.get("counterparty_name") or "Counterparty",
            "withdrawal": float(line_dict.get("withdrawal_amount", 0)),
            "deposit": float(line_dict.get("deposit_amount", 0)),
            "balance": float(line_dict.get("running_balance", 0)),
            "reconciliation_tier": "unreconciled",
            "status": "pending"
        })

    db.add_all(lines)
    await db.commit()
    await db.refresh(statement)

    # Automatically execute 3-tier reconciliation sweep
    try:
        await ReconciliationEngine.reconcile_statement(
            session=db,
            tenant_id=tenant.id,
            statement_id=statement.id,
            user_id=current_user.id
        )
        await db.commit()
    except Exception as e:
        await db.rollback()

    # Fetch updated lines from DB with real IDs, tiers, and statuses
    lines_stmt = select(BankStatementLine).where(
        BankStatementLine.statement_id == statement.id,
        BankStatementLine.tenant_id == tenant.id
    ).order_by(BankStatementLine.line_number)
    db_lines = (await db.execute(lines_stmt)).scalars().all()

    parsed_transactions = []
    for l in db_lines:
        parsed_transactions.append({
            "id": str(l.id),
            "line_number": l.line_number,
            "date": str(l.transaction_date),
            "description": l.description,
            "reference_number": l.reference_number or "",
            "payment_channel": l.payment_channel or "OTHER",
            "counterparty": l.counterparty_name or "Counterparty",
            "withdrawal": float(l.withdrawal_amount),
            "deposit": float(l.deposit_amount),
            "balance": float(l.running_balance),
            "reconciliation_tier": l.reconciliation_tier,
            "status": l.reconciliation_status,
            "confidence_score": float(l.confidence_score or 0),
            "notes": l.notes
        })

    # Return statement with both lines and parsed_transactions structure
    return {
        "id": str(statement.id),
        "statement_id": str(statement.id),
        "bank_name": statement.bank_name,
        "account_number": statement.account_number,
        "account_name": parsed.get("account_name"),
        "customer_id": parsed.get("customer_id"),
        "ifsc": parsed.get("ifsc"),
        "branch": parsed.get("branch"),
        "statement_from": str(statement.statement_from) if statement.statement_from else None,
        "statement_to": str(statement.statement_to) if statement.statement_to else None,
        "opening_balance": float(statement.opening_balance),
        "closing_balance": float(statement.closing_balance),
        "total_withdrawals": float(statement.total_withdrawals),
        "total_deposits": float(statement.total_deposits),
        "file_name": statement.file_name,
        "status": statement.status,
        "parsed_transactions": parsed_transactions,
        "lines": parsed_transactions
    }

@router.get("/statements", response_model=List[BankStatementResponse])
async def list_statements(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(BankStatement)
        .options(selectinload(BankStatement.lines))
        .where(BankStatement.tenant_id == tenant.id)
        .order_by(BankStatement.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/statements/{statement_id}", response_model=BankStatementResponse)
async def get_statement_details(
    statement_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(BankStatement)
        .options(selectinload(BankStatement.lines))
        .where(BankStatement.id == statement_id, BankStatement.tenant_id == tenant.id)
    )
    res = await db.execute(stmt)
    statement = res.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    return statement

@router.post("/statements/{statement_id}/reconcile", response_model=Dict[str, Any])
async def execute_reconciliation(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers the 3-Tier Reconciliation matching algorithm:
    Tier 1: Exact UTR / Amount match
    Tier 2: Date window [-2, +5] days + Fuzzy counterparty match
    Tier 3: Auto-posts to Schedule III Suspense Account (Code 2099)
    """
    summary = await ReconciliationEngine.reconcile_statement(
        session=db,
        tenant_id=tenant.id,
        statement_id=statement_id,
        user_id=current_user.id
    )
    await db.commit()
    return summary

@router.post("/reconcile-all")
async def reconcile_all_statements(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes 3-Tier Reconciliation sweep across all statements for the tenant in 1 click.
    """
    stmts_res = await db.execute(select(BankStatement).where(BankStatement.tenant_id == tenant.id))
    stmts = stmts_res.scalars().all()
    total_lines = 0
    total_tier1 = 0
    total_tier2 = 0
    total_tier3 = 0
    for s in stmts:
        res = await ReconciliationEngine.reconcile_statement(
            session=db,
            tenant_id=tenant.id,
            statement_id=s.id,
            user_id=current_user.id
        )
        total_lines += res.get("total_lines", 0)
        total_tier1 += res.get("tier1_reconciled", 0)
        total_tier2 += res.get("tier2_probable", 0)
        total_tier3 += res.get("tier3_suspense", 0)

    await db.commit()
    return {
        "success": True,
        "total_statements": len(stmts),
        "total_lines": total_lines,
        "tier1_reconciled": total_tier1,
        "tier2_probable": total_tier2,
        "tier3_suspense": total_tier3,
        "message": f"Global Reconciliation Complete across {len(stmts)} statements: {total_tier1} Tier 1 exact matched, {total_tier2} Tier 2 probable, {total_tier3} routed to Suspense."
    }

@router.post("/lines/{line_id}/allocate-suspense")
async def allocate_suspense(
    line_id: uuid.UUID,
    payload: AllocateSuspenseRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Re-allocates a Tier 3 Suspense record to a designated target Chart of Accounts code
    (e.g., 4010 Direct Expense, 4030 Bank Charges, 3010 Revenue).
    """
    line_stmt = select(BankStatementLine).where(
        BankStatementLine.id == line_id,
        BankStatementLine.tenant_id == tenant.id
    )
    line = (await db.execute(line_stmt)).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Statement line not found")

    target_acc = await db.get(ChartOfAccounts, payload.target_account_id)
    if not target_acc or target_acc.tenant_id != tenant.id:
        raise HTTPException(status_code=400, detail="Target account does not exist")

    suspense_acc_stmt = select(ChartOfAccounts).where(
        ChartOfAccounts.tenant_id == tenant.id,
        ChartOfAccounts.code == "2099"
    )
    suspense_acc = (await db.execute(suspense_acc_stmt)).scalar_one_or_none()
    if not suspense_acc:
        raise HTTPException(status_code=400, detail="Suspense account 2099 not found")

    is_deposit = line.deposit_amount > Decimal("0.00")
    amount = line.deposit_amount if is_deposit else line.withdrawal_amount

    # Post Reversing Re-allocation Journal: Clears Suspense 2099 and transfers to Target Account
    stmt_short = str(line.statement_id)[:8].upper()
    line_short = str(line.id)[:6].upper() if line.id else uuid.uuid4().hex[:6].upper()
    entry = JournalEntry(
        tenant_id=tenant.id,
        entry_number=f"JV-ALLOC-{stmt_short}-{line.line_number}-{line_short}",
        entry_date=line.transaction_date,
        reference_type="suspense_allocation",
        reference_id=line.id,
        narration=payload.narration or f"Re-allocation of suspense line #{line.line_number} to {target_acc.name}",
        status="posted",
        is_posted=True,
        created_by=current_user.id
    )
    db.add(entry)
    await db.flush()

    if is_deposit:
        # Clear Suspense (Debit 2099), Recognize in Target Account (Credit)
        db.add_all([
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=suspense_acc.id, debit_amount=amount, credit_amount=Decimal("0.00"), description="Reversing suspense deposit"),
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=target_acc.id, debit_amount=Decimal("0.00"), credit_amount=amount, description=f"Allocated to {target_acc.name}")
        ])
    else:
        # Clear Suspense (Credit 2099), Recognize in Target Account (Debit)
        db.add_all([
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=target_acc.id, debit_amount=amount, credit_amount=Decimal("0.00"), description=f"Allocated to {target_acc.name}"),
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=suspense_acc.id, debit_amount=Decimal("0.00"), credit_amount=amount, description="Reversing suspense withdrawal")
        ])

    line.reconciliation_status = "reconciled"
    line.notes = f"Re-allocated from Suspense to {target_acc.name} ({target_acc.code})"
    await db.commit()

    return {"message": f"Line #{line.line_number} successfully re-allocated to {target_acc.name}"}

@router.post("/lines/{line_id}/confirm-match")
async def confirm_line_match(
    line_id: uuid.UUID,
    payload: ConfirmMatchRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Confirms a Tier 1 or Tier 2 match for a bank statement line.
    Posts the corresponding double-entry journal entry to the general ledger:
    - Deposit: DR 1010 Bank, CR 1020 Accounts Receivable (or target customer)
    - Withdrawal: DR 4010 Direct Expense, CR 1010 Bank
    Marks line status as 'reconciled'.
    """
    stmt = select(BankStatementLine).where(
        BankStatementLine.id == line_id,
        BankStatementLine.tenant_id == tenant.id
    )
    line = (await db.execute(stmt)).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Statement line not found")

    bank_acc = await LedgerService.get_account_by_code(db, tenant.id, "1010")
    ar_acc = await LedgerService.get_account_by_code(db, tenant.id, "1020")
    exp_acc = await LedgerService.get_account_by_code(db, tenant.id, "4010")
    suspense_acc = await LedgerService.get_account_by_code(db, tenant.id, "2099")

    if not bank_acc:
        raise HTTPException(status_code=400, detail="Bank account (Code 1010) not configured in Chart of Accounts")

    is_deposit = line.deposit_amount > Decimal("0.00")
    amount = line.deposit_amount if is_deposit else line.withdrawal_amount

    # Check if this line already has an active suspense_posting journal entry
    existing_suspense = (await db.execute(
        select(JournalEntry).where(
            JournalEntry.tenant_id == tenant.id,
            JournalEntry.reference_type == "suspense_posting",
            JournalEntry.reference_id == line.id
        )
    )).scalar_one_or_none()

    # Post double-entry settlement journal (clear 2099 Suspense if previously routed to Suspense)
    jv_number = f"JV-RECON-CONFIRM-{line.line_number}-{uuid.uuid4().hex[:6].upper()}"
    entry = JournalEntry(
        tenant_id=tenant.id,
        entry_number=jv_number,
        entry_date=line.transaction_date,
        reference_type="bank_reconciliation",
        reference_id=line.id,
        narration=payload.notes or f"Confirmed reconciliation match for line #{line.line_number}: {line.description[:100]}",
        status="posted",
        is_posted=True,
        created_by=current_user.id
    )
    db.add(entry)
    await db.flush()

    if is_deposit:
        debit_acc_id = suspense_acc.id if (existing_suspense and suspense_acc) else bank_acc.id
        debit_desc = "Clear Suspense 2099 on confirmed invoice settlement" if (existing_suspense and suspense_acc) else f"Deposit via {line.reference_number or line.payment_channel}"
        credit_acc_id = ar_acc.id if ar_acc else bank_acc.id
        db.add_all([
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=debit_acc_id, debit_amount=amount, credit_amount=Decimal("0.00"), description=debit_desc),
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=credit_acc_id, debit_amount=Decimal("0.00"), credit_amount=amount, description=f"Settlement: {line.counterparty_name or 'Customer'}")
        ])
        # Mark matched invoice as paid if found
        import re as _re
        from app.models.invoice import Invoice
        matched_inv_obj = None
        if payload.matched_invoice_id:
            matched_inv_obj = await db.get(Invoice, payload.matched_invoice_id)
        if not matched_inv_obj and line.notes:
            m = _re.search(r"Inv\s*#([A-Za-z0-9\-_/]+)", line.notes)
            if m:
                inv_num = m.group(1)
                matched_inv_obj = (await db.execute(
                    select(Invoice).where(Invoice.tenant_id == tenant.id, Invoice.invoice_number == inv_num)
                )).scalar_one_or_none()
        if not matched_inv_obj:
            matched_inv_obj = (await db.execute(
                select(Invoice).where(
                    Invoice.tenant_id == tenant.id,
                    Invoice.grand_total == amount,
                    Invoice.status.in_(["sent", "draft", "partially_paid"])
                )
            )).scalars().first()
        if matched_inv_obj and matched_inv_obj.tenant_id == tenant.id:
            matched_inv_obj.status = "paid"
    else:
        debit_acc_id = exp_acc.id if exp_acc else bank_acc.id
        credit_acc_id = suspense_acc.id if (existing_suspense and suspense_acc) else bank_acc.id
        credit_desc = "Clear Suspense 2099 on confirmed withdrawal" if (existing_suspense and suspense_acc) else f"Withdrawal via {line.reference_number or line.payment_channel}"
        db.add_all([
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=debit_acc_id, debit_amount=amount, credit_amount=Decimal("0.00"), description=f"Expense discharge: {line.counterparty_name or line.description[:50]}"),
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=credit_acc_id, debit_amount=Decimal("0.00"), credit_amount=amount, description=credit_desc)
        ])

    line.reconciliation_status = "reconciled"
    line.matched_journal_entry_id = entry.id
    line.confidence_score = Decimal("100.00")
    if line.notes and "Inv #" in line.notes:
        line.notes = f"{line.notes} [Confirmed]"
    elif payload.notes:
        line.notes = payload.notes
    else:
        line.notes = f"Match confirmed manually for line #{line.line_number}"

    await db.commit()
    return {
        "success": True,
        "message": f"Line #{line.line_number} successfully reconciled and posted to ledger.",
        "line_id": str(line.id),
        "journal_entry_number": jv_number
    }

@router.post("/lines/{line_id}/route-to-suspense")
async def route_line_to_suspense(
    line_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually routes an unmatched bank transaction to Schedule III Suspense Account (Code 2099)
    and posts double-entry journal entry.
    """
    stmt = select(BankStatementLine).where(
        BankStatementLine.id == line_id,
        BankStatementLine.tenant_id == tenant.id
    )
    line = (await db.execute(stmt)).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Statement line not found")

    bank_acc = await LedgerService.get_account_by_code(db, tenant.id, "1010")
    suspense_acc = await LedgerService.get_account_by_code(db, tenant.id, "2099")
    if not suspense_acc or not bank_acc:
        raise HTTPException(status_code=400, detail="Required COA accounts (1010 or 2099) not configured")

    is_deposit = line.deposit_amount > Decimal("0.00")
    amount = line.deposit_amount if is_deposit else line.withdrawal_amount

    jv_number = f"JV-SUSPENSE-MANUAL-{line.line_number}-{uuid.uuid4().hex[:6].upper()}"
    entry = JournalEntry(
        tenant_id=tenant.id,
        entry_number=jv_number,
        entry_date=line.transaction_date,
        reference_type="suspense_posting",
        reference_id=line.id,
        narration=f"Manual Suspense allocation: {line.description[:100]}",
        status="posted",
        is_posted=True,
        created_by=current_user.id
    )
    db.add(entry)
    await db.flush()

    if is_deposit:
        db.add_all([
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=bank_acc.id, debit_amount=amount, credit_amount=Decimal("0.00"), description="Unidentified incoming credit"),
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=suspense_acc.id, debit_amount=Decimal("0.00"), credit_amount=amount, description="Suspense Account credit pending allocation")
        ])
    else:
        db.add_all([
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=suspense_acc.id, debit_amount=amount, credit_amount=Decimal("0.00"), description="Suspense Account debit pending allocation"),
            JournalLine(journal_entry_id=entry.id, tenant_id=tenant.id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=amount, description="Unidentified bank debit")
        ])

    line.reconciliation_tier = "tier3_suspense"
    line.reconciliation_status = "suspense_posted"
    line.suspense_journal_id = entry.id
    line.confidence_score = Decimal("50.00")
    line.notes = "Manually routed to Schedule III Suspense Account (Code 2099)"

    await db.commit()
    return {
        "success": True,
        "message": f"Line #{line.line_number} routed to Suspense Account (Code 2099).",
        "line_id": str(line.id),
        "journal_entry_number": jv_number
    }

