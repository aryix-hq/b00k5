"""
b00k5 Financial Engine: Sub-Ledger & Statutory Withholding Service
Pillars:
- Pillar 3: Accounts Receivable (AR), Sales Sub-Ledger, Credit Notes, AR Aging, Bad Debts
- Pillar 4: Accounts Payable (AP), Procurement, Section 194J/194C TDS, Debit Notes, TDS Remittance
- Pillar 5: Advance Payments, Unearned Revenue, Multi-Voucher Allocation
"""

from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.invoice import Invoice, InvoiceItem, Contact
from app.services.ledger_service import LedgerService


class SubledgerService:
    @staticmethod
    def bankers_round(value: Decimal, places: int = 2) -> Decimal:
        """Applies banker's rounding (ROUND_HALF_EVEN) to arbitrary-precision decimal."""
        quant = Decimal('10') ** -places
        return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_EVEN)

    # =========================================================================
    # PILLAR 3: ACCOUNTS RECEIVABLE (AR) & SALES SUB-LEDGER
    # =========================================================================

    @staticmethod
    async def post_tax_invoice(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        invoice_number: str,
        subtotal: Decimal,
        cgst_rate: Decimal = Decimal("9.00"),
        sgst_rate: Decimal = Decimal("9.00"),
        igst_rate: Decimal = Decimal("0.00"),
        issue_date: Optional[date] = None,
        due_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Pillar 3.1: Post Tax Invoice with Atomic AR and Output GST Recognition:
        DR 1020 Accounts Receivable  = Grand Total
        CR 3010/4010 Operating Revenue = Subtotal
        CR 2050 Output CGST          = CGST Total
        CR 2051 Output SGST          = SGST Total (or CR 2052 Output IGST)
        """
        issue_dt = issue_date or date.today()
        due_dt = due_date or (issue_dt + timedelta(days=30))

        subtotal = SubledgerService.bankers_round(subtotal)
        cgst_amt = SubledgerService.bankers_round(subtotal * (cgst_rate / Decimal("100.00")))
        sgst_amt = SubledgerService.bankers_round(subtotal * (sgst_rate / Decimal("100.00")))
        igst_amt = SubledgerService.bankers_round(subtotal * (igst_rate / Decimal("100.00")))
        grand_total = subtotal + cgst_amt + sgst_amt + igst_amt

        # Retrieve accounts
        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, "1020")
        rev_acc = await LedgerService.get_account_by_code(session, tenant_id, "3010")
        cgst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2050")
        sgst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2051")
        igst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2052")

        if not (ar_acc and rev_acc):
            raise ValueError("Required accounts (1020 Accounts Receivable, 3010 Revenue) not found.")

        # Header
        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-INV-{invoice_number}",
            entry_date=issue_dt,
            reference_type="tax_invoice",
            reference_id=customer_id,
            narration=f"Tax Invoice #{invoice_number} issued to customer",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = []
        # DR Accounts Receivable
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=ar_acc.id,
            debit_amount=grand_total,
            credit_amount=Decimal("0.00"),
            description=f"AR Claim for Invoice #{invoice_number}"
        ))

        # CR Revenue
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=rev_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=subtotal,
            description=f"Operating Revenue for Invoice #{invoice_number}"
        ))

        # CR Taxes
        if igst_amt > Decimal("0.00") and igst_acc:
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=igst_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=igst_amt,
                description=f"Output IGST on Invoice #{invoice_number}"
            ))
        else:
            if cgst_amt > Decimal("0.00") and cgst_acc:
                lines.append(JournalLine(
                    journal_entry_id=entry.id,
                    tenant_id=tenant_id,
                    account_id=cgst_acc.id,
                    debit_amount=Decimal("0.00"),
                    credit_amount=cgst_amt,
                    description=f"Output CGST on Invoice #{invoice_number}"
                ))
            if sgst_amt > Decimal("0.00") and sgst_acc:
                lines.append(JournalLine(
                    journal_entry_id=entry.id,
                    tenant_id=tenant_id,
                    account_id=sgst_acc.id,
                    debit_amount=Decimal("0.00"),
                    credit_amount=sgst_amt,
                    description=f"Output SGST on Invoice #{invoice_number}"
                ))

        session.add_all(lines)
        await session.flush()

        return {
            "journal_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "subtotal": subtotal,
            "cgst_amount": cgst_amt,
            "sgst_amount": sgst_amt,
            "igst_amount": igst_amt,
            "grand_total": grand_total,
            "due_date": due_dt
        }

    @staticmethod
    async def apply_partial_payment(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        invoice_number: str,
        payment_amount: Decimal,
        bank_account_code: str = "1010",
        payment_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 3.2: Partial Payment Allocation against AR:
        DR 1010 Bank Current Account
        CR 1020 Accounts Receivable
        """
        pay_amt = SubledgerService.bankers_round(payment_amount)
        pay_dt = payment_date or date.today()

        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, bank_account_code)
        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, "1020")
        if not (bank_acc and ar_acc):
            raise ValueError("Required accounts (Bank or AR) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-PAY-{invoice_number}-{uuid.uuid4().hex[:6]}",
            entry_date=pay_dt,
            reference_type="customer_payment",
            narration=f"Payment received against Invoice #{invoice_number}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=bank_acc.id,
                debit_amount=pay_amt,
                credit_amount=Decimal("0.00"),
                description=f"Inflow for Inv #{invoice_number}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=ar_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=pay_amt,
                description=f"AR Settlement for Inv #{invoice_number}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    def calculate_ar_aging_buckets(
        invoices: List[Dict[str, Any]],
        as_of_date: date
    ) -> Dict[str, Decimal]:
        """
        Pillar 3.2: AR Aging Schedule (0-30, 31-60, 61-90, 90+ days).
        """
        buckets = {
            "current_0_30": Decimal("0.00"),
            "overdue_31_60": Decimal("0.00"),
            "overdue_61_90": Decimal("0.00"),
            "overdue_90_plus": Decimal("0.00"),
            "total_outstanding": Decimal("0.00")
        }

        for inv in invoices:
            outstanding = SubledgerService.bankers_round(inv.get("outstanding_balance", Decimal("0.00")))
            if outstanding <= Decimal("0.00"):
                continue

            inv_date = inv.get("issue_date") or as_of_date
            age_days = (as_of_date - inv_date).days

            if age_days <= 30:
                buckets["current_0_30"] += outstanding
            elif 31 <= age_days <= 60:
                buckets["overdue_31_60"] += outstanding
            elif 61 <= age_days <= 90:
                buckets["overdue_61_90"] += outstanding
            else:
                buckets["overdue_90_plus"] += outstanding

            buckets["total_outstanding"] += outstanding

        return buckets

    @staticmethod
    async def issue_credit_note(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        invoice_number: str,
        credit_note_number: str,
        return_subtotal: Decimal,
        cgst_rate: Decimal = Decimal("9.00"),
        sgst_rate: Decimal = Decimal("9.00"),
        igst_rate: Decimal = Decimal("0.00"),
        credit_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 3.3: Credit Note & Tax Output Reversal:
        DR 3010/4010 Revenue / Sales Returns = return_subtotal
        DR 2050 Output CGST                  = cgst_reversal
        DR 2051 Output SGST                  = sgst_reversal
        CR 1020 Accounts Receivable          = total_credit_note
        """
        cdt = credit_date or date.today()
        ret_sub = SubledgerService.bankers_round(return_subtotal)
        cgst_rev = SubledgerService.bankers_round(ret_sub * (cgst_rate / Decimal("100.00")))
        sgst_rev = SubledgerService.bankers_round(ret_sub * (sgst_rate / Decimal("100.00")))
        igst_rev = SubledgerService.bankers_round(ret_sub * (igst_rate / Decimal("100.00")))
        total_cr = ret_sub + cgst_rev + sgst_rev + igst_rev

        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, "1020")
        rev_acc = await LedgerService.get_account_by_code(session, tenant_id, "3010")
        cgst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2050")
        sgst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2051")
        igst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2052")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-CN-{credit_note_number}",
            entry_date=cdt,
            reference_type="credit_note",
            narration=f"Credit Note #{credit_note_number} against Invoice #{invoice_number}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = []
        # DR Revenue (Sales Return)
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=rev_acc.id,
            debit_amount=ret_sub,
            credit_amount=Decimal("0.00"),
            description=f"Sales Return reversal for CN #{credit_note_number}"
        ))

        # DR Taxes (Reversing collected liability)
        if igst_rev > 0 and igst_acc:
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=igst_acc.id,
                debit_amount=igst_rev,
                credit_amount=Decimal("0.00"),
                description=f"Output IGST Reversal for CN #{credit_note_number}"
            ))
        else:
            if cgst_rev > 0 and cgst_acc:
                lines.append(JournalLine(
                    journal_entry_id=entry.id,
                    tenant_id=tenant_id,
                    account_id=cgst_acc.id,
                    debit_amount=cgst_rev,
                    credit_amount=Decimal("0.00"),
                    description=f"Output CGST Reversal for CN #{credit_note_number}"
                ))
            if sgst_rev > 0 and sgst_acc:
                lines.append(JournalLine(
                    journal_entry_id=entry.id,
                    tenant_id=tenant_id,
                    account_id=sgst_acc.id,
                    debit_amount=sgst_rev,
                    credit_amount=Decimal("0.00"),
                    description=f"Output SGST Reversal for CN #{credit_note_number}"
                ))

        # CR Accounts Receivable
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=ar_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=total_cr,
            description=f"AR Reduction for CN #{credit_note_number}"
        ))

        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    async def write_off_bad_debt(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        invoice_number: str,
        write_off_amount: Decimal,
        bad_debt_account_code: str = "4040", # Legal / Bad Debt Expense
        write_off_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 3.4: Bad Debt Write-Off:
        DR 4040 / 5080 Bad Debt Expense
        CR 1020 Accounts Receivable
        Customer balance drops to 0; Tax ledger remains untouched unless relief claimed.
        """
        wo_amt = SubledgerService.bankers_round(write_off_amount)
        wo_dt = write_off_date or date.today()

        bad_debt_acc = await LedgerService.get_account_by_code(session, tenant_id, bad_debt_account_code)
        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, "1020")
        if not (bad_debt_acc and ar_acc):
            raise ValueError("Required accounts (Bad Debt Expense or AR) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-WO-{invoice_number}-{uuid.uuid4().hex[:6]}",
            entry_date=wo_dt,
            reference_type="bad_debt_writeoff",
            narration=f"Uncollectible debt write-off for Invoice #{invoice_number}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=bad_debt_acc.id,
                debit_amount=wo_amt,
                credit_amount=Decimal("0.00"),
                description=f"Bad debt expense write-off for Inv #{invoice_number}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=ar_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=wo_amt,
                description=f"AR derecognition for uncollectible Inv #{invoice_number}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    # =========================================================================
    # PILLAR 4: ACCOUNTS PAYABLE (AP) & STATUTORY WITHHOLDING (TDS)
    # =========================================================================

    @staticmethod
    async def post_vendor_bill_with_tds(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        vendor_name: str,
        bill_number: str,
        base_amount: Decimal,
        gst_rate: Decimal = Decimal("18.00"),
        tds_section: str = "194J", # 10% on professional fees
        tds_rate: Decimal = Decimal("10.00"),
        expense_account_code: str = "4040", # Legal & Professional Retainer
        is_interstate: bool = True,
        bill_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Pillar 4.1: Vendor Bill Ingestion with Statutory Withholding (TDS):
        DR 4040 Legal Expense       = Base Amount (₹100,000)
        DR 1032 GST Input Credit     = 18% IGST (₹18,000)
        CR 2060 TDS Payable u/s 194J = 10% on Base (₹10,000)
        CR 2040 Vendor AP (Creditors) = Net Payable (₹108,000)
        Total Debits (₹118,000) == Total Credits (₹118,000)
        """
        b_dt = bill_date or date.today()
        base = SubledgerService.bankers_round(base_amount)
        gst_amt = SubledgerService.bankers_round(base * (gst_rate / Decimal("100.00")))
        tds_amt = SubledgerService.bankers_round(base * (tds_rate / Decimal("100.00")))
        net_vendor_payable = (base + gst_amt) - tds_amt

        exp_acc = await LedgerService.get_account_by_code(session, tenant_id, expense_account_code)
        input_gst_acc = await LedgerService.get_account_by_code(session, tenant_id, "1032" if is_interstate else "1030")
        tds_acc = await LedgerService.get_account_by_code(session, tenant_id, "2060")
        ap_acc = await LedgerService.get_account_by_code(session, tenant_id, "2040")

        if not (exp_acc and input_gst_acc and tds_acc and ap_acc):
            raise ValueError("Required accounts (Expense, GST Input, TDS Payable, or AP) not found.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-BILL-{bill_number}",
            entry_date=b_dt,
            reference_type="vendor_bill",
            narration=f"Vendor Bill #{bill_number} from {vendor_name} with TDS u/s {tds_section}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            # 1. DR Expense
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=exp_acc.id,
                debit_amount=base,
                credit_amount=Decimal("0.00"),
                description=f"Base expense for Bill #{bill_number}"
            ),
            # 2. DR GST Input Credit
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=input_gst_acc.id,
                debit_amount=gst_amt,
                credit_amount=Decimal("0.00"),
                description=f"Input GST credit on Bill #{bill_number}"
            ),
            # 3. CR TDS Payable
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=tds_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=tds_amt,
                description=f"Statutory withholding TDS u/s {tds_section} on Bill #{bill_number}"
            ),
            # 4. CR Vendor AP
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=ap_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=net_vendor_payable,
                description=f"Net accounts payable to {vendor_name} for Bill #{bill_number}"
            )
        ]

        total_deb = sum(l.debit_amount for l in lines)
        total_crd = sum(l.credit_amount for l in lines)
        if total_deb != total_crd:
            raise ValueError(f"Imbalanced AP entry: {total_deb} vs {total_crd}")

        session.add_all(lines)
        await session.flush()

        return {
            "journal_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "base_amount": base,
            "gst_amount": gst_amt,
            "tds_amount": tds_amt,
            "net_payable": net_vendor_payable,
            "total_debits": total_deb,
            "total_credits": total_crd
        }

    @staticmethod
    async def issue_vendor_debit_note(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        bill_number: str,
        debit_note_number: str,
        return_base_amount: Decimal,
        gst_rate: Decimal = Decimal("18.00"),
        expense_account_code: str = "4040",
        is_interstate: bool = True,
        dn_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 4.2: Vendor Debit Note (Purchase Return):
        DR 2040 Vendor AP           = Total Return (Base + GST)
        CR 4040 Expense / Return    = Return Base
        CR 1032 GST Input Credit    = GST Reversal
        """
        d_dt = dn_date or date.today()
        base = SubledgerService.bankers_round(return_base_amount)
        gst_rev = SubledgerService.bankers_round(base * (gst_rate / Decimal("100.00")))
        total_dn = base + gst_rev

        ap_acc = await LedgerService.get_account_by_code(session, tenant_id, "2040")
        exp_acc = await LedgerService.get_account_by_code(session, tenant_id, expense_account_code)
        input_gst_acc = await LedgerService.get_account_by_code(session, tenant_id, "1032" if is_interstate else "1030")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-DN-{debit_note_number}",
            entry_date=d_dt,
            reference_type="vendor_debit_note",
            narration=f"Vendor Debit Note #{debit_note_number} for purchase return on Bill #{bill_number}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=ap_acc.id,
                debit_amount=total_dn,
                credit_amount=Decimal("0.00"),
                description=f"AP reduction for Debit Note #{debit_note_number}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=exp_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=base,
                description=f"Purchase return reversal for Debit Note #{debit_note_number}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=input_gst_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=gst_rev,
                description=f"Input GST credit reversal for Debit Note #{debit_note_number}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    async def remit_statutory_tds(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        tds_amount: Decimal,
        bank_account_code: str = "1010",
        remit_date: Optional[date] = None,
        challan_ref: str = "CHALLAN-ITNS281",
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 4.3: Statutory TDS Remittance to Government:
        DR 2060 TDS Payable
        CR 1010 Bank Current Account
        TDS Liability zeroes out; bank balance reflects tax outflow.
        """
        amt = SubledgerService.bankers_round(tds_amount)
        r_dt = remit_date or date.today()

        tds_acc = await LedgerService.get_account_by_code(session, tenant_id, "2060")
        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, bank_account_code)

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-TDS-REMIT-{uuid.uuid4().hex[:6]}",
            entry_date=r_dt,
            reference_type="tds_challan_remittance",
            narration=f"Government TDS remittance payment via {challan_ref}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=tds_acc.id,
                debit_amount=amt,
                credit_amount=Decimal("0.00"),
                description=f"TDS tax liability discharged: {challan_ref}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=bank_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=amt,
                description=f"Bank outflow for statutory TDS remittance: {challan_ref}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    # =========================================================================
    # PILLAR 5: ADVANCE PAYMENTS, UNEARNED REVENUE & ALLOCATION
    # =========================================================================

    @staticmethod
    async def receive_customer_advance(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        customer_name: str,
        amount: Decimal,
        advance_account_code: str = "2040", # Customer Advances / Unearned Revenue (Liability)
        bank_account_code: str = "1010",
        advance_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 5.1: Customer Advance Received (Unearned Revenue):
        DR 1010 Bank Current Account
        CR 2040 Customer Advances (Current Liability)
        P&L revenue is strictly untouched.
        """
        adv_amt = SubledgerService.bankers_round(amount)
        adv_dt = advance_date or date.today()

        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, bank_account_code)
        adv_acc = await LedgerService.get_account_by_code(session, tenant_id, advance_account_code)

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-ADV-{uuid.uuid4().hex[:6]}",
            entry_date=adv_dt,
            reference_type="customer_advance",
            narration=f"Advance payment received from {customer_name} pending delivery",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=bank_acc.id,
                debit_amount=adv_amt,
                credit_amount=Decimal("0.00"),
                description=f"Bank deposit of customer advance from {customer_name}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=adv_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=adv_amt,
                description=f"Unearned customer advance liability from {customer_name}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    async def offset_advance_against_invoice(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        invoice_number: str,
        advance_applied: Decimal,
        net_ar_remaining: Decimal,
        total_revenue_recognized: Decimal,
        advance_account_code: str = "2040",
        revenue_account_code: str = "3010",
        ar_account_code: str = "1020",
        offset_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 5.2: Subsequent Invoice Offset:
        DR 2040 Customer Advances (Offset Liability) = ₹50,000
        DR 1020 Accounts Receivable (Net Due)        = ₹30,000
        CR 3010 Operating Revenue (Total Value)      = ₹80,000
        Customer advance liability zeroes out; AR reflects net due.
        """
        adv_applied = SubledgerService.bankers_round(advance_applied)
        net_ar = SubledgerService.bankers_round(net_ar_remaining)
        tot_rev = SubledgerService.bankers_round(total_revenue_recognized)
        off_dt = offset_date or date.today()

        if adv_applied + net_ar != tot_rev:
            raise ValueError(f"Offset invariant violation: {adv_applied} + {net_ar} != {tot_rev}")

        adv_acc = await LedgerService.get_account_by_code(session, tenant_id, advance_account_code)
        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, ar_account_code)
        rev_acc = await LedgerService.get_account_by_code(session, tenant_id, revenue_account_code)

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-OFFSET-{invoice_number}",
            entry_date=off_dt,
            reference_type="advance_offset",
            narration=f"Offset advance against Invoice #{invoice_number}",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=adv_acc.id,
                debit_amount=adv_applied,
                credit_amount=Decimal("0.00"),
                description=f"Offset advance against Inv #{invoice_number}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=ar_acc.id,
                debit_amount=net_ar,
                credit_amount=Decimal("0.00"),
                description=f"Net debtor claim for Inv #{invoice_number}"
            ),
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=rev_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=tot_rev,
                description=f"Full revenue recognized on Inv #{invoice_number}"
            )
        ]
        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    async def match_many_to_many_payments(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        total_payment: Decimal,
        allocations: List[Dict[str, Any]], # [{"invoice_number": str, "allocated_amount": Decimal}]
        bank_account_code: str = "1010",
        payment_date: Optional[date] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Pillar 5.3: Cross-Voucher Many-to-Many Matching:
        Single payment of ₹100,000 covering 3 open invoices (₹30k, ₹45k, ₹25k).
        DR 1010 Bank Current Account = Total Payment (₹100,000)
        CR 1020 Accounts Receivable  = Inv 1 (₹30,000)
        CR 1020 Accounts Receivable  = Inv 2 (₹45,000)
        CR 1020 Accounts Receivable  = Inv 3 (₹25,000)
        Zero orphan residues.
        """
        tot_pay = SubledgerService.bankers_round(total_payment)
        p_dt = payment_date or date.today()

        allocated_sum = sum(SubledgerService.bankers_round(a["allocated_amount"]) for a in allocations)
        if tot_pay != allocated_sum:
            raise ValueError(f"Allocation mismatch: Total payment ({tot_pay}) != Allocations sum ({allocated_sum})")

        bank_acc = await LedgerService.get_account_by_code(session, tenant_id, bank_account_code)
        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, "1020")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-M2M-{uuid.uuid4().hex[:6]}",
            entry_date=p_dt,
            reference_type="multi_payment_match",
            narration=f"Lump-sum payment allocation across {len(allocations)} open invoices",
            status="posted",
            is_posted=True,
            created_by=created_by
        )
        session.add(entry)
        await session.flush()

        lines = [
            JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=bank_acc.id,
                debit_amount=tot_pay,
                credit_amount=Decimal("0.00"),
                description=f"Lump sum inflow allocated across {len(allocations)} invoices"
            )
        ]

        for alloc in allocations:
            inv_num = alloc["invoice_number"]
            amt = SubledgerService.bankers_round(alloc["allocated_amount"])
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=ar_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=amt,
                description=f"Settlement allocation for Inv #{inv_num}"
            ))

        session.add_all(lines)
        await session.flush()
        return entry
