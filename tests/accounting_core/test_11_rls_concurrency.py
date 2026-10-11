"""
Pillar 11: Multi-Tenant Row-Level Security (RLS) & Concurrency Audit Tests
Asserts:
1. PostgreSQL Row-Level Security (RLS) Penetration:
   - Tenant A (Acme Labs) posts 10 journal entries and invoices.
   - Tenant B (Zenith Commerce) executes raw SQL across all tables.
   - Cross-tenant leakage is ZERO: Tenant B sees 0 rows from Tenant A even with explicit WHERE tenant_id clauses.
2. High-Concurrency Posting (Race Condition Test):
   - 50 concurrent async workers posting journals with with_for_update() row locking.
   - Zero deadlocks.
   - Exact mathematical balance preserved: ₹50,000.00 DR == ₹50,000.00 CR, zero drift.
"""

from decimal import Decimal
from datetime import date
import uuid
import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func

from app.models.tenant import Tenant
from app.models.ledger import ChartOfAccounts, JournalEntry, JournalLine
from app.models.invoice import Invoice
from app.services.ledger_service import LedgerService
from tests.accounting_core.conftest import TestAsyncSessionLocal, test_async_engine


@pytest.mark.asyncio
async def test_01_rls_tenant_isolation_penetration(async_db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant):
    """
    Pillar 11.1: PostgreSQL Row-Level Security (RLS) Penetration Test:
    1. Authenticate as Tenant A (Acme Labs).
       Set session variable: SET LOCAL app.current_tenant = tenant_a.id.
       Post 10 journal entries and 2 invoices.
    2. Authenticate as Tenant B (Zenith Commerce).
       Set session variable: SET LOCAL app.current_tenant = tenant_b.id.
       Attempt raw SQL penetration:
       - SELECT * FROM journal_entries;
       - SELECT * FROM journal_lines;
       - SELECT * FROM chart_of_accounts;
       - SELECT * FROM invoices;
       - Explicit target query: SELECT * FROM journal_entries WHERE tenant_id = tenant_a.id;
    3. Assert Tenant B retrieves ZERO rows belonging to Tenant A.
       Cross-tenant leakage is 0.00%.
    """
    # -------------------------------------------------------------
    # PHASE 1: Tenant A Context & Postings
    # -------------------------------------------------------------
    await async_db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true);"),
        {"tid": str(tenant_a.id)}
    )

    bank_a = await LedgerService.get_account_by_code(async_db, tenant_a.id, "1010")
    rev_a = await LedgerService.get_account_by_code(async_db, tenant_a.id, "3010")

    # Post 10 journal entries under Tenant A
    for i in range(10):
        entry_a = JournalEntry(
            tenant_id=tenant_a.id,
            entry_number=f"JV-RLS-A-{i:03d}-{uuid.uuid4().hex[:4]}",
            entry_date=date.today(),
            narration=f"Tenant A Confidential Transaction #{i}",
            status="posted",
            is_posted=True
        )
        async_db.add(entry_a)
        await async_db.flush()

        async_db.add_all([
            JournalLine(journal_entry_id=entry_a.id, tenant_id=tenant_a.id, account_id=bank_a.id, debit_amount=Decimal("1000.00"), credit_amount=Decimal("0.00")),
            JournalLine(journal_entry_id=entry_a.id, tenant_id=tenant_a.id, account_id=rev_a.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("1000.00"))
        ])
        await async_db.flush()

    from app.models.invoice import Contact
    contact_a = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Confidential Customer A",
        is_customer=True,
        state_code="29",
        billing_address="Bengaluru, Karnataka"
    )
    async_db.add(contact_a)
    await async_db.flush()

    # Create 2 confidential invoices under Tenant A
    for j in range(2):
        inv_a = Invoice(
            tenant_id=tenant_a.id,
            contact_id=contact_a.id,
            invoice_number=f"INV-CONFIDENTIAL-A-{j:02d}",
            issue_date=date.today(),
            due_date=date.today(),
            place_of_supply="29",
            subtotal=Decimal("10000.00"),
            grand_total=Decimal("11800.00"),
            status="sent"
        )
        async_db.add(inv_a)
    await async_db.flush()

    # Switch to application role to enforce RLS policies
    await async_db.execute(text("SET LOCAL ROLE b00k5_app;"))
    await async_db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true);"),
        {"tid": str(tenant_a.id)}
    )

    # Verify Tenant A sees all 10 entries and 2 invoices
    count_a_entries = (await async_db.execute(text("SELECT count(*) FROM journal_entries;"))).scalar_one()
    assert count_a_entries == 10

    count_a_invoices = (await async_db.execute(text("SELECT count(*) FROM invoices;"))).scalar_one()
    assert count_a_invoices == 2

    # -------------------------------------------------------------
    # PHASE 2: Tenant B Context & Penetration Attack
    # -------------------------------------------------------------
    await async_db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true);"),
        {"tid": str(tenant_b.id)}
    )

    # Attack 1: Broad SELECT * without filters
    entries_b = (await async_db.execute(text("SELECT tenant_id FROM journal_entries;"))).scalars().all()
    assert len(entries_b) == 0, "RLS Leakage! Tenant B read Tenant A journal entries"

    lines_b = (await async_db.execute(text("SELECT tenant_id FROM journal_lines;"))).scalars().all()
    assert len(lines_b) == 0, "RLS Leakage! Tenant B read Tenant A journal lines"

    invoices_b = (await async_db.execute(text("SELECT tenant_id FROM invoices;"))).scalars().all()
    assert len(invoices_b) == 0, "RLS Leakage! Tenant B read Tenant A invoices"

    # COA: Tenant B sees only its own accounts
    coas_b = (await async_db.execute(text("SELECT DISTINCT tenant_id FROM chart_of_accounts;"))).scalars().all()
    for tid in coas_b:
        assert tid == tenant_b.id, "RLS Leakage! Tenant B retrieved Tenant A COA rows"

    # Attack 2: Targeted hostile query explicitly querying Tenant A's UUID
    hostile_query = await async_db.execute(
        text("SELECT * FROM journal_entries WHERE tenant_id = :victim_id;"),
        {"victim_id": str(tenant_a.id)}
    )
    hostile_results = hostile_query.fetchall()
    assert len(hostile_results) == 0, "RLS Bypass Exploit! Tenant B targeted Tenant A rows directly"

    # Attack 3: Hostile UPDATE / DELETE attempted across tenants
    delete_attack = await async_db.execute(
        text("DELETE FROM journal_entries WHERE tenant_id = :victim_id;"),
        {"victim_id": str(tenant_a.id)}
    )
    assert delete_attack.rowcount == 0, "RLS Security Violation! Tenant B deleted Tenant A rows"


@pytest.mark.asyncio
async def test_02_high_concurrency_posting_race_condition():
    """
    Pillar 11.2: High-Concurrency Posting Race Condition Test:
    - Spawn 50 simultaneous asynchronous workers firing journal postings
      against the exact same Bank (1010) and Revenue (3010) accounts.
    - Each worker locks the target account row with SELECT ... FOR UPDATE.
    - Assert:
      1. Zero deadlocks across 50 concurrent transactions.
      2. Exactly 50 entries posted with atomic balance.
      3. Total Debit = 50 * ₹1,000 = ₹50,000.00.
      4. Total Credit = 50 * ₹1,000 = ₹50,000.00.
      5. Drift = ₹0.00.
    """
    tenant_id = uuid.uuid4()

    # 1. Setup isolated tenant and COA in an independent session
    async with TestAsyncSessionLocal() as setup_session:
        tenant = Tenant(
            id=tenant_id,
            legal_name=f"Concurrency Stress Test Org {tenant_id.hex[:6]}",
            cin=f"U72900KA2026PTC{tenant_id.hex[:4].upper()}",
            gstin=f"29AABCS{tenant_id.hex[:4].upper()}1Z5",
            pan=f"AABCS{tenant_id.hex[:4].upper()}",
            state_code="29",
            registered_office="Indiranagar, Bengaluru, Karnataka 560038"
        )
        setup_session.add(tenant)
        await setup_session.flush()

        bank_acc = ChartOfAccounts(
            tenant_id=tenant_id,
            code="1010",
            name="Operating HDFC Account",
            type="asset",
            sub_type="bank",
            normal_balance="debit",
            is_leaf=True,
            is_active=True
        )
        rev_acc = ChartOfAccounts(
            tenant_id=tenant_id,
            code="3010",
            name="SaaS Subscriptions Revenue",
            type="revenue",
            sub_type="operating_revenue",
            normal_balance="credit",
            is_leaf=True,
            is_active=True
        )
        setup_session.add_all([bank_acc, rev_acc])
        await setup_session.commit()
        bank_id = bank_acc.id
        rev_id = rev_acc.id

    # 2. Define concurrent worker
    concurrency_count = 50
    amount_per_worker = Decimal("1000.00")

    async def worker_post_journal(worker_index: int):
        async with TestAsyncSessionLocal() as session:
            async with session.begin():
                # Set replication role and RLS context
                await session.execute(text("SET LOCAL session_replication_role = 'origin';"))
                await session.execute(
                    text("SELECT set_config('app.current_tenant', :tid, true);"),
                    {"tid": str(tenant_id)}
                )

                # Row-level lock on Bank account to serialize concurrent updates
                lock_stmt = select(ChartOfAccounts).where(
                    ChartOfAccounts.id == bank_id
                ).with_for_update()
                await session.execute(lock_stmt)

                # Post balanced journal entry
                entry = JournalEntry(
                    tenant_id=tenant_id,
                    entry_number=f"JV-CONC-{worker_index:03d}-{uuid.uuid4().hex[:4]}",
                    entry_date=date.today(),
                    narration=f"Concurrent Worker #{worker_index} Subscription Charge",
                    status="posted",
                    is_posted=True
                )
                session.add(entry)
                await session.flush()

                session.add_all([
                    JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=bank_id, debit_amount=amount_per_worker, credit_amount=Decimal("0.00")),
                    JournalLine(journal_entry_id=entry.id, tenant_id=tenant_id, account_id=rev_id, debit_amount=Decimal("0.00"), credit_amount=amount_per_worker)
                ])
                await session.flush()

    # 3. Fire all 50 workers concurrently
    tasks = [worker_post_journal(i) for i in range(concurrency_count)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check for deadlocks or exceptions
    for idx, res in enumerate(results):
        if isinstance(res, Exception):
            pytest.fail(f"Worker {idx} failed with deadlock/concurrency exception: {res}")

    # 4. Verify aggregated totals in database
    async with TestAsyncSessionLocal() as verify_session:
        sum_stmt = select(
            func.count(JournalEntry.id),
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).select_from(JournalEntry).join(
            JournalLine, JournalEntry.id == JournalLine.journal_entry_id
        ).where(
            JournalEntry.tenant_id == tenant_id
        )

        row = (await verify_session.execute(sum_stmt)).one()
        # Each entry has 2 lines, so line count = 100
        total_dr = row[1]
        total_cr = row[2]

        expected_total = amount_per_worker * concurrency_count # ₹50,000.00
        assert total_dr == expected_total, f"Drift detected! Expected {expected_total}, got {total_dr}"
        assert total_cr == expected_total, f"Drift detected! Expected {expected_total}, got {total_cr}"
        assert (total_dr - total_cr) == Decimal("0.00"), "Fatal Failure: Ledger is unbalanced under concurrency!"

        # Cleanup test tenant
        await verify_session.execute(text("SET session_replication_role = 'replica';"))
        await verify_session.execute(text("DELETE FROM journal_lines WHERE tenant_id = :tid;"), {"tid": str(tenant_id)})
        await verify_session.execute(text("DELETE FROM journal_entries WHERE tenant_id = :tid;"), {"tid": str(tenant_id)})
        await verify_session.execute(text("DELETE FROM chart_of_accounts WHERE tenant_id = :tid;"), {"tid": str(tenant_id)})
        await verify_session.execute(text("DELETE FROM tenants WHERE id = :tid;"), {"tid": str(tenant_id)})
        await verify_session.execute(text("SET session_replication_role = 'origin';"))
        await verify_session.commit()
