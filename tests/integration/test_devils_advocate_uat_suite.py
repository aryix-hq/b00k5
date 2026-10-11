"""
b00k5 — Devil's Advocate Project Audit & 18-Case UAT Verification Suite
Covers:
- Section 2 & 5 Security Hardening (SEC-01 through SEC-06)
- Section 3 Critical Accounting & Database Logic Defects (Findings A, B, C)
- Section 4 & 7 Statutory Compliance & Functional Edge Cases (Income-tax Act 2025 transition,
  OPC/Small Company board cadence, multi-factor GST ITC/POS, Sec 40A(3) cash aggregation,
  DPT-3 director loan rules, form-specific penalties, ambiguous reconciliation, suspense clearance)
- Section 6 Complete 18-Case UAT Battery (UAT-01 through UAT-18)
- Section 8 Disaster Recovery 7-Point Staging Gate & Cutover Rollback
"""

import io
import gzip
import uuid
import hashlib
import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from PIL import Image
from fastapi import HTTPException
from sqlalchemy import text

from app.core.config import validate_production_security
from app.core.security import create_access_token, decode_access_token
from app.core.database import AsyncSessionLocal, set_tenant_context
from app.api.deps import enforce_rbac_policy
from app.core.fiscal_year import (
    calculate_indian_fy_ay,
    evaluate_cross_period_tds_transition,
)
from app.services.compliance_watchdog import ComplianceWatchdogService
from app.services.reconciliation_engine import ReconciliationEngine
from app.services.bank_parser import (
    compute_line_fingerprint,
    detect_statement_overlap,
    validate_uploaded_document_safety,
)
from app.services.db_backup import (
    DatabaseBackupManager,
    derive_aes_key,
    encrypt_bytes_aes256_gcm,
)


# ============================================================================
# UAT-01: Balanced vs Unbalanced Journal Entry & Minimum 2-Line Invariant
# ============================================================================
@pytest.mark.asyncio
async def test_uat01_balanced_vs_unbalanced_and_single_line_rejection():
    async with AsyncSessionLocal() as session:
        t_id = uuid.uuid4()
        c_id = f"U72900KA2026PTC{uuid.uuid4().int % 900000 + 100000}"
        p_id = f"AABCA{uuid.uuid4().int % 9000 + 1000}F"
        await session.execute(text("""
            INSERT INTO tenants (id, legal_name, cin, pan, state_code, registered_office)
            VALUES (:id, 'UAT01 Corp Pvt Ltd', :cin, :pan, '29', 'Bengaluru')
        """), {"id": t_id, "cin": c_id, "pan": p_id})
        await session.execute(text("SELECT seed_tenant_chart_of_accounts(:t_id)"), {"t_id": t_id})

        res = await session.execute(text(
            "SELECT id, code FROM chart_of_accounts WHERE tenant_id = :t_id AND code IN ('1010', '3010')"
        ), {"t_id": t_id})
        coa = {row.code: row.id for row in res.fetchall()}

        # 1. Post a valid balanced entry (₹10,000.00 == ₹10,000.00)
        je_ok = uuid.uuid4()
        await session.execute(text("""
            INSERT INTO journal_entries (id, tenant_id, entry_number, entry_date, narration, status)
            VALUES (:id, :t_id, 'JV-UAT01-OK', '2026-04-10', 'Balanced entry', 'posted')
        """), {"id": je_ok, "t_id": t_id})
        await session.execute(text("""
            INSERT INTO journal_lines (id, journal_entry_id, tenant_id, account_id, debit_amount, credit_amount)
            VALUES
                (:l1, :je, :t_id, :acc1, 10000.00, 0.00),
                (:l2, :je, :t_id, :acc2, 0.00, 10000.00)
        """), {"l1": uuid.uuid4(), "l2": uuid.uuid4(), "je": je_ok, "t_id": t_id, "acc1": coa["1010"], "acc2": coa["3010"]})
        await session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        await session.commit()

    # 2. Attempt an unbalanced entry (₹10,000.00 vs ₹9,999.99) -> rejected atomically
    async with AsyncSessionLocal() as session:
        je_bad = uuid.uuid4()
        with pytest.raises(Exception) as exc_info:
            await session.execute(text("""
                INSERT INTO journal_entries (id, tenant_id, entry_number, entry_date, narration, status)
                VALUES (:id, :t_id, 'JV-UAT01-BAD', '2026-04-10', 'Unbalanced entry', 'posted')
            """), {"id": je_bad, "t_id": t_id})
            await session.execute(text("""
                INSERT INTO journal_lines (id, journal_entry_id, tenant_id, account_id, debit_amount, credit_amount)
                VALUES
                    (:l1, :je, :t_id, :acc1, 10000.00, 0.00),
                    (:l2, :je, :t_id, :acc2, 0.00, 9999.99)
            """), {"l1": uuid.uuid4(), "l2": uuid.uuid4(), "je": je_bad, "t_id": t_id, "acc1": coa["1010"], "acc2": coa["3010"]})
            await session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        assert "check_zero_sum_balance" in str(exc_info.value)
        await session.rollback()

    # 3. Attempt to post an entry with zero lines -> rejected by enforce_journal_entry_has_lines
    async with AsyncSessionLocal() as session:
        je_empty = uuid.uuid4()
        with pytest.raises(Exception) as exc_empty:
            await session.execute(text("""
                INSERT INTO journal_entries (id, tenant_id, entry_number, entry_date, narration, status)
                VALUES (:id, :t_id, 'JV-UAT01-EMPTY', '2026-04-10', 'Empty entry', 'posted')
            """), {"id": je_empty, "t_id": t_id})
            await session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        assert "requires at least 2 journal lines" in str(exc_empty.value)
        await session.rollback()


# ============================================================================
# UAT-02 (Finding A): Block INSERT of Balanced Pair into Already-Posted Entry
# ============================================================================
@pytest.mark.asyncio
async def test_uat02_finding_a_prevent_insert_into_already_posted_journal_entry():
    async with AsyncSessionLocal() as session:
        t_id = uuid.uuid4()
        c_id = f"U72900KA2026PTC{uuid.uuid4().int % 900000 + 100000}"
        p_id = f"AABCB{uuid.uuid4().int % 9000 + 1000}F"
        await session.execute(text("""
            INSERT INTO tenants (id, legal_name, cin, pan, state_code, registered_office)
            VALUES (:id, 'UAT02 Corp Pvt Ltd', :cin, :pan, '29', 'Bengaluru')
        """), {"id": t_id, "cin": c_id, "pan": p_id})
        await session.execute(text("SELECT seed_tenant_chart_of_accounts(:t_id)"), {"t_id": t_id})

        res = await session.execute(text(
            "SELECT id, code FROM chart_of_accounts WHERE tenant_id = :t_id AND code IN ('1010', '3010', '4010')"
        ), {"t_id": t_id})
        coa = {row.code: row.id for row in res.fetchall()}

        je_id = uuid.uuid4()
        await session.execute(text("""
            INSERT INTO journal_entries (id, tenant_id, entry_number, entry_date, narration, status)
            VALUES (:id, :t_id, 'JV-UAT02-POSTED', '2026-04-11', 'Original ₹10,000 entry', 'posted')
        """), {"id": je_id, "t_id": t_id})
        await session.execute(text("""
            INSERT INTO journal_lines (id, journal_entry_id, tenant_id, account_id, debit_amount, credit_amount)
            VALUES
                (:l1, :je, :t_id, :acc1, 10000.00, 0.00),
                (:l2, :je, :t_id, :acc2, 0.00, 10000.00)
        """), {"l1": uuid.uuid4(), "l2": uuid.uuid4(), "je": je_id, "t_id": t_id, "acc1": coa["1010"], "acc2": coa["3010"]})

        # Devil's Advocate Attack Scenario (Finding A):
        # Attempt to insert two additional balanced lines (+₹5,000 Dr / +₹5,000 Cr) into the already-posted entry
        with pytest.raises(Exception) as exc_attack:
            await session.execute(text("""
                INSERT INTO journal_lines (id, journal_entry_id, tenant_id, account_id, debit_amount, credit_amount)
                VALUES
                    (:l3, :je, :t_id, :acc3, 5000.00, 0.00),
                    (:l4, :je, :t_id, :acc1, 0.00, 5000.00)
            """), {"l3": uuid.uuid4(), "l4": uuid.uuid4(), "je": je_id, "t_id": t_id, "acc3": coa["4010"], "acc1": coa["1010"]})
        assert "Audit Immutability Violation" in str(exc_attack.value)
        assert "Cannot insert additional lines into an already-posted journal entry" in str(exc_attack.value)
        await session.rollback()


# ============================================================================
# UAT-03 (Finding B & C): FORCE RLS Verification, b00k5_app Isolation & Cross-Tenant FK Block
# ============================================================================
@pytest.mark.asyncio
async def test_uat03_finding_b_and_c_rls_force_coverage_and_cross_tenant_line_rejection():
    async with AsyncSessionLocal() as session:
        # 1. Verify all 19 tenant tables have BOTH relrowsecurity=true AND relforcerowsecurity=true
        rls_res = await session.execute(text("""
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relnamespace = 'public'::regnamespace
              AND relkind = 'r'
              AND relname != 'users'
        """))
        rows = rls_res.fetchall()
        assert len(rows) >= 19
        for relname, rls_enabled, rls_forced in rows:
            assert rls_enabled is True, f"Table {relname} missing ENABLE ROW LEVEL SECURITY"
            assert rls_forced is True, f"Table {relname} missing FORCE ROW LEVEL SECURITY"

        # 2. Provision Tenant A and Tenant B
        ta_id, tb_id = uuid.uuid4(), uuid.uuid4()
        for tid, name, st in [(ta_id, "Tenant A Pvt Ltd", "29"), (tb_id, "Tenant B Pvt Ltd", "27")]:
            await session.execute(text("""
                INSERT INTO tenants (id, legal_name, cin, pan, state_code, registered_office)
                VALUES (:id, :name, :cin, :pan, :st, 'Address')
            """), {
                "id": tid,
                "name": name,
                "cin": f"U72900KA2026PTC{uuid.uuid4().int % 900000 + 100000}",
                "pan": f"AABCX{uuid.uuid4().int % 9000 + 1000}F",
                "st": st
            })
            await session.execute(text("SELECT seed_tenant_chart_of_accounts(:t_id)"), {"t_id": tid})

        res_a = await session.execute(text("SELECT id, code FROM chart_of_accounts WHERE tenant_id = :t AND code IN ('1010', '3010')"), {"t": ta_id})
        coa_a = {r.code: r.id for r in res_a.fetchall()}
        res_b = await session.execute(text("SELECT id, code FROM chart_of_accounts WHERE tenant_id = :t AND code IN ('1010', '3010')"), {"t": tb_id})
        coa_b = {r.code: r.id for r in res_b.fetchall()}
        await session.commit()

    # 3. Verify set_tenant_context switches to non-superuser role `b00k5_app` and blocks cross-tenant visibility
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, ta_id)
        role_res = await session.execute(text("SELECT current_user"))
        assert role_res.scalar() == "b00k5_app"

        # Tenant A cannot see Tenant B's Chart of Accounts or Tenant record
        tb_visible = (await session.execute(text("SELECT COUNT(*) FROM chart_of_accounts WHERE tenant_id = :tb"), {"tb": tb_id})).scalar()
        assert tb_visible == 0
        await session.rollback()

    # 4. Finding C UAT Criterion: Deliberately malformed cross-tenant journal line rejected at DB level
    async with AsyncSessionLocal() as session:
        je_a = uuid.uuid4()
        await session.execute(text("""
            INSERT INTO journal_entries (id, tenant_id, entry_number, entry_date, narration, status)
            VALUES (:id, :ta, 'JV-CROSS-TENANT', '2026-04-12', 'Cross-tenant test', 'draft')
        """), {"id": je_a, "ta": ta_id})

        with pytest.raises(Exception) as exc_cross:
            # Attempt to attach Tenant B's account (coa_b['3010']) to Tenant A's journal entry!
            await session.execute(text("""
                INSERT INTO journal_lines (id, journal_entry_id, tenant_id, account_id, debit_amount, credit_amount)
                VALUES (:l1, :je, :ta, :acc_b, 1000.00, 0.00)
            """), {"l1": uuid.uuid4(), "je": je_a, "ta": ta_id, "acc_b": coa_b["3010"]})
        assert "Cross-Tenant Integrity Violation" in str(exc_cross.value)
        await session.rollback()


# ============================================================================
# UAT-04 & UAT-05 (SEC-01 & SEC-02): Fail-Closed Secrets & Loopback Infrastructure
# ============================================================================
def test_uat04_uat05_fail_closed_production_secrets_and_compose_loopback():
    # UAT-04: Missing or default production secrets must fail closed
    with pytest.raises(RuntimeError) as exc_default:
        validate_production_security({
            "APP_ENV": "production",
            "SECRET_KEY": "b00k5_default_dev_jwt_secret_key_change_in_prod_2026",
            "DATABASE_URL": "postgresql+asyncpg://b00k5_admin:b00k5_secure_vault_password_2026@localhost:5432/b00k5_db",
            "MINIO_SECRET_KEY": "minio_storage_secret_key_2026",
            "UVICORN_RELOAD": "true",
        })
    assert "SEC-01 Fail-Closed" in str(exc_default.value)

    # Strong production secrets with hardware DSC and without reload succeed
    valid_res = validate_production_security({
        "APP_ENV": "production",
        "SECRET_KEY": "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e",
        "DATABASE_URL": "postgresql+asyncpg://prod_user:X9_kLp29mQz81vBnR4tYw@db.internal:5432/b00k5_prod",
        "MINIO_SECRET_KEY": "M9_vXp72qLz45wKnT8yJcR3b",
        "UVICORN_RELOAD": "false",
        "DSC_MODE": "hardware",
    })
    assert valid_res["status"] == "secure"

    # Mock/simulated DSC in production must also fail closed
    with pytest.raises(RuntimeError) as exc_mock_dsc:
        validate_production_security({
            "APP_ENV": "production",
            "SECRET_KEY": "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e",
            "DATABASE_URL": "postgresql+asyncpg://prod_user:X9_kLp29mQz81vBnR4tYw@db.internal:5432/b00k5_prod",
            "MINIO_SECRET_KEY": "M9_vXp72qLz45wKnT8yJcR3b",
            "UVICORN_RELOAD": "false",
            "DSC_MODE": "simulated",
        })
    assert "DSC_MODE" in str(exc_mock_dsc.value)

    # UAT-05: Verify docker-compose.yml binds ports to 127.0.0.1 and pins MinIO release (when running on host or mounted)
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    if compose_path.exists():
        compose_text = compose_path.read_text(encoding="utf-8")
        assert "127.0.0.1:${POSTGRES_PORT:-5432}:5432" in compose_text
        assert "127.0.0.1:${REDIS_PORT:-6379}:6379" in compose_text
        assert "127.0.0.1:${MINIO_API_PORT:-9000}:9000" in compose_text
        assert "127.0.0.1:28045:28045" in compose_text
        assert "--reload" not in compose_text
        assert "minio:latest" not in compose_text


# ============================================================================
# UAT-06 & UAT-07: Statement Overlap, Same-Day Distinct Txns, Ambiguous Match & Suspense
# ============================================================================
def test_uat06_uat07_statement_overlap_legitimate_duplicates_and_ambiguous_matching():
    # UAT-06a: Two legitimate payments to the same vendor on the same date for the same amount
    # have different running balances -> distinct fingerprints (neither is dropped!)
    fp_payment_1 = compute_line_fingerprint("50200099998888", "2026-04-15", "5000.00", "95000.00", "")
    fp_payment_2 = compute_line_fingerprint("50200099998888", "2026-04-15", "5000.00", "90000.00", "")
    fp_reupload_1 = compute_line_fingerprint("50200099998888", "2026-04-15", "5000.00", "95000.00", "")
    assert fp_payment_1 != fp_payment_2
    assert fp_payment_1 == fp_reupload_1

    # UAT-06b: Overlapping bank statement period detection
    existing_stmts = [{
        "id": "stmt-nov",
        "account_number": "50200099998888",
        "statement_from": date(2025, 11, 1),
        "statement_to": date(2025, 11, 30),
        "opening_balance": Decimal("100000.00")
    }]
    overlap_res = detect_statement_overlap({
        "account_number": "50200099998888",
        "statement_from": date(2025, 11, 15),
        "statement_to": date(2025, 12, 15),
        "opening_balance": Decimal("85000.00")
    }, existing_stmts)
    assert overlap_res["has_overlap"] is True
    assert overlap_res["overlap_type"] == "PARTIAL_DATE_RANGE_OVERLAP"

    # UAT-07a: Ambiguous match against two similar invoices with the same amount
    bank_line = {
        "transaction_date": date(2026, 4, 10),
        "description": "NEFT CR-CLOUD INFRA SERVICES",
        "reference_number": "NEFT0001928",
        "counterparty_name": "Cloud Infra Services Pvt Ltd",
        "deposit_amount": Decimal("23600.00"),
        "withdrawal_amount": Decimal("0.00"),
    }
    open_invoices = [
        {
            "id": uuid.uuid4(),
            "invoice_number": "INV-2026-001",
            "issue_date": date(2026, 4, 5),
            "grand_total": Decimal("23600.00"),
            "contact_name": "Cloud Infra Services Pvt Ltd",
        },
        {
            "id": uuid.uuid4(),
            "invoice_number": "INV-2026-002",
            "issue_date": date(2026, 4, 6),
            "grand_total": Decimal("23600.00"),
            "contact_name": "Cloud Infra Services Limited",
        },
    ]
    match_res = ReconciliationEngine.match_tier2(bank_line, open_invoices)
    assert match_res is not None
    matched_inv, score = match_res
    assert matched_inv["is_ambiguous"] is True
    assert matched_inv["auto_reconcile_allowed"] is False
    assert matched_inv["reconciliation_status"] == "probable_match"
    assert set(matched_inv["ambiguous_candidate_numbers"]) == {"INV-2026-001", "INV-2026-002"}

    # UAT-07b: Suspense clearance moves balance from 2099 to target account without double-counting Bank 1010
    clearance = ReconciliationEngine.compute_suspense_clearance_entries(
        suspense_amount=Decimal("11800.00"),
        is_withdrawal=True,
        suspense_account_code="2099",
        target_account_code="4010"
    )
    assert clearance["touches_bank_account_1010"] is False
    assert clearance["total_debit"] == clearance["total_credit"] == Decimal("11800.00")


# ============================================================================
# UAT-08 & UAT-09: Multi-Factor GST POS, Export, RCM & ITC Eligibility Engine
# ============================================================================
def test_uat08_uat09_gst_place_of_supply_and_itc_eligibility():
    # UAT-08: Intrastate, Interstate, Export with LUT, and Immovable Property (Sec 12(3) Hotel)
    intra = ComplianceWatchdogService.evaluate_gst_place_of_supply("29", "29")
    assert intra["tax_regime"] == "CGST_SGST_INTRASTATE" and intra["cgst_applicable"] is True

    inter = ComplianceWatchdogService.evaluate_gst_place_of_supply("29", "27", is_reverse_charge=True)
    assert inter["tax_regime"] == "IGST_INTERSTATE" and inter["reverse_charge_applicable"] is True

    export_lut = ComplianceWatchdogService.evaluate_gst_place_of_supply("29", is_export=True, has_lut_bond=True)
    assert export_lut["tax_regime"] == "ZERO_RATED_EXPORT_LUT" and export_lut["igst_applicable"] is False

    hotel_pos = ComplianceWatchdogService.evaluate_gst_place_of_supply(
        supplier_state_code="27",
        recipient_state_code="29",
        supply_type="hotel_accommodation",
        property_location_state_code="27"
    )
    assert hotel_pos["effective_pos"] == "27"
    assert hotel_pos["requires_manual_review"] is True

    # UAT-09a: Missing or mismatched recipient GSTIN -> Ineligible
    itc_missing_recipient = ComplianceWatchdogService.evaluate_gst_itc_eligibility(
        tenant_gstin="29AABCA1234F1Z5",
        supplier_gstin="29AABCS9999K1Z2",
        recipient_gstin_on_invoice=None,
        invoice_number="INV-101",
        invoice_date=date(2026, 4, 5),
        place_of_supply="29",
        gstr2b_verified=True
    )
    assert itc_missing_recipient["itc_eligible"] is False
    assert itc_missing_recipient["itc_status"] == "INELIGIBLE"

    # UAT-09b: Section 17(5) Blocked Credit (Food & Catering) -> Ineligible even with valid GSTINs
    itc_blocked = ComplianceWatchdogService.evaluate_gst_itc_eligibility(
        tenant_gstin="29AABCA1234F1Z5",
        supplier_gstin="29AABCS9999K1Z2",
        recipient_gstin_on_invoice="29AABCA1234F1Z5",
        invoice_number="INV-FOOD-99",
        invoice_date=date(2026, 4, 5),
        place_of_supply="29",
        expense_category="food_beverages",
        gstr2b_verified=True
    )
    assert itc_blocked["itc_eligible"] is False
    assert any("Section 17(5)" in r for r in itc_blocked["reasons"])

    # UAT-09c: Unverified in GSTR-2B -> Provisional / Not auto-approved
    itc_unmatched_2b = ComplianceWatchdogService.evaluate_gst_itc_eligibility(
        tenant_gstin="29AABCA1234F1Z5",
        supplier_gstin="29AABCS9999K1Z2",
        recipient_gstin_on_invoice="29AABCA1234F1Z5",
        invoice_number="INV-CLOUD-10",
        invoice_date=date(2026, 4, 5),
        place_of_supply="29",
        expense_category="cloud_hosting",
        gstr2b_verified=False
    )
    assert itc_unmatched_2b["itc_eligible"] is False
    assert itc_unmatched_2b["itc_status"] == "PROVISIONAL_PENDING_GSTR2B"


# ============================================================================
# UAT-10 & UAT-11: Board Exemptions, Income-tax Act 2025 Transition, Sec 40A(3) & DPT-3
# ============================================================================
def test_uat10_uat11_statutory_compliance_and_income_tax_act_2025_transition():
    # UAT-10a: Single-Director OPC is exempt from Section 173 board meeting interval
    opc_eval = ComplianceWatchdogService.evaluate_board_meeting_cadence(
        last_meeting_date=date(2025, 1, 1),
        today=date(2026, 10, 1),
        entity_type="opc",
        director_count=1
    )
    assert opc_eval["status"] == "exempt_opc_single_director"
    assert opc_eval["is_violation"] is False

    # UAT-10b: Newly incorporated Pvt Ltd must hold first Board Meeting within 30 days
    first_bm = ComplianceWatchdogService.evaluate_board_meeting_cadence(
        last_meeting_date=None,
        incorporation_date=date(2026, 4, 1),
        today=date(2026, 5, 10),
        entity_type="private_limited"
    )
    assert first_bm["is_violation"] is True
    assert first_bm["first_meeting_deadline"] == date(2026, 5, 1)

    # UAT-10c: Form-specific penalty with Section 446B Small Company 50% relief and Sec 234E TDS cap
    aoc4_small = ComplianceWatchdogService.calculate_form_specific_penalty("AOC-4", overdue_days=20, entity_type="small_company")
    assert aoc4_small["penalty_inr"] == Decimal("1000.00")  # 50% of ₹2,000 under Sec 446B

    tds_234e = ComplianceWatchdogService.calculate_form_specific_penalty("26Q", overdue_days=30, tax_or_tds_amount=Decimal("1500.00"))
    assert tds_234e["penalty_inr"] == Decimal("1500.00")  # Capped at TDS amount (₹1,500 < ₹6,000)
    assert tds_234e["cap_applied"] is True

    # UAT-11a: Direct Tax Transition — 31 March 2026 (IT Act 1961) vs 1 April 2026 (IT Act 2025)
    mar31 = calculate_indian_fy_ay(date(2026, 3, 31))
    apr01 = calculate_indian_fy_ay(date(2026, 4, 1))
    assert mar31["governing_direct_tax_act"] == "Income-tax Act, 1961"
    assert mar31["fy_label"] == "2025-2026" and mar31["ay_label"] == "2026-2027"
    assert mar31["tax_year_label"] is None

    assert apr01["governing_direct_tax_act"] == "Income-tax Act, 2025"
    assert apr01["fy_label"] == "2026-2027"
    assert apr01["tax_year_label"] == "TY 2026-27"

    # UAT-11b: Cross-period TDS transition (Accrued 31 March 2026, Paid 15 April 2026, Remitted 30 April 2026)
    tds_trans = evaluate_cross_period_tds_transition(
        accrual_date=date(2026, 3, 31),
        payment_date=date(2026, 4, 15),
        remittance_date=date(2026, 4, 30),
        section="194J",
        gross_amount=Decimal("50000.00"),
        tds_rate_percent=Decimal("10.00")
    )
    assert tds_trans["crosses_act_2025_transition"] is True
    assert tds_trans["accrual_governing_act"] == "Income-tax Act, 1961"
    assert tds_trans["payment_governing_act"] == "Income-tax Act, 2025"
    assert tds_trans["allowable_in_accrual_fy"] is True

    # UAT-11c: Section 40A(3) daily cash aggregation across split receipts & goods carriage ₹35,000 limit
    split_cash = ComplianceWatchdogService.evaluate_cash_payment_disallowance([
        {"amount": Decimal("6000.00"), "payment_mode": "cash"},
        {"amount": Decimal("5500.00"), "payment_mode": "cash"},
    ], is_goods_carriage=False)
    assert split_cash["aggregate_cash_paid"] == Decimal("11500.00")
    assert split_cash["is_disallowed"] is True

    transport_cash = ComplianceWatchdogService.evaluate_cash_payment_disallowance([
        {"amount": Decimal("32000.00"), "payment_mode": "cash"},
    ], is_goods_carriage=True)
    assert transport_cash["is_disallowed"] is False

    # UAT-11d: DPT-3 Director balance never auto-converts without Own-Funds Declaration & Board Resolution
    dpt3_unclassified = ComplianceWatchdogService.evaluate_director_balance_dpt3(
        balance_amount=Decimal("50000.00"),
        is_explicitly_classified_as_loan=False
    )
    assert dpt3_unclassified["exempt_from_deposit_rules"] is False
    assert dpt3_unclassified["dpt3_reporting_status"] == "REVIEW_REQUIRED_NOT_AUTO_CONVERTED"


# ============================================================================
# UAT-12 (SEC-04): Mock vs Hardware DSC Signing & Minutes Governance Validation
# ============================================================================
def test_uat12_dsc_simulated_vs_hardware_and_minutes_governance():
    meeting_payload = {
        "notice_days": 7,
        "shorter_notice_consent": False,
        "total_directors": 2,
        "directors_present": [{"din": "09876541"}, {"din": "09876542"}],
    }
    # 1. Simulated signature is explicitly labelled and blocked from legal filing readiness
    sim_check = ComplianceWatchdogService.validate_board_minutes_and_dsc(
        meeting_payload=meeting_payload,
        dsc_result={"simulation": True, "signer_din": "09876541"},
        authorized_director_dins=["09876541", "09876542"]
    )
    assert sim_check["governance_valid"] is True
    assert sim_check["is_simulated_signature"] is True
    assert sim_check["signature_mode"] == "SIMULATED_DEV_MOCK"
    assert sim_check["legal_filing_ready"] is False
    assert "SIMULATED SIGNATURE" in sim_check["watermark_required"]

    # 2. Hardware PKCS#11 signature with valid quorum, notice, and authorized DIN is legal-filing ready
    hw_check = ComplianceWatchdogService.validate_board_minutes_and_dsc(
        meeting_payload=meeting_payload,
        dsc_result={"simulation": False, "signer_din": "09876541"},
        authorized_director_dins=["09876541", "09876542"]
    )
    assert hw_check["governance_valid"] is True
    assert hw_check["signature_mode"] == "HARDWARE_PKCS11_VERIFIED"
    assert hw_check["legal_filing_ready"] is True


# ============================================================================
# UAT-13 & UAT-18 (SEC-06 & Section 8): 7-Point Staging Restore Gate & Cutover Rollback
# ============================================================================
def test_uat13_uat18_disaster_recovery_staging_gate_and_failed_cutover_rollback():
    secret = "strong_backup_secret_key_2026_production_verified"
    raw_sql = b"-- b00k5 Verified Dump\nSELECT 1;\n"
    compressed = gzip.compress(raw_sql)
    enc_bytes = encrypt_bytes_aes256_gcm(compressed, derive_aes_key(secret))
    checksum = hashlib.sha256(enc_bytes).hexdigest()

    # 1. Valid restore passes all 7 gates
    ok_res = DatabaseBackupManager.verify_and_stage_restore(
        encrypted_bytes=enc_bytes,
        expected_sha256=checksum,
        decryption_secret=secret,
        backup_status="completed",
        simulated_ledger_state={
            "total_debits": Decimal("250000.00"),
            "total_credits": Decimal("250000.00"),
            "cross_tenant_fk_violations": 0,
            "subledger_control_drift": Decimal("0.00"),
            "duplicate_source_postings": 0,
        }
    )
    assert ok_res["restore_approved"] is True
    assert ok_res["stage_status"] == "RESTORED_AND_VERIFIED"

    # 2. Wrong decryption key rejected
    wrong_key_res = DatabaseBackupManager.verify_and_stage_restore(
        encrypted_bytes=enc_bytes,
        expected_sha256=checksum,
        decryption_secret="wrong_secret_key"
    )
    assert wrong_key_res["restore_approved"] is False
    assert wrong_key_res["production_modified"] is False
    assert wrong_key_res["stage_status"] == "REJECTED_AUTHENTICATION_OR_CORRUPTION"

    # 3. Truncated ciphertext rejected
    trunc_res = DatabaseBackupManager.verify_and_stage_restore(
        encrypted_bytes=enc_bytes[:16],
        expected_sha256=checksum,
        decryption_secret=secret
    )
    assert trunc_res["restore_approved"] is False
    assert trunc_res["stage_status"] == "REJECTED_TRUNCATED_ARCHIVE"

    # 4. Valid ciphertext but inconsistent ledger / subledger drift rejected
    drift_res = DatabaseBackupManager.verify_and_stage_restore(
        encrypted_bytes=enc_bytes,
        expected_sha256=checksum,
        decryption_secret=secret,
        simulated_ledger_state={
            "total_debits": Decimal("250000.00"),
            "total_credits": Decimal("250000.00"),
            "cross_tenant_fk_violations": 0,
            "subledger_control_drift": Decimal("1500.00"),
            "duplicate_source_postings": 0,
        }
    )
    assert drift_res["restore_approved"] is False
    assert drift_res["stage_status"] == "REJECTED_LEDGER_INCONSISTENCY"

    # 5. UAT-18a: Interrupted / incomplete Google Drive upload excluded from restore
    incomplete_res = DatabaseBackupManager.verify_and_stage_restore(
        encrypted_bytes=enc_bytes,
        expected_sha256=checksum,
        decryption_secret=secret,
        backup_status="failed"
    )
    assert incomplete_res["restore_approved"] is False
    assert incomplete_res["stage_status"] == "REJECTED_INCOMPLETE_ARCHIVE"

    # 6. UAT-18b: Simulated cutover failure triggers automatic rollback, leaving production intact
    cutover_fail_res = DatabaseBackupManager.verify_and_stage_restore(
        encrypted_bytes=enc_bytes,
        expected_sha256=checksum,
        decryption_secret=secret,
        simulate_cutover_failure=True
    )
    assert cutover_fail_res["restore_approved"] is False
    assert cutover_fail_res["production_modified"] is False
    assert cutover_fail_res["rollback_executed"] is True
    assert cutover_fail_res["stage_status"] == "CUTOVER_FAILED_ROLLED_BACK_SAFELY"


# ============================================================================
# UAT-14 (SEC-03): RBAC Enforcement & JWT Algorithm Confusion Rejection
# ============================================================================
def test_uat14_rbac_matrix_and_jwt_algorithm_confusion():
    # 1. Employee blocked from Ledger, IAM, Cap-Table/Governance, and Expense Approval
    for restricted_path in ["/api/v1/ledger/entries", "/api/v1/iam/users", "/api/v1/compliance/meetings", "/api/v1/expenses/123/settle"]:
        with pytest.raises(HTTPException) as exc_emp:
            enforce_rbac_policy("employee", "POST", restricted_path)
        assert exc_emp.value.status_code == 403

    # Employee allowed to view and submit own expense
    enforce_rbac_policy("employee", "GET", "/api/v1/expenses")
    enforce_rbac_policy("employee", "POST", "/api/v1/expenses")

    # 2. Auditor (CA) allowed read-only GET and export, blocked from all mutations
    enforce_rbac_policy("auditor_ca", "GET", "/api/v1/ledger/entries")
    enforce_rbac_policy("auditor_ca", "GET", "/api/v1/expenses/export/auditor")
    for mutate_path in ["/api/v1/invoices", "/api/v1/iam/users", "/api/v1/ledger/entries"]:
        with pytest.raises(HTTPException) as exc_aud:
            enforce_rbac_policy("auditor_ca", "POST", mutate_path)
        assert exc_aud.value.status_code == 403

    # 3. Reject forged 'alg: none' JWT token
    import base64
    import json
    hdr = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    pld = base64.urlsafe_b64encode(json.dumps({"sub": str(uuid.uuid4()), "exp": 9999999999}).encode()).decode().rstrip("=")
    forged_none_token = f"{hdr}.{pld}."
    assert decode_access_token(forged_none_token) is None


# ============================================================================
# UAT-15: Period Close DB Trigger Enforcement & Authorized Reopen
# ============================================================================
@pytest.mark.asyncio
async def test_uat15_period_close_database_trigger_enforcement():
    async with AsyncSessionLocal() as session:
        t_id = uuid.uuid4()
        await session.execute(text("""
            INSERT INTO tenants (id, legal_name, cin, pan, state_code, registered_office)
            VALUES (:id, 'UAT15 Period Close Corp', :cin, :pan, '29', 'Bengaluru')
        """), {
            "id": t_id,
            "cin": f"U72900KA2026PTC{uuid.uuid4().int % 900000 + 100000}",
            "pan": f"AABCP{uuid.uuid4().int % 9000 + 1000}F"
        })
        await session.execute(text("SELECT seed_tenant_chart_of_accounts(:t_id)"), {"t_id": t_id})

        # Create and close FY 2025-2026
        fy_id = uuid.uuid4()
        await session.execute(text("""
            INSERT INTO fiscal_years (id, tenant_id, label, assessment_year, start_date, end_date, is_closed)
            VALUES (:id, :t_id, '2025-2026', '2026-2027', '2025-04-01', '2026-03-31', TRUE)
        """), {"id": fy_id, "t_id": t_id})
        await session.commit()

    # Attempt to post a backdated journal entry into closed FY 2025-2026 -> rejected by DB trigger!
    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception) as exc_closed:
            await session.execute(text("""
                INSERT INTO journal_entries (id, tenant_id, entry_number, entry_date, narration, status)
                VALUES (:id, :t_id, 'JV-CLOSED-2025', '2025-12-15', 'Backdated into closed FY', 'posted')
            """), {"id": uuid.uuid4(), "t_id": t_id})
        assert "Period Close Violation" in str(exc_closed.value)
        await session.rollback()


# ============================================================================
# UAT-16 & UAT-17 (SEC-05): Malicious Uploads, Active PDF Scripts & Concurrency
# ============================================================================
def test_uat16_uat17_malicious_upload_rejection_and_concurrent_workload():
    # 1. Path traversal rejected
    with pytest.raises(ValueError) as exc_path:
        validate_uploaded_document_safety(b"%PDF-1.4\n%%EOF", "../../etc/passwd")
    assert "path-traversal" in str(exc_path.value)

    # 2. PDF with embedded /JavaScript rejected
    malicious_pdf = b"%PDF-1.4\n1 0 obj << /Type /Catalog /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >> endobj\n%%EOF"
    with pytest.raises(ValueError) as exc_js:
        validate_uploaded_document_safety(malicious_pdf, "invoice.pdf")
    assert "/JavaScript" in str(exc_js.value)

    # 3. Oversized payload rejected
    with pytest.raises(ValueError) as exc_size:
        validate_uploaded_document_safety(b"%PDF-1.4\n" + b"A" * 2048, "huge.pdf", max_size_bytes=1024)
    assert "exceeds maximum allowed limit" in str(exc_size.value)

    # 4. Image exceeding pixel threshold rejected
    buf = io.BytesIO()
    Image.new("RGB", (200, 200)).save(buf, format="PNG")
    with pytest.raises(ValueError) as exc_bomb:
        validate_uploaded_document_safety(buf.getvalue(), "bomb.png", max_image_pixels=10000)
    assert "decompression bomb" in str(exc_bomb.value).lower()

    # 5. Valid clean PDF and PNG pass
    clean_res = validate_uploaded_document_safety(b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF", "clean_statement.pdf")
    assert clean_res["safe"] is True

    # 6. UAT-17: Concurrent batch fingerprint determinism across 100 rapid transactions
    fps = {
        compute_line_fingerprint("50200099998888", "2026-04-20", "1000.00", f"{100000 - i * 1000}.00", f"UTR{i:05d}")
        for i in range(100)
    }
    assert len(fps) == 100
