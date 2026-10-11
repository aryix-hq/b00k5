from decimal import Decimal
from datetime import date
from typing import Dict, Any, List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.invoice import Invoice

class LedgerService:
    @staticmethod
    async def get_account_by_code(session: AsyncSession, tenant_id: uuid.UUID, code: str) -> Optional[ChartOfAccounts]:
        stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.tenant_id == tenant_id,
            ChartOfAccounts.code == code
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def post_invoice_journal(
        session: AsyncSession,
        invoice: Invoice,
        created_by_user_id: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Creates a balanced double-entry journal entry for an issued Tax Invoice:
        DR 1020 Accounts Receivable  = Grand Total
        CR 4010 Operating Revenue     = Subtotal
        CR 2020 Output CGST           = CGST Total (if intra-state)
        CR 2021 Output SGST           = SGST Total (if intra-state)
        CR 2022 Output IGST           = IGST Total (if inter-state)
        """
        tenant_id = invoice.tenant_id

        # Fetch required Schedule III accounts
        ar_acc = await LedgerService.get_account_by_code(session, tenant_id, "1020")
        rev_acc = await LedgerService.get_account_by_code(session, tenant_id, "3010")
        cgst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2050")
        sgst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2051")
        igst_acc = await LedgerService.get_account_by_code(session, tenant_id, "2052")

        if not (ar_acc and rev_acc):
            raise ValueError("Required Schedule III accounts (1020 Trade Receivables, 3010 Revenue from Operations) not found.")

        # Create Journal Entry header
        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=f"JV-INV-{invoice.invoice_number}",
            entry_date=invoice.issue_date,
            reference_type="invoice",
            reference_id=invoice.id,
            narration=f"Tax Invoice #{invoice.invoice_number} issued to contact",
            status="posted",
            is_posted=True,
            created_by=created_by_user_id
        )
        session.add(entry)
        await session.flush()

        lines = []
        # 1. DR Accounts Receivable
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=ar_acc.id,
            debit_amount=invoice.grand_total,
            credit_amount=Decimal("0.00"),
            description=f"Debtor claim for Inv #{invoice.invoice_number}"
        ))

        # 2. CR Operating Revenue
        lines.append(JournalLine(
            journal_entry_id=entry.id,
            tenant_id=tenant_id,
            account_id=rev_acc.id,
            debit_amount=Decimal("0.00"),
            credit_amount=invoice.subtotal,
            description=f"Revenue recognized for Inv #{invoice.invoice_number}"
        ))

        # 3. CR Output GST Tax accounts
        if invoice.is_interstate and invoice.igst_total > Decimal("0.00") and igst_acc:
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=igst_acc.id,
                debit_amount=Decimal("0.00"),
                credit_amount=invoice.igst_total,
                description=f"Output IGST collected on Inv #{invoice.invoice_number}"
            ))
        else:
            if invoice.cgst_total > Decimal("0.00") and cgst_acc:
                lines.append(JournalLine(
                    journal_entry_id=entry.id,
                    tenant_id=tenant_id,
                    account_id=cgst_acc.id,
                    debit_amount=Decimal("0.00"),
                    credit_amount=invoice.cgst_total,
                    description=f"Output CGST collected on Inv #{invoice.invoice_number}"
                ))
            if invoice.sgst_total > Decimal("0.00") and sgst_acc:
                lines.append(JournalLine(
                    journal_entry_id=entry.id,
                    tenant_id=tenant_id,
                    account_id=sgst_acc.id,
                    debit_amount=Decimal("0.00"),
                    credit_amount=invoice.sgst_total,
                    description=f"Output SGST collected on Inv #{invoice.invoice_number}"
                ))

        # Verify balanced entry (sum of debits == sum of credits)
        total_debits = sum(line.debit_amount for line in lines)
        total_credits = sum(line.credit_amount for line in lines)
        if total_debits != total_credits:
            raise ValueError(f"Imbalanced Journal Entry! Debits: {total_debits}, Credits: {total_credits}")

        session.add_all(lines)
        return entry

    @staticmethod
    async def create_journal_entry(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        payload,
        created_by_user_id: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Creates an immutable, strictly balanced double-entry Journal Entry with explicit row-locking
        and mathematical verification: Sum(Debits) - Sum(Credits) = 0.
        """
        # Validate zero-sum balance
        total_debits = sum(line.debit_amount for line in payload.lines)
        total_credits = sum(line.credit_amount for line in payload.lines)
        discrepancy = abs(total_debits - total_credits)
        if discrepancy != Decimal("0.00"):
            raise ValueError(f"Inviolable Balance Error: Debits ({total_debits}) != Credits ({total_credits}). Difference: {discrepancy}")

        # Check duplicate entry number
        dup_stmt = select(JournalEntry).where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.entry_number == payload.entry_number
        )
        dup = (await session.execute(dup_stmt)).scalar_one_or_none()
        if dup:
            raise ValueError(f"Journal entry number '{payload.entry_number}' already exists.")

        # Lock referenced account rows for update
        account_ids = [line.account_id for line in payload.lines]
        acc_stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.tenant_id == tenant_id,
            ChartOfAccounts.id.in_(account_ids)
        ).with_for_update()
        locked_accounts = (await session.execute(acc_stmt)).scalars().all()
        if len(locked_accounts) != len(set(account_ids)):
            raise ValueError("One or more referenced Chart of Accounts records do not exist or belong to another organization.")

        # Invariant checks on accounts: must be leaf and active
        for acc in locked_accounts:
            if not getattr(acc, "is_leaf", True):
                raise ValueError(f"Posting Invariant Violation: Direct transaction posting to parent account '{acc.code} - {acc.name}' is prohibited. Post to a leaf child account instead.")
            if not acc.is_active:
                raise ValueError(f"Posting Invariant Violation: Cannot post to deactivated account '{acc.code} - {acc.name}'.")

        entry = JournalEntry(
            tenant_id=tenant_id,
            entry_number=payload.entry_number,
            entry_date=payload.entry_date,
            reference_type=payload.reference_type or "manual_jv",
            reference_id=payload.reference_id,
            narration=payload.narration,
            status="posted",
            is_posted=True,
            created_by=created_by_user_id
        )
        session.add(entry)
        await session.flush()

        lines = []
        for line in payload.lines:
            lines.append(JournalLine(
                journal_entry_id=entry.id,
                tenant_id=tenant_id,
                account_id=line.account_id,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                description=line.description
            ))

        session.add_all(lines)
        await session.flush()
        return entry

    @staticmethod
    async def get_trial_balance(session: AsyncSession, tenant_id: uuid.UUID) -> Dict[str, Any]:
        """
        Calculates the complete Trial Balance report by summing journal lines.
        """
        # Fetch all accounts for tenant
        acc_stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.tenant_id == tenant_id,
            ChartOfAccounts.is_active == True
        ).order_by(ChartOfAccounts.code)
        acc_res = await session.execute(acc_stmt)
        accounts = acc_res.scalars().all()

        items = []
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")

        for acc in accounts:
            sum_stmt = select(
                func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("total_debits"),
                func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("total_credits")
            ).where(
                JournalLine.tenant_id == tenant_id,
                JournalLine.account_id == acc.id
            )
            res = await session.execute(sum_stmt)
            row = res.one()
            d_sum = row.total_debits
            c_sum = row.total_credits

            # Calculate net balance according to normal nature
            if acc.normal_balance == "debit":
                net = d_sum - c_sum
                debit_bal = net if net > 0 else Decimal("0.00")
                credit_bal = abs(net) if net < 0 else Decimal("0.00")
            else:
                net = c_sum - d_sum
                credit_bal = net if net > 0 else Decimal("0.00")
                debit_bal = abs(net) if net < 0 else Decimal("0.00")

            if debit_bal > 0 or credit_bal > 0:
                items.append({
                    "account_id": acc.id,
                    "code": acc.code,
                    "name": acc.name,
                    "type": acc.type,
                    "debit_balance": debit_bal,
                    "credit_balance": credit_bal
                })
                total_debits += debit_bal
                total_credits += credit_bal

        return {
            "tenant_id": tenant_id,
            "as_of_date": date.today(),
            "items": items,
            "total_debits": total_debits,
            "total_credits": total_credits,
            "is_balanced": total_debits == total_credits
        }

    @staticmethod
    async def deactivate_account(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        account_id: uuid.UUID
    ) -> ChartOfAccounts:
        """
        Pillar 2.3: Deactivation Invariant:
        System blocks deactivation if account has a non-zero balance.
        """
        acc = await session.get(ChartOfAccounts, account_id)
        if not acc or acc.tenant_id != tenant_id:
            raise ValueError("Chart of accounts record not found.")

        sum_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
        ).where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == account_id
        )
        row = (await session.execute(sum_stmt)).one()
        d_sum, c_sum = row.d, row.c
        net_balance = abs(d_sum - c_sum)

        if net_balance > Decimal("0.00"):
            raise ValueError(
                f"Deactivation Invariant Error: Cannot deactivate account '{acc.code} - {acc.name}' "
                f"with non-zero balance of ₹{net_balance}. Balance must be transferred or journaled to zero first."
            )

        acc.is_active = False
        await session.flush()
        return acc

    @staticmethod
    async def get_account_balance_with_rollups(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        account_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> Decimal:
        """
        Pillar 2.2: Account Tree & Roll-Up:
        Recursively computes aggregates from child nodes without timeout.
        """
        target_date = as_of_date or date.today()
        parent_acc = await session.get(ChartOfAccounts, account_id)
        if not parent_acc or parent_acc.tenant_id != tenant_id:
            raise ValueError("Account not found.")

        # Collect all descendant IDs
        descendant_ids = [account_id]

        async def collect_children(p_id: uuid.UUID):
            c_stmt = select(ChartOfAccounts.id).where(
                ChartOfAccounts.tenant_id == tenant_id,
                ChartOfAccounts.parent_id == p_id
            )
            c_ids = (await session.execute(c_stmt)).scalars().all()
            for cid in c_ids:
                descendant_ids.append(cid)
                await collect_children(cid)

        await collect_children(account_id)

        sum_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")).label("d"),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")).label("c")
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id.in_(descendant_ids),
            JournalEntry.entry_date <= target_date,
            JournalEntry.status == "posted"
        )
        row = (await session.execute(sum_stmt)).one()
        d_sum, c_sum = row.d, row.c

        if parent_acc.normal_balance == "debit":
            return d_sum - c_sum
        else:
            return c_sum - d_sum

