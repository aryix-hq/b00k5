#!/usr/bin/env bash
""":"
python3 "$0" "$@"
exit $?
"""
import os
import sys
import uuid
import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("b00k5_seeder")

TENANT_1_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_2_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

USER_1_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_2_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
USER_3_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")

# Test CIN and GSTIN
CIN_TENANT_1 = "U72900KA2026PTC123456"
GSTIN_TENANT_1 = "29AABCA1234F1Z5" # Karnataka (State Code 29)
PAN_TENANT_1 = "AABCA1234F"

CIN_TENANT_2 = "U72900DL2024PTC199888"
GSTIN_TENANT_2 = "07AABCS9999K1ZE" # Delhi (State Code 07, Mod-36 check char E)
PAN_TENANT_2 = "AABCS9999K"

SCHEDULE_III_COA = [
    # 1000-1999: Assets
    ('1010', 'Bank Current Account (HDFC Bank)', 'asset', 'bank', 'debit', 'Primary business checking account'),
    ('1020', 'Trade Receivables (Debtors)', 'asset', 'current_asset', 'debit', 'Outstanding customer billings'),
    ('1030', 'Input CGST', 'asset', 'tax_asset', 'debit', 'Input Central GST Credit on purchases'),
    ('1031', 'Input SGST', 'asset', 'tax_asset', 'debit', 'Input State GST Credit on purchases'),
    ('1032', 'Input IGST', 'asset', 'tax_asset', 'debit', 'Input Integrated GST Credit on inter-state purchases'),
    ('1050', 'Computer & IT Hardware', 'asset', 'fixed_asset', 'debit', 'Laptops, workstations, and office equipment'),

    # 2000-2999: Equity & Liabilities
    ('2010', 'Paid-up Equity Share Capital', 'equity', 'share_capital', 'credit', 'Nominal value of equity shares issued'),
    ('2020', 'Reserves & Surplus / Retained Earnings', 'equity', 'retained_earnings', 'credit', 'Accumulated profits or losses'),
    ('2030', 'Director Unsecured Borrowings', 'liability', 'director_loan', 'credit', 'Loans from promoters'),
    ('2040', 'Trade Payables (Creditors)', 'liability', 'current_liability', 'credit', 'Unpaid vendor invoices'),
    ('2050', 'Output CGST', 'liability', 'tax_liability', 'credit', 'Central GST collected on intra-state sales'),
    ('2051', 'Output SGST', 'liability', 'tax_liability', 'credit', 'State GST collected on intra-state sales'),
    ('2052', 'Output IGST', 'liability', 'tax_liability', 'credit', 'Integrated GST collected on inter-state sales'),
    ('2060', 'TDS Payable u/s 194J (Professional)', 'liability', 'tax_liability', 'credit', 'TDS on professional fees'),
    ('2099', 'Suspense Account (Bank Reconciliation)', 'liability', 'suspense', 'credit', 'Unmatched bank lines pending allocation'),

    # 3000-3999: Revenue
    ('3010', 'Revenue from Software Subscriptions (SaaS)', 'revenue', 'operating_revenue', 'credit', 'Core platform subscription revenue'),
    ('3020', 'Professional & Implementation Services', 'revenue', 'operating_revenue', 'credit', 'Consulting & onboarding revenue'),
    ('3030', 'Interest Income on Fixed Deposits', 'revenue', 'other_income', 'credit', 'Bank interest earned'),

    # 4000-4999: Expenses
    ('4010', 'Cloud Infrastructure & Hosting (AWS/GCP)', 'expense', 'direct_expense', 'debit', 'Cloud compute, DBs, and S3 storage'),
    ('4020', 'Employee Benefit Expenses / Payroll', 'expense', 'payroll', 'debit', 'Salaries, stipends, and payroll taxes'),
    ('4030', 'Payment Gateway & Bank Wire Charges', 'expense', 'financial_expense', 'debit', 'Razorpay & HDFC wire charges'),
    ('4040', 'Legal & Professional Retainer (CA/CS)', 'expense', 'professional_fees', 'debit', 'Corporate filings and audit fees')
]

def generate_sql_seed_script() -> str:
    """
    Generates a deterministic SQL seed script compatible with PostgreSQL 16.
    """
    sql = []
    sql.append("-- ============================================================================")
    sql.append("-- b00k5 DETERMINISTIC SEED DATA FOR TESTING & MULTI-TENANCY")
    sql.append("-- ============================================================================")
    sql.append("BEGIN;")

    # 1. Tenants (Acme Labs Pvt Ltd & Zenith Commerce LLP)
    sql.append(f"""
    INSERT INTO tenants (id, legal_name, trade_name, cin, gstin, pan, state_code, registered_office)
    VALUES 
    ('{TENANT_1_ID}', 'Acme Labs Pvt Ltd', 'Acme Cloud', '{CIN_TENANT_1}', '{GSTIN_TENANT_1}', '{PAN_TENANT_1}', '29', 'Indiranagar, 100 Feet Road, Bengaluru, Karnataka 560038'),
    ('{TENANT_2_ID}', 'Zenith Commerce LLP', 'Zenith Commerce', '{CIN_TENANT_2}', '{GSTIN_TENANT_2}', '{PAN_TENANT_2}', '07', 'Barakhamba Road, Connaught Place, New Delhi 110001')
    ON CONFLICT (id) DO UPDATE SET legal_name = EXCLUDED.legal_name, cin = EXCLUDED.cin, gstin = EXCLUDED.gstin, pan = EXCLUDED.pan;
    """)

    # 2. Users (Password: Admin@12345 / password123)
    pwd_hash = "$2b$12$7kPsk2f15KkgFj0tX1X7w.gYc06R7B.U6xR0s8yXvK5u7N21xG9ye"
    sql.append(f"""
    INSERT INTO users (id, email, password_hash, first_name, last_name, phone, is_active)
    VALUES
    ('{USER_1_ID}', 'admin@acme.corp', '{pwd_hash}', 'Vikram', 'Sharma', '+919876543210', true),
    ('{USER_2_ID}', 'auditor@acme.corp', '{pwd_hash}', 'Rohit', 'Verma', '+919876543211', true),
    ('{USER_3_ID}', 'admin@zenith.corp', '{pwd_hash}', 'Siddharth', 'Rao', '+919876543212', true)
    ON CONFLICT (id) DO NOTHING;
    """)

    # 3. Tenant Users
    sql.append(f"""
    INSERT INTO tenant_users (tenant_id, user_id, role, is_primary)
    VALUES
    ('{TENANT_1_ID}', '{USER_1_ID}', 'owner', true),
    ('{TENANT_1_ID}', '{USER_2_ID}', 'auditor_ca', false),
    ('{TENANT_2_ID}', '{USER_3_ID}', 'owner', true)
    ON CONFLICT DO NOTHING;
    """)

    # 4. Schedule III COA for Tenant 1 and Tenant 2
    for tid in [TENANT_1_ID, TENANT_2_ID]:
        for code, name, acc_type, sub_type, bal, desc in SCHEDULE_III_COA:
            sql.append(f"""
            INSERT INTO chart_of_accounts (tenant_id, code, name, type, sub_type, normal_balance, description)
            VALUES ('{tid}', '{code}', '{name}', '{acc_type}', '{sub_type}', '{bal}', '{desc}')
            ON CONFLICT DO NOTHING;
            """)

    # 5. Contacts & Invoices
    contact_1_id = uuid.UUID("c1111111-1111-1111-1111-111111111111")
    sql.append(f"""
    INSERT INTO contacts (id, tenant_id, name, is_customer, is_vendor, gstin, pan, state_code, billing_address)
    VALUES ('{contact_1_id}', '{TENANT_1_ID}', 'Cloud Solutions Pvt Ltd', true, false, '29AABCA1234F1Z5', 'AABCA1234F', '29', 'Embassy Tech Village, Bengaluru, Karnataka')
    ON CONFLICT (id) DO NOTHING;
    """)

    inv_1_id = uuid.UUID("a1111111-1111-1111-1111-111111111111")
    inv_2_id = uuid.UUID("a2222222-2222-2222-2222-222222222222")

    sql.append(f"""
    INSERT INTO invoices (id, tenant_id, contact_id, invoice_number, type, issue_date, due_date, place_of_supply, is_interstate, subtotal, cgst_total, sgst_total, igst_total, grand_total, status)
    VALUES
    ('{inv_1_id}', '{TENANT_1_ID}', '{contact_1_id}', 'INV-2026-001', 'tax_invoice', '2026-01-10', '2026-01-25', '29', false, 20000.00, 1800.00, 1800.00, 0.00, 23600.00, 'sent'),
    ('{inv_2_id}', '{TENANT_1_ID}', '{contact_1_id}', 'BILL-AWS-001', 'tax_invoice', '2026-01-15', '2026-01-30', '29', false, 7161.02, 644.49, 644.49, 0.00, 8450.00, 'sent')
    ON CONFLICT (id) DO NOTHING;
    """)

    # 6. Document Locker entries (MOA, Incorporation, GST)
    vault_1_id = uuid.UUID("d1111111-1111-1111-1111-111111111111")
    vault_2_id = uuid.UUID("d2222222-2222-2222-2222-222222222222")
    vault_3_id = uuid.UUID("d3333333-3333-3333-3333-333333333333")

    sql.append(f"""
    INSERT INTO document_vault (id, tenant_id, category, document_name, document_number, minio_s3_key, file_size_bytes, mime_type, sha256_hash)
    VALUES
    ('{vault_1_id}', '{TENANT_1_ID}', 'corporate_legal', 'Memorandum_of_Association_MOA.pdf', 'MOA-2026', 'vault/MOA.pdf', 104857, 'application/pdf', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    ('{vault_2_id}', '{TENANT_1_ID}', 'corporate_legal', 'Certificate_of_Incorporation_Acme.pdf', '{CIN_TENANT_1}', 'vault/COI.pdf', 52428, 'application/pdf', 'a9f4e27c81d34bc58941038204bb842189ad92c89018442841029cba8371903e'),
    ('{vault_3_id}', '{TENANT_2_ID}', 'corporate_legal', 'Zenith_Partnership_Deed_Confidential.pdf', 'DEED-ZENITH', 'vault/DEED.pdf', 204800, 'application/pdf', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    ON CONFLICT (id) DO NOTHING;
    """)

    sql.append("COMMIT;")
    return "\n".join(sql)

def execute_seed():
    seed_sql = generate_sql_seed_script()
    sql_path = "/tmp/b00k5_seed.sql"
    with open(sql_path, "w") as f:
        f.write(seed_sql)
    logger.info(f"Generated deterministic seed SQL ({len(seed_sql)} bytes) at {sql_path}")

    # If psycopg2 is available and environment specifies DB URL, execute directly
    try:
        import psycopg2
        db_url = os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
        if not db_url:
            pg_user = os.getenv("POSTGRES_USER", "b00k5_admin")
            pg_pass = os.getenv("POSTGRES_PASSWORD", "")
            pg_host = os.getenv("POSTGRES_HOST", "localhost")
            pg_port = os.getenv("POSTGRES_PORT", "5432")
            pg_db = os.getenv("POSTGRES_DB", "b00k5_db")
            db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(seed_sql)
        logger.info("✓ Successfully executed deterministic seed in PostgreSQL!")
    except Exception as e:
        logger.info(f"Notice: Direct psycopg2 connection bypassed ({e}). SQL seed script saved to {sql_path}.")

if __name__ == "__main__":
    execute_seed()
