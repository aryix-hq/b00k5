from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import uuid
import difflib
try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.bank import BankStatement, BankStatementLine
    from app.models.invoice import Invoice, Contact
    from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
    from app.models.payroll import ContractorPayment, PayrollRun
    from app.services.ledger_service import LedgerService
    from app.services.payroll_service import PayrollService
    HAVE_SQLALCHEMY = True
except ImportError:
    AsyncSession = Any
    HAVE_SQLALCHEMY = False

PAYMENT_AGGREGATORS = (
    "RAZORPAY",
    "PAYMENT AGGREGATOR",
    "STRIPE",
    "PAYU",
    "CASHFREE",
    "PHONEPE",
    "CCAVENUE",
    "BILLDESK",
    "INSTAMOJO",
)


def is_payment_aggregator(text: Optional[str]) -> bool:
    if not text:
        return False
    upper = text.upper()
    return any(agg in upper for agg in PAYMENT_AGGREGATORS)


def calculate_name_similarity(name1: Optional[str], name2: Optional[str]) -> float:
    if not name1 or not name2:
        return 0.0
    n1 = name1.upper().replace("PVT", "").replace("LTD", "").replace("PRIVATE", "").replace("LIMITED", "").strip()
    n2 = name2.upper().replace("PVT", "").replace("LTD", "").replace("PRIVATE", "").replace("LIMITED", "").strip()
    matcher = difflib.SequenceMatcher(None, n1, n2)
    return matcher.ratio() * 100.0

class ReconciliationEngine:
    """
    3-Tier Indian Bank Reconciliation State Engine:
    - Tier 1: Deterministic Match (Exact Reference / UTR + Exact Amount -> 100% confidence).
    - Tier 2: Window Heuristic (Exact Amount within [-2, +15] days + Fuzzy Name Match >= 70% OR Payment Aggregator Settlement).
    - Tier 3: Suspense Auto-Posting (Unmatched records auto-post to Code 2099 Suspense Account).
    """

    @staticmethod
    def match_tier1(
        line: Dict[str, Any],
        open_invoices: List[Dict[str, Any]]
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Deterministic match: Exact UTR / Reference match OR exact invoice number + amount match.
        """
        line_ref = (line.get("reference_number") or "").upper().strip()
        line_desc = (line.get("description") or "").upper()
        amount = line.get("deposit_amount", Decimal("0.00"))

        if amount <= Decimal("0.00"):
            return None

        for inv in open_invoices:
            inv_total = Decimal(str(inv.get("grand_total", "0.00")))
            inv_num = inv.get("invoice_number", "").upper().strip()

            # 1. Exact amount match required
            if inv_total != amount:
                continue

            # 2. Check if invoice number appears in reference or description
            if inv_num and (inv_num in line_ref or inv_num in line_desc):
                return inv, 100.00

            # 3. Check if explicit UTR/reference match exists
            if line_ref and len(line_ref) >= 8 and (line_ref in inv.get("notes", "").upper() or line_ref in inv.get("invoice_number", "").upper()):
                return inv, 100.00

        return None

    @staticmethod
    def match_tier2(
        line: Dict[str, Any],
        open_invoices: List[Dict[str, Any]]
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Window heuristic: Exact amount within [-2, +15] days + fuzzy counterparty match >= 70%
        OR Payment Aggregator (Razorpay/Stripe/PayU/Cashfree) settlement matching an open invoice
        in the [-2, +15] day window (exact amount or net of ~2-3% gateway fee).
        UAT-07: If two or more open invoices match with similar scores and identical amounts,
        flags the result with `is_ambiguous = True` and `reconciliation_status = 'probable_match'`
        so it is never silently auto-reconciled.
        """
        amount = line.get("deposit_amount", Decimal("0.00"))
        if amount <= Decimal("0.00"):
            return None

        txn_date = line.get("transaction_date")
        counterparty = line.get("counterparty_name")
        description = line.get("description")
        aggregator_deposit = is_payment_aggregator(counterparty) or is_payment_aggregator(description)

        best_match = None
        highest_score = 0.0
        qualifying_candidates: List[Tuple[Dict[str, Any], float]] = []

        for inv in open_invoices:
            inv_total = Decimal(str(inv.get("grand_total", "0.00")))
            if inv_total <= Decimal("0.00"):
                continue

            exact_amount = (inv_total == amount)
            net_of_fee_amount = aggregator_deposit and (Decimal("0.96") * inv_total <= amount < inv_total)
            if not (exact_amount or net_of_fee_amount):
                continue

            inv_date = inv.get("issue_date")
            if txn_date and inv_date:
                # Window check: txn_date between inv_date - 2 days and inv_date + 15 days
                days_diff = (txn_date - inv_date).days
                if not (-2 <= days_diff <= 15):
                    continue

                contact_name = inv.get("contact_name")
                sim_score = calculate_name_similarity(counterparty, contact_name)
                if aggregator_deposit and sim_score < 60.0:
                    sim_score = 85.0 if exact_amount else 75.0

                # Bonus points for date closeness
                date_closeness_bonus = max(0, 10 - abs(days_diff))
                composite_score = min(95.0, sim_score + date_closeness_bonus)

                if sim_score >= 60.0 and composite_score >= 70.0:
                    qualifying_candidates.append((inv, round(composite_score, 2)))
                    if composite_score > highest_score:
                        highest_score = composite_score
                        best_match = inv

        if best_match and highest_score >= 70.0:
            result_inv = dict(best_match)
            if len(qualifying_candidates) > 1:
                result_inv["is_ambiguous"] = True
                result_inv["reconciliation_status"] = "probable_match"
                result_inv["auto_reconcile_allowed"] = False
                result_inv["ambiguous_candidate_numbers"] = [
                    c[0].get("invoice_number") for c in qualifying_candidates
                ]
            else:
                result_inv["is_ambiguous"] = False
                result_inv["reconciliation_status"] = "probable_match"
                result_inv["auto_reconcile_allowed"] = True
            return result_inv, round(highest_score, 2)

        return None

    @staticmethod
    def compute_suspense_clearance_entries(
        suspense_amount: Decimal,
        is_withdrawal: bool,
        suspense_account_code: str = "2099",
        target_account_code: str = "4010"
    ) -> Dict[str, Any]:
        """
        Section 7 Suspense Clearance Helper:
        Clears a previously posted Suspense (2099) entry to the final Expense/AR/AP account
        WITHOUT touching Bank Account (1010) a second time, preventing cash or expense double-counting.
        """
        amt = Decimal(str(suspense_amount)).quantize(Decimal("0.01"))
        if is_withdrawal:
            # Original suspense entry for withdrawal was: Dr 2099 Suspense / Cr 1010 Bank
            # Clearance entry moves from Suspense to Target Expense: Dr Target (4010) / Cr 2099 Suspense
            lines = [
                {"account_code": target_account_code, "debit": amt, "credit": Decimal("0.00")},
                {"account_code": suspense_account_code, "debit": Decimal("0.00"), "credit": amt},
            ]
        else:
            # Original suspense entry for deposit was: Dr 1010 Bank / Cr 2099 Suspense
            # Clearance entry moves from Suspense to Target Revenue/AR: Dr 2099 Suspense / Cr Target (1020/3010)
            lines = [
                {"account_code": suspense_account_code, "debit": amt, "credit": Decimal("0.00")},
                {"account_code": target_account_code, "debit": Decimal("0.00"), "credit": amt},
            ]
        return {
            "lines": lines,
            "touches_bank_account_1010": False,
            "net_suspense_balance_after_clearance": Decimal("0.00"),
            "total_debit": amt,
            "total_credit": amt,
        }

    @staticmethod
    async def reconcile_statement(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        statement_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Executes the full 3-Tier Reconciliation sweep over all lines of a bank statement.
        """
        # Fetch statement lines
        lines_stmt = select(BankStatementLine).where(
            BankStatementLine.statement_id == statement_id,
            BankStatementLine.tenant_id == tenant_id
        ).order_by(BankStatementLine.line_number)
        lines = (await session.execute(lines_stmt)).scalars().all()

        # Fetch open/unpaid invoices
        inv_stmt = select(Invoice, Contact.name.label("contact_name")).join(
            Contact, Invoice.contact_id == Contact.id
        ).where(
            Invoice.tenant_id == tenant_id,
            Invoice.status.in_(["sent", "draft", "partially_paid"])
        )
        inv_res = await session.execute(inv_stmt)
        open_invoices = []
        for inv, contact_name in inv_res.all():
            open_invoices.append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "issue_date": inv.issue_date,
                "grand_total": inv.grand_total,
                "contact_name": contact_name,
                "notes": inv.invoice_number
            })

        # Fetch open / payable contractor payments
        cp_stmt = select(ContractorPayment).options(
            selectinload(ContractorPayment.contractor)
        ).where(
            ContractorPayment.tenant_id == tenant_id,
            ContractorPayment.status.in_(["approved", "disbursed", "pending"])
        )
        open_contractor_payments = list((await session.execute(cp_stmt)).scalars().all())

        # Fetch payroll runs
        pr_stmt = select(PayrollRun).where(
            PayrollRun.tenant_id == tenant_id,
            PayrollRun.status.in_(["locked", "disbursed"])
        )
        open_payroll_runs = list((await session.execute(pr_stmt)).scalars().all())

        tier1_count = 0
        tier2_count = 0
        tier3_count = 0

        # Required COA accounts for Tier 3 Suspense posting & settlements
        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, "1010")
        suspense_acc = await LedgerService.get_account_by_code(session, tenant_id, "2099")
        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, "1020")
        bank_charges_acc = await LedgerService.get_account_by_code(session, tenant_id, "4030")
        interest_income_acc = await LedgerService.get_account_by_code(session, tenant_id, "3020")
        advances_acc = await LedgerService.get_account_by_code(session, tenant_id, "1040")

        # Fetch existing posted GL lines on Bank Current Account 1010
        existing_bank_gl = []
        if bank_acc:
            bank_lines_stmt = select(JournalLine, JournalEntry).join(
                JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
            ).where(
                JournalLine.tenant_id == tenant_id,
                JournalLine.account_id == bank_acc.id,
                JournalEntry.reference_type.notin_(["suspense_posting", "bank_reconciliation", "bank_charge", "bank_interest", "fd_liquidation"])
            )
            existing_bank_gl = (await session.execute(bank_lines_stmt)).all()

        matched_gl_ids = set()

        for line in lines:
            if line.reconciliation_status == "reconciled" and line.matched_journal_entry_id:
                matched_gl_ids.add(line.matched_journal_entry_id)
                tier1_count += 1
                continue

            line_dict = {
                "transaction_date": line.transaction_date,
                "description": line.description,
                "reference_number": line.reference_number,
                "counterparty_name": line.counterparty_name,
                "deposit_amount": line.deposit_amount,
                "withdrawal_amount": line.withdrawal_amount
            }

            stmt_short = str(statement_id)[:8].upper()
            line_short = str(line.id)[:6].upper() if line.id else uuid.uuid4().hex[:6].upper()
            desc_upper = (line.description or "").upper()
            ref_upper = (line.reference_number or "").upper()

            # Guard: Skip zero-value non-financial statement lines (e.g. blank trailing rows)
            dep = line.deposit_amount or Decimal("0.00")
            wdr = line.withdrawal_amount or Decimal("0.00")
            if dep <= Decimal("0.00") and wdr <= Decimal("0.00"):
                line.reconciliation_tier = "tier1_exact"
                line.reconciliation_status = "reconciled"
                line.confidence_score = Decimal("100.00")
                line.notes = "Zero-value non-financial row ignored"
                tier1_count += 1
                continue

            existing_suspense_je = (await session.execute(
                select(JournalEntry).where(
                    JournalEntry.tenant_id == tenant_id,
                    JournalEntry.reference_type == "suspense_posting",
                    JournalEntry.reference_id == line.id
                )
            )).scalar_one_or_none()

            # --- A. WITHDRAWAL HANDLING ---
            if line.withdrawal_amount > Decimal("0.00"):
                # 1. Match against existing GL Journal Entry crediting Bank Account 1010
                matched_je = None
                for jl, je in existing_bank_gl:
                    if je.id in matched_gl_ids:
                        continue
                    if jl.credit_amount == line.withdrawal_amount:
                        matched_je = je
                        matched_gl_ids.add(je.id)
                        break

                if matched_je:
                    line.matched_journal_entry_id = matched_je.id
                    line.reconciliation_tier = "tier1_exact"
                    line.reconciliation_status = "reconciled"
                    line.confidence_score = Decimal("100.00")
                    line.notes = f"Tier 1 Exact Match with GL Voucher {matched_je.entry_number}"
                    tier1_count += 1
                    continue

                # 2. Match against Contractor / Freelancer Payments
                matched_cp = None
                matched_cp_score = 0.0
                for cp in open_contractor_payments:
                    if cp.net_payable == line.withdrawal_amount:
                        c_name = cp.contractor.name if cp.contractor else ""
                        c_pan = cp.contractor.pan_number if cp.contractor else ""
                        c_code = cp.contractor.contractor_code if cp.contractor else ""
                        # Exact UTR or payment number match
                        if (cp.payment_number.upper() in ref_upper or cp.payment_number.upper() in desc_upper) or \
                           (cp.payout_utr and (cp.payout_utr.upper() in ref_upper or cp.payout_utr.upper() in desc_upper)):
                            matched_cp = cp
                            matched_cp_score = 100.0
                            break
                        # Name or PAN match in counterparty / description
                        sim = calculate_name_similarity(line.counterparty_name or line.description, c_name)
                        if (c_pan and c_pan in desc_upper) or (c_code and c_code in desc_upper) or sim >= 70.0:
                            matched_cp = cp
                            matched_cp_score = 100.0
                            break
                        elif sim >= 50.0:
                            matched_cp = cp
                            matched_cp_score = 85.0

                if matched_cp:
                    c_label = matched_cp.contractor.name if matched_cp.contractor else "Contractor"
                    cp_id = matched_cp.id
                    cp_pnum = matched_cp.payment_number
                    if matched_cp_score >= 100.0:
                        if matched_cp.status != "disbursed":
                            matched_cp = await PayrollService.disburse_contractor_payment(
                                session, tenant_id, cp_id, user_id, utr=line.reference_number
                            )
                        line.matched_journal_entry_id = matched_cp.disbursement_journal_id
                        line.reconciliation_tier = "tier1_exact"
                        line.reconciliation_status = "reconciled"
                        line.confidence_score = Decimal("100.00")
                        line.notes = f"Tier 1 Exact Match: Contractor Payout to {c_label} (#{cp_pnum})"
                        open_contractor_payments = [p for p in open_contractor_payments if p.id != cp_id]
                        tier1_count += 1
                        continue
                    else:
                        line.reconciliation_tier = "tier2_heuristic"
                        line.reconciliation_status = "probable_match"
                        line.confidence_score = Decimal(str(matched_cp_score))
                        line.notes = f"Tier 2 Probable Match: Contractor Payout to {c_label} (#{cp_pnum})"
                        open_contractor_payments = [p for p in open_contractor_payments if p.id != cp_id]
                        tier2_count += 1
                        continue

                # 3. Match against Payroll Runs (Employee Salaries)
                matched_pr = None
                for pr in open_payroll_runs:
                    if pr.total_net_pay == line.withdrawal_amount:
                        if ("SALARY" in desc_upper or "PAYROLL" in desc_upper or "SAL" in desc_upper or "NEFT" in desc_upper or pr.run_number.upper() in desc_upper or pr.run_number.upper() in ref_upper):
                            matched_pr = pr
                            break

                if matched_pr:
                    pr_id = matched_pr.id
                    pr_month = matched_pr.month
                    pr_year = matched_pr.year
                    pr_run_num = matched_pr.run_number
                    if matched_pr.status == "locked":
                        disb_entry = await PayrollService.post_disbursement_journal(
                            session=session,
                            run_id=pr_id,
                            bank_account_code="1010",
                            payout_utr=line.reference_number,
                            created_by_user_id=user_id
                        )
                        line.matched_journal_entry_id = disb_entry.id
                    else:
                        line.matched_journal_entry_id = matched_pr.disbursement_journal_id
                    line.reconciliation_tier = "tier1_exact"
                    line.reconciliation_status = "reconciled"
                    line.confidence_score = Decimal("100.00")
                    line.notes = f"Tier 1 Exact Match: Salary Payout for {pr_month}/{pr_year} (#{pr_run_num})"
                    open_payroll_runs = [r for r in open_payroll_runs if r.id != pr_id]
                    tier1_count += 1
                    continue

                # 4. Pattern Match: Bank Charges / Debit Card Fee / Maintenance
                if ("DEBIT CARD" in desc_upper or "CHARGES" in desc_upper or "FEE" in desc_upper or "ISSUANCE" in desc_upper) and bank_charges_acc and bank_acc:
                    credit_acc_id = suspense_acc.id if (existing_suspense_je and suspense_acc) else bank_acc.id
                    entry = JournalEntry(
                        tenant_id=tenant_id,
                        entry_number=f"JV-CHG-{stmt_short}-{line.line_number}-{line_short}",
                        entry_date=line.transaction_date,
                        reference_type="bank_charge",
                        reference_id=line.id,
                        narration=f"Bank Charges / Debit Card Fee: {line.description[:100]}",
                        status="posted",
                        is_posted=True,
                        created_by=user_id
                    )
                    session.add(entry)
                    await session.flush()
                    session.add_all([
                        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=bank_charges_acc.id, debit_amount=line.withdrawal_amount, credit_amount=Decimal("0.00"), description=f"Bank charge: {line.description[:64]}"),
                        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=credit_acc_id, debit_amount=Decimal("0.00"), credit_amount=line.withdrawal_amount, description="Bank auto-debit charge")
                    ])
                    line.matched_journal_entry_id = entry.id
                    line.reconciliation_tier = "tier1_exact"
                    line.reconciliation_status = "reconciled"
                    line.confidence_score = Decimal("100.00")
                    line.notes = "Direct bank charge posted to Code 4030 Finance Costs & Bank Charges"
                    tier1_count += 1
                    continue

            # --- B. DEPOSIT HANDLING ---
            if line.deposit_amount > Decimal("0.00"):
                # 1. Match against existing GL Journal Entry debiting Bank Account 1010
                matched_je = None
                for jl, je in existing_bank_gl:
                    if je.id in matched_gl_ids:
                        continue
                    if jl.debit_amount == line.deposit_amount:
                        matched_je = je
                        matched_gl_ids.add(je.id)
                        break

                if matched_je:
                    line.matched_journal_entry_id = matched_je.id
                    line.reconciliation_tier = "tier1_exact"
                    line.reconciliation_status = "reconciled"
                    line.confidence_score = Decimal("100.00")
                    line.notes = f"Tier 1 Exact Match with GL Voucher {matched_je.entry_number}"
                    tier1_count += 1
                    continue

                # 2. Tier 1 Deterministic Match against Open Customer Invoices
                t1_match = ReconciliationEngine.match_tier1(line_dict, open_invoices)
                if t1_match:
                    matched_inv, score = t1_match
                    line.reconciliation_tier = "tier1_exact"
                    line.reconciliation_status = "reconciled"
                    line.confidence_score = Decimal(str(score))
                    line.notes = f"Tier 1 Exact Match with Invoice #{matched_inv['invoice_number']}"

                    if bank_acc and ar_acc:
                        debit_acc_id = suspense_acc.id if (existing_suspense_je and suspense_acc) else bank_acc.id
                        debit_desc = "Clear Suspense 2099 on invoice settlement" if (existing_suspense_je and suspense_acc) else f"Deposit via {line.reference_number or 'Bank'}"
                        entry = JournalEntry(
                            tenant_id=tenant_id,
                            entry_number=f"JV-RECON-T1-{stmt_short}-{line.line_number}-{line_short}",
                            entry_date=line.transaction_date,
                            reference_type="bank_reconciliation",
                            reference_id=line.id,
                            narration=f"Settlement of Inv #{matched_inv['invoice_number']} via {line.payment_channel}",
                            status="posted",
                            is_posted=True,
                            created_by=user_id
                        )
                        session.add(entry)
                        await session.flush()
                        session.add_all([
                            JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=debit_acc_id, debit_amount=line.deposit_amount, credit_amount=Decimal("0.00"), description=debit_desc),
                            JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=ar_acc.id, debit_amount=Decimal("0.00"), credit_amount=line.deposit_amount, description=f"Settlement of Inv #{matched_inv['invoice_number']}")
                        ])
                        line.matched_journal_entry_id = entry.id

                    inv_obj = await session.get(Invoice, matched_inv["id"])
                    if inv_obj:
                        inv_obj.status = "paid"

                    open_invoices = [i for i in open_invoices if i["id"] != matched_inv["id"]]
                    tier1_count += 1
                    continue

                # 3. Pattern Match: FD Redeem Interest / Bank Interest
                if ("INTEREST" in desc_upper or "REDEEM INTEREST" in desc_upper) and interest_income_acc and bank_acc:
                    debit_acc_id = suspense_acc.id if (existing_suspense_je and suspense_acc) else bank_acc.id
                    entry = JournalEntry(
                        tenant_id=tenant_id,
                        entry_number=f"JV-INT-{stmt_short}-{line.line_number}-{line_short}",
                        entry_date=line.transaction_date,
                        reference_type="bank_interest",
                        reference_id=line.id,
                        narration=f"Bank Interest Credit: {line.description[:100]}",
                        status="posted",
                        is_posted=True,
                        created_by=user_id
                    )
                    session.add(entry)
                    await session.flush()
                    session.add_all([
                        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=debit_acc_id, debit_amount=line.deposit_amount, credit_amount=Decimal("0.00"), description="Bank interest credited"),
                        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=interest_income_acc.id, debit_amount=Decimal("0.00"), credit_amount=line.deposit_amount, description=f"Interest earned: {line.description[:64]}")
                    ])
                    line.matched_journal_entry_id = entry.id
                    line.reconciliation_tier = "tier1_exact"
                    line.reconciliation_status = "reconciled"
                    line.confidence_score = Decimal("100.00")
                    line.notes = "Interest credit recognized in Code 3020 Other Income & Interest Received"
                    tier1_count += 1
                    continue

                # 4. Pattern Match: FD Redeem Principal / Term Deposit Liquidation
                if ("REDEEM PRINCIPAL" in desc_upper or "PRINCIPAL" in desc_upper or "FD REDEEM" in desc_upper) and advances_acc and bank_acc:
                    debit_acc_id = suspense_acc.id if (existing_suspense_je and suspense_acc) else bank_acc.id
                    entry = JournalEntry(
                        tenant_id=tenant_id,
                        entry_number=f"JV-FD-{stmt_short}-{line.line_number}-{line_short}",
                        entry_date=line.transaction_date,
                        reference_type="fd_liquidation",
                        reference_id=line.id,
                        narration=f"Fixed Deposit Principal Liquidation: {line.description[:100]}",
                        status="posted",
                        is_posted=True,
                        created_by=user_id
                    )
                    session.add(entry)
                    await session.flush()
                    session.add_all([
                        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=debit_acc_id, debit_amount=line.deposit_amount, credit_amount=Decimal("0.00"), description="FD principal proceeds deposited"),
                        JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=advances_acc.id, debit_amount=Decimal("0.00"), credit_amount=line.deposit_amount, description=f"FD redemption: {line.description[:64]}")
                    ])
                    line.matched_journal_entry_id = entry.id
                    line.reconciliation_tier = "tier1_exact"
                    line.reconciliation_status = "reconciled"
                    line.confidence_score = Decimal("100.00")
                    line.notes = "Fixed Deposit principal redemption recognized in Code 1040 Loans & Advances"
                    tier1_count += 1
                    continue

                # 5. Tier 2 Window Heuristic + Fuzzy / Payment Aggregator Match
                t2_match = ReconciliationEngine.match_tier2(line_dict, open_invoices)
                if t2_match:
                    matched_inv, score = t2_match
                    line.reconciliation_tier = "tier2_heuristic"
                    line.reconciliation_status = "probable_match"
                    line.confidence_score = Decimal(str(score))
                    is_agg = is_payment_aggregator(line.counterparty_name) or is_payment_aggregator(line.description)
                    via_suffix = " [via Payment Aggregator Settlement]" if is_agg else ""
                    line.notes = f"Tier 2 Probable Match: {matched_inv['contact_name']} (Inv #{matched_inv['invoice_number']}){via_suffix}"
                    open_invoices = [i for i in open_invoices if i["id"] != matched_inv["id"]]
                    tier2_count += 1
                    continue

            # --- C. TIER 3: SUSPENSE AUTO-POSTING ---
            if suspense_acc and bank_acc:
                line.reconciliation_tier = "tier3_suspense"
                line.reconciliation_status = "suspense_posted"
                line.confidence_score = Decimal("50.00")
                line.notes = "Unmatched bank transaction auto-routed to Schedule III Suspense Account (Code 2099)"

                is_deposit = line.deposit_amount > Decimal("0.00")
                amount = line.deposit_amount if is_deposit else line.withdrawal_amount
                if not amount or amount <= Decimal("0.00"):
                    continue

                existing_suspense = (await session.execute(
                    select(JournalEntry).where(
                        JournalEntry.tenant_id == tenant_id,
                        JournalEntry.reference_type == "suspense_posting",
                        JournalEntry.reference_id == line.id
                    )
                )).scalar_one_or_none()

                if not existing_suspense:
                    entry = JournalEntry(
                        tenant_id=tenant_id,
                        entry_number=f"JV-SUSPENSE-{stmt_short}-{line.line_number}-{line_short}",
                        entry_date=line.transaction_date,
                        reference_type="suspense_posting",
                        reference_id=line.id,
                        narration=f"Suspense allocation pending review: {line.description[:100]}",
                        status="posted",
                        is_posted=True,
                        created_by=user_id
                    )
                    session.add(entry)
                    await session.flush()

                    if is_deposit:
                        # Money came into bank: DR Bank, CR Suspense
                        session.add_all([
                            JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=amount, credit_amount=Decimal("0.00"), description="Unidentified incoming credit"),
                            JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=suspense_acc.id, debit_amount=Decimal("0.00"), credit_amount=amount, description="Suspense Account credit pending allocation")
                        ])
                    else:
                        # Money left bank: DR Suspense, CR Bank
                        session.add_all([
                            JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=suspense_acc.id, debit_amount=amount, credit_amount=Decimal("0.00"), description="Suspense Account debit pending allocation"),
                            JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=bank_acc.id, debit_amount=Decimal("0.00"), credit_amount=amount, description="Unidentified bank debit")
                        ])

                    line.suspense_journal_id = entry.id
                else:
                    line.suspense_journal_id = existing_suspense.id
                tier3_count += 1

        # Update statement overall status
        stmt_obj = await session.get(BankStatement, statement_id)
        if stmt_obj:
            if len(lines) == 0 or (tier1_count + tier2_count == len(lines)):
                stmt_obj.status = "reconciled"
            elif (tier1_count + tier2_count + tier3_count) > 0:
                stmt_obj.status = "partially_reconciled"
            else:
                stmt_obj.status = "unreconciled"

        await session.flush()

        return {
            "statement_id": statement_id,
            "total_lines": len(lines),
            "tier1_reconciled": tier1_count,
            "tier2_probable": tier2_count,
            "tier3_suspense": tier3_count,
            "unreconciled": len(lines) - (tier1_count + tier2_count + tier3_count)
        }
