-- ============================================================================
-- b00k5 - Production Database Schema (PostgreSQL 16+)
-- An Open-Source, Local-First ERP, Compliance Engine, and Document Vault
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Application role with NOLOGIN and NOBYPASSRLS for row-level security enforcement (assumed via SET LOCAL ROLE)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'b00k5_app') THEN
        CREATE ROLE b00k5_app WITH NOLOGIN NOBYPASSRLS;
    ELSE
        ALTER ROLE b00k5_app WITH NOLOGIN PASSWORD NULL NOBYPASSRLS;
    END IF;
END
$$;
GRANT USAGE ON SCHEMA public TO b00k5_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO b00k5_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO b00k5_app;
GRANT b00k5_app TO b00k5_admin;

-- ============================================================================
-- 1. TENANCY & IDENTITY AND ACCESS MANAGEMENT (IAM)
-- ============================================================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    legal_name VARCHAR(255) NOT NULL,
    trade_name VARCHAR(255),
    entity_type VARCHAR(64) DEFAULT 'Private Limited Company',
    cin VARCHAR(21) UNIQUE,               -- 21-digit Corporate Identity Number (e.g. U72900KA2026PTC123456)
    pan VARCHAR(10) UNIQUE NOT NULL,      -- 10-char Permanent Account Number
    gstin VARCHAR(15) UNIQUE,             -- 15-char Goods and Services Tax Identification Number
    state_code VARCHAR(2) NOT NULL,       -- 2-digit Indian State Code (e.g. '29' Karnataka, '27' Maharashtra)
    registered_office TEXT NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    fy_start_month SMALLINT DEFAULT 4,    -- Default Indian Financial Year starts in April (4)
    logo_url TEXT,                        -- Base64 or MinIO object key for company logo
    logo_s3_key VARCHAR(255),
    statutory_profile JSONB DEFAULT '{}'::jsonb, -- Legal extraction matrix (MOA, AOA, ADT-1, etc.)
    is_archived BOOLEAN DEFAULT FALSE,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TYPE user_role_enum AS ENUM ('owner', 'company_owner', 'finance_manager', 'auditor_ca', 'ca_auditor', 'employee');
CREATE TYPE tenant_role_enum AS ENUM ('company_owner', 'ca_auditor', 'finance_manager', 'employee', 'owner', 'auditor_ca');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name VARCHAR(128) NOT NULL,
    last_name VARCHAR(128) NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    is_super_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tenant_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role user_role_enum NOT NULL DEFAULT 'employee',
    din VARCHAR(8),                        -- Director Identification Number if user is an MCA director
    icai_membership_no VARCHAR(16),        -- For CAs / Auditors
    is_primary BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_tenant_user UNIQUE(tenant_id, user_id)
);

CREATE INDEX idx_tenant_users_lookup ON tenant_users(tenant_id, user_id);

CREATE TABLE tenant_invitations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(64) NOT NULL DEFAULT 'employee',
    token VARCHAR(128) UNIQUE NOT NULL,
    invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_accepted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tenant_invitations_token ON tenant_invitations(token);
CREATE INDEX idx_tenant_invitations_tenant ON tenant_invitations(tenant_id);

-- ============================================================================
-- 2. GENERAL LEDGER & CHART OF ACCOUNTS (CORE DOUBLE-ENTRY)
-- ============================================================================

CREATE TYPE account_type_enum AS ENUM ('asset', 'liability', 'equity', 'revenue', 'expense');
CREATE TYPE balance_nature_enum AS ENUM ('debit', 'credit');

CREATE TABLE fiscal_years (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    label VARCHAR(32) NOT NULL,
    assessment_year VARCHAR(32) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_closed BOOLEAN DEFAULT FALSE,
    is_statutory_sealed BOOLEAN DEFAULT FALSE,
    closing_stage VARCHAR(32) DEFAULT 'active' NOT NULL CHECK (closing_stage IN ('active', 'audit_closing_window', 'statutory_sealed')),
    audit_closing_deadline DATE,
    statutory_seal_hash VARCHAR(64),
    sealed_at TIMESTAMPTZ,
    sealed_by_user_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tenant_fy_label UNIQUE (tenant_id, label)
);

CREATE INDEX idx_fiscal_years_tenant ON fiscal_years(tenant_id);

CREATE TABLE chart_of_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(32) NOT NULL,             -- e.g., '1010' for HDFC Current A/C, '2010' for AP
    name VARCHAR(255) NOT NULL,            -- e.g., 'Accounts Receivable', 'Output IGST'
    type account_type_enum NOT NULL,
    sub_type VARCHAR(64),                  -- e.g., 'current_asset', 'operating_revenue', 'statutory_liability'
    normal_balance balance_nature_enum NOT NULL,
    is_reconciliation BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    parent_id UUID REFERENCES chart_of_accounts(id) ON DELETE RESTRICT,
    is_leaf BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_tenant_account_code UNIQUE(tenant_id, code)
);

CREATE INDEX idx_coa_tenant_type ON chart_of_accounts(tenant_id, type);

CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    entry_number VARCHAR(64) NOT NULL,
    entry_date DATE NOT NULL,
    reference_type VARCHAR(64),            -- e.g., 'invoice', 'expense', 'manual_jv', 'bank_reconciliation'
    reference_id UUID,
    narration TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'posted' CHECK (status IN ('draft', 'posted', 'voided')),
    is_posted BOOLEAN DEFAULT TRUE,
    posted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_tenant_journal_number UNIQUE(tenant_id, entry_number)
);

CREATE INDEX idx_journal_tenant_date ON journal_entries(tenant_id, entry_date);

CREATE TABLE journal_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES chart_of_accounts(id) ON DELETE RESTRICT,
    debit_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00 CHECK (debit_amount >= 0),
    credit_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00 CHECK (credit_amount >= 0),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    -- Hard Phase 1 Constraints: Mutually exclusive & strictly non-zero
    CONSTRAINT check_mutually_exclusive_debit_credit CHECK (
        (debit_amount > 0 AND credit_amount = 0) OR
        (credit_amount > 0 AND debit_amount = 0)
    )
);

CREATE INDEX idx_journal_lines_account ON journal_lines(tenant_id, account_id);
CREATE INDEX idx_journal_lines_entry ON journal_lines(journal_entry_id);

-- PostgreSQL Triggers for Audit Immutability: Prevent UPDATE or DELETE on posted records
CREATE OR REPLACE FUNCTION prevent_posted_journal_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'posted' THEN
        RAISE EXCEPTION 'Audit Immutability Violation: Posted journal entries cannot be modified or deleted. Create a reversing entry instead.';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_journal_immutability
BEFORE UPDATE OR DELETE ON journal_entries
FOR EACH ROW EXECUTE FUNCTION prevent_posted_journal_mutation();

-- Prevent posting into a closed fiscal period or statutory sealed period at the database level
CREATE OR REPLACE FUNCTION check_journal_entry_period_open()
RETURNS TRIGGER AS $$
DECLARE
    v_closed BOOLEAN;
    v_sealed BOOLEAN;
    v_stage VARCHAR(32);
BEGIN
    IF NEW.status = 'posted' THEN
        SELECT is_closed, is_statutory_sealed, COALESCE(closing_stage, 'active')
        INTO v_closed, v_sealed, v_stage
        FROM fiscal_years
        WHERE tenant_id = NEW.tenant_id
          AND NEW.entry_date BETWEEN start_date AND end_date
        LIMIT 1;

        -- Hard lock: Statutory Sealed (Stage 3)
        IF v_sealed IS TRUE OR v_stage = 'statutory_sealed' THEN
            RAISE EXCEPTION 'Statutory Breach: Cannot post or modify journal entry (%) dated % in a legally sealed fiscal period anchored to filed MCA Form AOC-4.',
                NEW.entry_number, NEW.entry_date;
        END IF;

        -- If in audit closing window (Stage 2), allow posting adjustments
        IF v_stage = 'audit_closing_window' THEN
            RETURN NEW;
        END IF;

        -- Closed period violation (if manually closed without being in audit window)
        IF v_closed IS TRUE THEN
            RAISE EXCEPTION 'Period Close Violation: Cannot post journal entry (%) dated % into a closed fiscal period.',
                NEW.entry_number, NEW.entry_date;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_journal_period_open ON journal_entries;
CREATE TRIGGER enforce_journal_period_open
BEFORE INSERT OR UPDATE ON journal_entries
FOR EACH ROW EXECUTE FUNCTION check_journal_entry_period_open();

-- Prevent INSERT, UPDATE, or DELETE on lines of an already-posted journal entry, and enforce cross-tenant integrity
CREATE OR REPLACE FUNCTION prevent_posted_journal_line_mutation()
RETURNS TRIGGER AS $$
DECLARE
    v_status VARCHAR(20);
    v_entry_tenant_id UUID;
    v_acc_tenant_id UUID;
    v_entry_xmin xid;
    v_existing_count INT;
    v_existing_debit NUMERIC(15, 2);
    v_existing_credit NUMERIC(15, 2);
BEGIN
    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
        SELECT status INTO v_status FROM journal_entries WHERE id = OLD.journal_entry_id;
        IF v_status = 'posted' THEN
            RAISE EXCEPTION 'Audit Immutability Violation: Lines of a posted journal entry cannot be modified or deleted.';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' THEN
        SELECT status, tenant_id, xmin
        INTO v_status, v_entry_tenant_id, v_entry_xmin
        FROM journal_entries
        WHERE id = NEW.journal_entry_id;

        SELECT tenant_id
        INTO v_acc_tenant_id
        FROM chart_of_accounts
        WHERE id = NEW.account_id;

        -- Finding C: Enforce cross-tenant consistency between journal_lines, journal_entries, and chart_of_accounts
        IF v_entry_tenant_id IS NOT NULL AND NEW.tenant_id <> v_entry_tenant_id THEN
            RAISE EXCEPTION 'Cross-Tenant Integrity Violation: journal_line tenant_id (%) does not match parent journal_entry tenant_id (%).',
                NEW.tenant_id, v_entry_tenant_id;
        END IF;

        IF v_acc_tenant_id IS NOT NULL AND NEW.tenant_id <> v_acc_tenant_id THEN
            RAISE EXCEPTION 'Cross-Tenant Integrity Violation: journal_line tenant_id (%) does not match chart_of_accounts tenant_id (%).',
                NEW.tenant_id, v_acc_tenant_id;
        END IF;

        -- Finding A: Block inserting additional lines into an already-posted journal entry
        IF v_status = 'posted' THEN
            SELECT COUNT(*), COALESCE(SUM(debit_amount), 0), COALESCE(SUM(credit_amount), 0)
            INTO v_existing_count, v_existing_debit, v_existing_credit
            FROM journal_lines
            WHERE journal_entry_id = NEW.journal_entry_id;

            IF (txid_status(v_entry_xmin::text::bigint) = 'committed') OR
               (v_existing_count >= 2 AND v_existing_debit = v_existing_credit AND v_existing_debit > 0) THEN
                RAISE EXCEPTION 'Audit Immutability Violation: Cannot insert additional lines into an already-posted journal entry (%). Create a reversing entry instead.',
                    NEW.journal_entry_id;
            END IF;
        END IF;

        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_journal_line_immutability ON journal_lines;
CREATE TRIGGER enforce_journal_line_immutability
BEFORE INSERT OR UPDATE OR DELETE ON journal_lines
FOR EACH ROW EXECUTE FUNCTION prevent_posted_journal_line_mutation();

-- PostgreSQL Deferred Constraint Trigger: Enforce Double-Entry Zero-Sum Balance & Minimum 2 Lines
CREATE OR REPLACE FUNCTION check_journal_entry_balance()
RETURNS TRIGGER AS $$
DECLARE
    v_debit NUMERIC(15, 2);
    v_credit NUMERIC(15, 2);
    v_count INT;
    v_status VARCHAR(20);
BEGIN
    SELECT status INTO v_status FROM journal_entries WHERE id = NEW.journal_entry_id;
    IF v_status = 'posted' THEN
        SELECT COUNT(*), COALESCE(SUM(debit_amount), 0), COALESCE(SUM(credit_amount), 0)
        INTO v_count, v_debit, v_credit
        FROM journal_lines
        WHERE journal_entry_id = NEW.journal_entry_id;

        IF v_count < 2 THEN
            RAISE EXCEPTION 'check_zero_sum_balance: Inviolable Double-Entry Invariant Failed! Posted journal entry requires at least 2 lines (found %).',
                v_count;
        END IF;

        IF v_debit <> v_credit THEN
            RAISE EXCEPTION 'check_zero_sum_balance: Inviolable Double-Entry Invariant Failed! Total Debits (%) != Total Credits (%). Discrepancy: %',
                v_debit, v_credit, ABS(v_debit - v_credit);
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_journal_zero_sum_balance ON journal_lines;
CREATE CONSTRAINT TRIGGER enforce_journal_zero_sum_balance
AFTER INSERT OR UPDATE ON journal_lines
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION check_journal_entry_balance();

CREATE OR REPLACE FUNCTION check_journal_entry_has_balanced_lines()
RETURNS TRIGGER AS $$
DECLARE
    v_debit NUMERIC(15, 2);
    v_credit NUMERIC(15, 2);
    v_count INT;
BEGIN
    IF NEW.status = 'posted' THEN
        SELECT COUNT(*), COALESCE(SUM(debit_amount), 0), COALESCE(SUM(credit_amount), 0)
        INTO v_count, v_debit, v_credit
        FROM journal_lines
        WHERE journal_entry_id = NEW.id;

        IF v_count < 2 THEN
            RAISE EXCEPTION 'check_zero_sum_balance: Posted journal entry (%) requires at least 2 journal lines (found %).',
                NEW.entry_number, v_count;
        END IF;

        IF v_debit <> v_credit THEN
            RAISE EXCEPTION 'check_zero_sum_balance: Inviolable Double-Entry Invariant Failed on entry (%): Total Debits (%) != Total Credits (%).',
                NEW.entry_number, v_debit, v_credit;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_journal_entry_has_lines ON journal_entries;
CREATE CONSTRAINT TRIGGER enforce_journal_entry_has_lines
AFTER INSERT OR UPDATE ON journal_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION check_journal_entry_has_balanced_lines();

-- ============================================================================
-- 2B. BANK STATEMENTS & 3-TIER RECONCILIATION ENGINE (PHASE 2)
-- ============================================================================

CREATE TYPE bank_name_enum AS ENUM ('HDFC', 'ICICI', 'SBI', 'AXIS', 'KOTAK', 'OTHER');
CREATE TYPE reconciliation_tier_enum AS ENUM ('unreconciled', 'tier1_exact', 'tier2_heuristic', 'tier3_suspense');
CREATE TYPE reconciliation_status_enum AS ENUM ('pending', 'probable_match', 'reconciled', 'suspense_posted');

CREATE TABLE bank_statements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    bank_name bank_name_enum NOT NULL DEFAULT 'HDFC',
    account_number VARCHAR(64) NOT NULL,
    statement_from DATE,
    statement_to DATE,
    opening_balance NUMERIC(15, 2) DEFAULT 0.00,
    closing_balance NUMERIC(15, 2) DEFAULT 0.00,
    total_withdrawals NUMERIC(15, 2) DEFAULT 0.00,
    total_deposits NUMERIC(15, 2) DEFAULT 0.00,
    file_name VARCHAR(255) NOT NULL,
    file_sha256 CHAR(64),
    s3_key TEXT NOT NULL,
    fiscal_year_id UUID REFERENCES fiscal_years(id) ON DELETE SET NULL,
    status VARCHAR(32) DEFAULT 'parsed',
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_statement_file UNIQUE (tenant_id, file_sha256),
    CONSTRAINT uq_statement_period UNIQUE (tenant_id, account_number, statement_from, statement_to)
);

CREATE INDEX idx_bank_statements_tenant ON bank_statements(tenant_id);

CREATE TABLE bank_statement_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    statement_id UUID NOT NULL REFERENCES bank_statements(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    line_number INT NOT NULL,
    fingerprint CHAR(64),
    transaction_date DATE NOT NULL,
    value_date DATE,
    description TEXT NOT NULL,
    reference_number VARCHAR(128),
    payment_channel VARCHAR(32) DEFAULT 'OTHER', -- UPI, NEFT, RTGS, IMPS, CHEQUE, CHARGES
    counterparty_name VARCHAR(255),
    withdrawal_amount NUMERIC(15, 2) DEFAULT 0.00 CHECK (withdrawal_amount >= 0),
    deposit_amount NUMERIC(15, 2) DEFAULT 0.00 CHECK (deposit_amount >= 0),
    running_balance NUMERIC(15, 2) NOT NULL,
    reconciliation_tier reconciliation_tier_enum DEFAULT 'unreconciled',
    reconciliation_status reconciliation_status_enum DEFAULT 'pending',
    confidence_score NUMERIC(5, 2) DEFAULT 0.00,
    matched_journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    matched_journal_line_id UUID REFERENCES journal_lines(id) ON DELETE SET NULL,
    suspense_journal_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_statement_line_fingerprint UNIQUE (tenant_id, fingerprint)
);

CREATE INDEX idx_statement_lines_tenant ON bank_statement_lines(tenant_id, reconciliation_status);
CREATE INDEX idx_statement_lines_statement ON bank_statement_lines(statement_id);
CREATE INDEX idx_statement_lines_ref ON bank_statement_lines(tenant_id, reference_number);

-- ============================================================================
-- 3. CONTACTS, INVOICING & GST TAX ENGINE (ZOHO/ODOO INSPIRED)
-- ============================================================================

CREATE TYPE invoice_type_enum AS ENUM ('tax_invoice', 'proforma', 'credit_note', 'debit_note');
CREATE TYPE invoice_status_enum AS ENUM ('draft', 'sent', 'paid', 'partially_paid', 'cancelled');

CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    is_customer BOOLEAN DEFAULT TRUE,
    is_vendor BOOLEAN DEFAULT FALSE,
    gstin VARCHAR(15),
    pan VARCHAR(10),
    state_code VARCHAR(2) NOT NULL,
    billing_address TEXT NOT NULL,
    shipping_address TEXT,
    email VARCHAR(255),
    phone VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_contacts_tenant ON contacts(tenant_id);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    contact_id UUID NOT NULL REFERENCES contacts(id),
    invoice_number VARCHAR(64) NOT NULL,
    type invoice_type_enum DEFAULT 'tax_invoice',
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    place_of_supply VARCHAR(2) NOT NULL,   -- 2-digit Indian State code
    is_interstate BOOLEAN NOT NULL DEFAULT FALSE, -- Dynamically evaluated against tenant's state_code
    subtotal NUMERIC(15, 2) NOT NULL,
    cgst_total NUMERIC(15, 2) DEFAULT 0.00,
    sgst_total NUMERIC(15, 2) DEFAULT 0.00,
    igst_total NUMERIC(15, 2) DEFAULT 0.00,
    grand_total NUMERIC(15, 2) NOT NULL,
    tds_amount NUMERIC(15, 2) DEFAULT 0.00 CHECK (tds_amount >= 0),
    status invoice_status_enum DEFAULT 'draft',
    pdf_s3_key TEXT,
    fiscal_year_id UUID REFERENCES fiscal_years(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_tenant_invoice_num UNIQUE(tenant_id, invoice_number)
);

CREATE INDEX idx_invoices_tenant_status ON invoices(tenant_id, status);

CREATE TABLE invoice_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    item_description TEXT NOT NULL,
    hsn_sac_code VARCHAR(10) NOT NULL,
    quantity NUMERIC(12, 3) NOT NULL DEFAULT 1.000,
    unit_price NUMERIC(15, 2) NOT NULL,
    taxable_value NUMERIC(15, 2) NOT NULL,
    gst_rate_percent NUMERIC(5, 2) NOT NULL, -- e.g., 18.00
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00,
    total_amount NUMERIC(15, 2) NOT NULL
);

CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);

-- Trigger function: Ensure is_interstate is correctly evaluated against tenant state
CREATE OR REPLACE FUNCTION trg_evaluate_invoice_interstate()
RETURNS TRIGGER AS $$
DECLARE
    v_tenant_state VARCHAR(2);
BEGIN
    SELECT state_code INTO v_tenant_state FROM tenants WHERE id = NEW.tenant_id;
    IF v_tenant_state IS NOT NULL THEN
        NEW.is_interstate := (NEW.place_of_supply != v_tenant_state);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_invoice_interstate_before_insert_or_update
BEFORE INSERT OR UPDATE OF place_of_supply, tenant_id ON invoices
FOR EACH ROW EXECUTE FUNCTION trg_evaluate_invoice_interstate();

-- ============================================================================
-- 4. EXPENSES & SMART-SCAN (EXPENSIFY INSPIRED WITH TDS SUPPORT)
-- ============================================================================

CREATE TYPE expense_status_enum AS ENUM ('draft', 'submitted', 'approved', 'reimbursed', 'rejected', 'struck_off');
CREATE TYPE tds_section_enum AS ENUM ('none', '194C', '194J', '194I', '194Q', '194H');

CREATE TABLE expenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES users(id),
    merchant_name VARCHAR(255) NOT NULL,
    merchant_gstin VARCHAR(15),
    expense_date DATE NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    total_amount NUMERIC(15, 2) NOT NULL CHECK (total_amount > 0),
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00,
    -- Indian TDS withholding fields
    tds_section tds_section_enum DEFAULT 'none',
    tds_rate NUMERIC(5, 2) DEFAULT 0.00,
    tds_amount NUMERIC(15, 2) DEFAULT 0.00,
    net_payable_amount NUMERIC(15, 2) GENERATED ALWAYS AS (total_amount - tds_amount) STORED,
    category VARCHAR(64) NOT NULL, -- e.g., 'Travel', 'Software / SaaS', 'Legal & Professional', 'Office Rent'
    receipt_s3_key TEXT,
    receipt_sha256 VARCHAR(64),
    fiscal_year_id UUID REFERENCES fiscal_years(id) ON DELETE SET NULL,
    ocr_raw_text TEXT,
    ocr_confidence NUMERIC(5, 2), -- e.g. 94.50%
    status expense_status_enum DEFAULT 'draft',
    paid_personally BOOLEAN DEFAULT FALSE,
    director_name VARCHAR(128),
    payment_mode VARCHAR(64) DEFAULT 'company_bank',
    journal_entry_number VARCHAR(64),
    has_company_gstin BOOLEAN DEFAULT FALSE,
    itc_eligible BOOLEAN DEFAULT FALSE,
    settlement_status VARCHAR(32) DEFAULT 'pending',
    notes TEXT,
    approved_by UUID REFERENCES users(id),
    reimbursed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_expenses_tenant_status ON expenses(tenant_id, status);
CREATE INDEX idx_expenses_tenant_receipt_sha ON expenses(tenant_id, receipt_sha256);

CREATE TABLE expense_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    expense_id UUID NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    changed_by UUID NOT NULL REFERENCES users(id),
    action VARCHAR(32) NOT NULL,
    field_changes JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_expense_audit_logs_expense ON expense_audit_logs(expense_id);
CREATE INDEX idx_expense_audit_logs_tenant ON expense_audit_logs(tenant_id);

-- ============================================================================
-- 5. FOUNDATIONAL DOCUMENT LOCKER (VAULT)
-- ============================================================================

CREATE TYPE document_category_enum AS ENUM (
    'corporate_legal',    -- COI, MOA, AOA, INC-20A
    'tax_registration',   -- PAN, TAN, GST REG-06, PT
    'operational_license',-- MSME, DPIIT, Shop & Est, Trademark
    'equity_governance',  -- Share Certificates, PAS-3, SH-7, Board Resolutions
    'statutory_filing'    -- Filed AOC-4, MGT-7, Audit Reports
);

CREATE TABLE document_vault (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    category document_category_enum NOT NULL,
    document_name VARCHAR(255) NOT NULL,
    document_number VARCHAR(128), -- e.g., Certificate No., Udyam Reg No.
    issue_date DATE,
    expiry_date DATE,
    minio_s3_key TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(64) NOT NULL,
    sha256_hash CHAR(64) NOT NULL,
    is_confidential BOOLEAN DEFAULT FALSE,
    uploaded_by UUID REFERENCES users(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_vault_tenant_category ON document_vault(tenant_id, category);

CREATE TYPE sync_status_enum AS ENUM ('pending', 'syncing', 'synced', 'failed');

CREATE TABLE cloud_sync_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL, -- 'statements', 'receipts', 'statutory', 'invoices'
    fiscal_year VARCHAR(32) NOT NULL, -- e.g. 'FY_2025-2026'
    s3_bucket VARCHAR(128) NOT NULL,
    s3_key TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    sha256_checksum CHAR(64) NOT NULL,
    gdrive_file_id VARCHAR(255),
    gdrive_folder_path TEXT NOT NULL,
    gdrive_md5_checksum VARCHAR(64),
    status sync_status_enum NOT NULL DEFAULT 'pending',
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 5,
    last_error TEXT,
    synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sync_tenant_status ON cloud_sync_ledger(tenant_id, status);
CREATE INDEX idx_sync_sha256 ON cloud_sync_ledger(sha256_checksum);
CREATE INDEX idx_sync_s3_key ON cloud_sync_ledger(s3_key);

ALTER TABLE cloud_sync_ledger ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 6. STATUTORY COMPLIANCE WATCHDOG & COUNTDOWN ENGINE
-- ============================================================================

CREATE TYPE compliance_category_enum AS ENUM (
    'board_meeting_120d', -- Section 173: max 120 days between consecutive board meetings
    'partner_meeting',    -- LLP: Periodic meeting of Designated Partners
    'dir3_kyc',           -- Annual Director/Designated Partner KYC by Sep 30
    'aoc_4',              -- Financial statements filing within 30 days of AGM
    'mgt_7',              -- Annual Return filing within 60 days of AGM
    'llp_form_11',        -- LLP: Annual Return under Rule 25(1) by May 30
    'llp_form_8',         -- LLP: Statement of Account & Solvency under Rule 24 by Oct 30
    'inc_20a',            -- Commencement of Business within 180 days of incorporation
    'advance_tax',        -- Advance tax installments (Jun 15, Sep 15, Dec 15, Mar 15)
    'gstr_1',             -- Monthly/Quarterly GST Outward Supplies
    'gstr_3b',            -- Monthly Summary GST Return
    'itr_filing'          -- Annual Corporate / Partnership Income Tax Return (ITR-5/6)
);

CREATE TYPE compliance_status_enum AS ENUM ('upcoming', 'due_soon', 'overdue', 'completed', 'waived');

CREATE TABLE compliance_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    category compliance_category_enum NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date DATE NOT NULL,
    statutory_reference VARCHAR(128),  -- e.g. 'Companies Act 2013 Sec 173(1)'
    fine_per_day_inr NUMERIC(10, 2) DEFAULT 0.00, -- e.g. 100.00 for MCA late fees
    status compliance_status_enum DEFAULT 'upcoming',
    completed_at TIMESTAMPTZ,
    document_id UUID REFERENCES document_vault(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_compliance_tenant_due ON compliance_events(tenant_id, due_date, status);

-- ============================================================================
-- 7. HARDWARE TOKEN DSC & AUDIT-TRAIL REGISTRY (HYP 2003)
-- ============================================================================

CREATE TABLE dsc_signature_audit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    document_type VARCHAR(64) NOT NULL, -- 'board_minutes', 'invoice', 'aoc4', 'mgt7'
    document_id UUID NOT NULL,
    signer_user_id UUID NOT NULL REFERENCES users(id),
    signer_din VARCHAR(8),
    signer_name VARCHAR(255) NOT NULL,
    token_model VARCHAR(128) DEFAULT 'HyperPKI HYP2003',
    token_serial_number VARCHAR(128),
    certificate_issuer TEXT NOT NULL,   -- e.g., 'CN=eMudhra Sub CA Class 3'
    certificate_valid_to TIMESTAMPTZ NOT NULL,
    sha256_document_hash CHAR(64) NOT NULL,
    signed_cms_signature_s3_key TEXT NOT NULL,
    signed_pdf_s3_key TEXT NOT NULL,
    ip_address INET NOT NULL,
    signed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dsc_audit_tenant_doc ON dsc_signature_audit(tenant_id, document_type, document_id);

-- ============================================================================
-- 7b. CORPORATE MEETINGS & SS-1 GOVERNANCE REGISTRY
-- ============================================================================

CREATE TABLE IF NOT EXISTS corporate_meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    meeting_type VARCHAR(50) NOT NULL DEFAULT 'board_meeting', -- 'board_meeting', 'egm', 'agm'
    meeting_number VARCHAR(50) NOT NULL,
    meeting_date DATE NOT NULL,
    meeting_time VARCHAR(50) NOT NULL,
    venue TEXT NOT NULL,
    directors_present JSONB NOT NULL DEFAULT '[]'::jsonb,
    agenda_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    resolutions JSONB NOT NULL DEFAULT '[]'::jsonb,
    signed_document_key VARCHAR(255),
    sha256_hash VARCHAR(64),
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_corporate_meetings_tenant_date ON corporate_meetings(tenant_id, meeting_date);

-- View for journal_items alias
CREATE OR REPLACE VIEW journal_items AS SELECT * FROM journal_lines;

-- ============================================================================
-- 7c. DATABASE BACKUP AUDIT LOGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS database_backup_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    filename VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    sha256_checksum VARCHAR(64) NOT NULL,
    encryption_algorithm VARCHAR(32) DEFAULT 'AES-256-GCM',
    gdrive_file_id VARCHAR(128),
    gdrive_folder_path TEXT,
    status VARCHAR(32) DEFAULT 'completed',
    duration_seconds NUMERIC(6, 2) DEFAULT 0.00,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 8. ROW-LEVEL SECURITY (RLS) POLICIES (FINDING B: COMPLETE FORCE RLS)
-- ============================================================================

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal_years ENABLE ROW LEVEL SECURITY;
ALTER TABLE chart_of_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE expense_audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_vault ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_sync_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE corporate_meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dsc_signature_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_statements ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_statement_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE database_backup_logs ENABLE ROW LEVEL SECURITY;

-- Enforce RLS even for table owners on ALL tenant-scoped tables
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_users FORCE ROW LEVEL SECURITY;
ALTER TABLE fiscal_years FORCE ROW LEVEL SECURITY;
ALTER TABLE chart_of_accounts FORCE ROW LEVEL SECURITY;
ALTER TABLE journal_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE journal_lines FORCE ROW LEVEL SECURITY;
ALTER TABLE contacts FORCE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
ALTER TABLE invoice_items FORCE ROW LEVEL SECURITY;
ALTER TABLE expenses FORCE ROW LEVEL SECURITY;
ALTER TABLE expense_audit_logs FORCE ROW LEVEL SECURITY;
ALTER TABLE document_vault FORCE ROW LEVEL SECURITY;
ALTER TABLE cloud_sync_ledger FORCE ROW LEVEL SECURITY;
ALTER TABLE corporate_meetings FORCE ROW LEVEL SECURITY;
ALTER TABLE compliance_events FORCE ROW LEVEL SECURITY;
ALTER TABLE dsc_signature_audit FORCE ROW LEVEL SECURITY;
ALTER TABLE bank_statements FORCE ROW LEVEL SECURITY;
ALTER TABLE bank_statement_lines FORCE ROW LEVEL SECURITY;
ALTER TABLE database_backup_logs FORCE ROW LEVEL SECURITY;

-- Helper RLS predicate macro using session variable 'app.current_tenant'
CREATE POLICY tenant_isolation_tenants ON tenants
    FOR ALL
    USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_tenant_users ON tenant_users
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_coa ON chart_of_accounts
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- DEF-04 & Finding B: Strict FOR ALL USING + WITH CHECK policies across all tenant tables
CREATE POLICY tenant_isolation_policy ON corporate_meetings
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_policy ON invoices
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
    );

CREATE POLICY tenant_isolation_policy ON expenses
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND (
            COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
            OR employee_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND (
            COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
            OR employee_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
    );

CREATE POLICY tenant_isolation_policy ON document_vault
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
    );

CREATE POLICY tenant_isolation_policy ON journal_entries
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
    );

CREATE POLICY tenant_isolation_policy ON journal_lines
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'admin') NOT IN ('employee')
    );

CREATE POLICY tenant_isolation_contacts ON contacts
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_invoice_items ON invoice_items
    FOR ALL
    USING (invoice_id IN (SELECT id FROM invoices WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid))
    WITH CHECK (invoice_id IN (SELECT id FROM invoices WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid));

CREATE POLICY tenant_isolation_compliance ON compliance_events
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_dsc ON dsc_signature_audit
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_bank_statements ON bank_statements
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_bank_statement_lines ON bank_statement_lines
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_cloud_sync ON cloud_sync_ledger
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_fiscal_years ON fiscal_years
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_expense_audit_logs ON expense_audit_logs
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_backup_logs ON database_backup_logs
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);


-- ============================================================================
-- 9. DEFAULT CHART OF ACCOUNTS AUTO-SEED FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION seed_tenant_chart_of_accounts(p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
    INSERT INTO chart_of_accounts (tenant_id, code, name, type, sub_type, normal_balance, description) VALUES
    -- 1000–1999: Non-Current Assets & Current Assets (Schedule III)
    (p_tenant_id, '1010', 'Bank Current Account (HDFC/ICICI)', 'asset', 'bank', 'debit', 'Primary operating bank account'),
    (p_tenant_id, '1020', 'Trade Receivables (Debtors)', 'asset', 'current_asset', 'debit', 'Customer outstanding invoices'),
    (p_tenant_id, '1030', 'Input CGST', 'asset', 'tax_asset', 'debit', 'Input Central GST Credit on purchases'),
    (p_tenant_id, '1031', 'Input SGST', 'asset', 'tax_asset', 'debit', 'Input State GST Credit on purchases'),
    (p_tenant_id, '1032', 'Input IGST', 'asset', 'tax_asset', 'debit', 'Input Integrated GST Credit on inter-state purchases'),
    (p_tenant_id, '1040', 'Loans & Advances / Prepayments', 'asset', 'current_asset', 'debit', 'Prepaid subscriptions & security deposits'),
    (p_tenant_id, '1050', 'Property, Plant & Equipment (Hardware)', 'asset', 'fixed_asset', 'debit', 'Office computers, servers & IT hardware'),
    (p_tenant_id, '1059', 'Accumulated Depreciation - Fixed Assets', 'asset', 'fixed_asset', 'credit', 'Contra-asset for cumulative Schedule II depreciation'),

    -- 2000–2999: Equity & Liabilities (Schedule III)
    (p_tenant_id, '2010', 'Paid-up Equity Share Capital', 'equity', 'share_capital', 'credit', 'Nominal value of equity shares issued'),
    (p_tenant_id, '2015', 'Prior Period Statutory Adjustments (Surplus/Deficit)', 'equity', 'retained_earnings', 'credit', 'AS-5 / Section 128 adjustments between filed returns and ledger'),
    (p_tenant_id, '2020', 'Reserves & Surplus / Retained Earnings', 'equity', 'retained_earnings', 'credit', 'Accumulated profits or losses'),
    (p_tenant_id, '2030', 'Long-Term & Director Borrowings', 'liability', 'director_loan', 'credit', 'Unsecured loans from directors/promoters'),
    (p_tenant_id, '2040', 'Trade Payables (Creditors)', 'liability', 'current_liability', 'credit', 'Vendor unpaid bills & invoices'),
    (p_tenant_id, '2050', 'Output CGST', 'liability', 'tax_liability', 'credit', 'Central GST collected on intra-state sales'),
    (p_tenant_id, '2051', 'Output SGST', 'liability', 'tax_liability', 'credit', 'State GST collected on intra-state sales'),
    (p_tenant_id, '2052', 'Output IGST', 'liability', 'tax_liability', 'credit', 'Integrated GST collected on inter-state sales'),
    (p_tenant_id, '2060', 'TDS Payable u/s 194J (Professional)', 'liability', 'tax_liability', 'credit', 'TDS on tech/professional services'),
    (p_tenant_id, '2061', 'TDS Payable u/s 194C (Contractor)', 'liability', 'tax_liability', 'credit', 'TDS on contractor invoices'),
    (p_tenant_id, '2062', 'TDS Payable u/s 194I (Rent)', 'liability', 'tax_liability', 'credit', 'TDS on rent of land, building & machinery'),
    (p_tenant_id, '2063', 'TDS Payable u/s 194Q (Purchase of Goods)', 'liability', 'tax_liability', 'credit', 'TDS on high-value goods purchases'),
    (p_tenant_id, '2064', 'TCS Payable u/s 206C', 'liability', 'tax_liability', 'credit', 'Tax Collected at Source on sales'),
    (p_tenant_id, '2099', 'Suspense Account (Bank Reconciliation)', 'liability', 'suspense', 'credit', 'Unmatched bank statement lines pending allocation'),

    -- 3000–3999: Revenue from Operations & Other Income (Schedule III)
    (p_tenant_id, '3010', 'Revenue from Operations (Software & Consulting)', 'revenue', 'operating_revenue', 'credit', 'Core subscription & service sales'),
    (p_tenant_id, '3020', 'Other Income & Interest Received', 'revenue', 'other_income', 'credit', 'Bank interest & non-operating income'),

    -- 4000–4999: Expenses (Schedule III)
    (p_tenant_id, '4010', 'Direct Expenses / Cloud Hosting (AWS/GCP)', 'expense', 'direct_expense', 'debit', 'Cloud servers, databases & infrastructure'),
    (p_tenant_id, '4020', 'Employee Benefit Expenses / Payroll', 'expense', 'payroll', 'debit', 'Salaries, stipends and contractor payouts'),
    (p_tenant_id, '4030', 'Finance Costs & Bank Charges', 'expense', 'financial_expense', 'debit', 'Payment gateway fees & wire charges'),
    (p_tenant_id, '4040', 'Legal & Professional Fees (CA/CS/ROC)', 'expense', 'professional_fees', 'debit', 'Auditor retainer, CS filings, legal advisory'),
    (p_tenant_id, '4050', 'Rent & Workplace Expenses', 'expense', 'rent', 'debit', 'Office lease, coworking and utilities'),
    (p_tenant_id, '4070', 'Depreciation & Amortization Expense', 'expense', 'depreciation', 'debit', 'Schedule II Companies Act depreciation on fixed assets');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- 10. STATUTORY BASELINE ANCHORS & ADVANCE TAX FORECASTING (PHASE 8)
-- ============================================================================

CREATE TABLE IF NOT EXISTS statutory_filing_anchors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    fiscal_year VARCHAR(32) NOT NULL,
    assessment_year VARCHAR(32) NOT NULL,
    form_type VARCHAR(50) NOT NULL,
    srn_or_ack_number VARCHAR(100) NOT NULL,
    filing_date DATE NOT NULL,
    signatory_din VARCHAR(8),
    auditor_udin VARCHAR(18),
    s3_document_key VARCHAR(500),
    document_sha256 VARCHAR(64),
    schedule_iii_payload JSONB NOT NULL DEFAULT '{}',
    is_locked BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tenant_fy_form UNIQUE (tenant_id, fiscal_year, form_type)
);

CREATE INDEX IF NOT EXISTS idx_statutory_anchors_tenant_fy ON statutory_filing_anchors(tenant_id, fiscal_year);
ALTER TABLE statutory_filing_anchors ENABLE ROW LEVEL SECURITY;
ALTER TABLE statutory_filing_anchors FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_statutory_anchors ON statutory_filing_anchors
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE TABLE IF NOT EXISTS advance_tax_forecasts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fiscal_year VARCHAR(32) NOT NULL,
    assessment_year VARCHAR(32) NOT NULL,
    calculation_date DATE NOT NULL,
    tax_regime VARCHAR(50) NOT NULL,
    ytd_revenue NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    ytd_expenses NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    ytd_net_profit NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    projected_annual_profit NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    effective_tax_rate NUMERIC(6, 3) NOT NULL,
    gross_projected_tax NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    tds_tcs_credits_claimed NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    net_advance_tax_payable NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    q1_due NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    q2_due NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    q3_due NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    q4_due NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    q1_paid NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    q2_paid NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    q3_paid NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    q4_paid NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    interest_234c_projected NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    interest_234b_projected NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_advance_tax_forecasts_tenant ON advance_tax_forecasts(tenant_id, fiscal_year);
ALTER TABLE advance_tax_forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE advance_tax_forecasts FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_advance_tax_forecasts ON advance_tax_forecasts
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE TABLE IF NOT EXISTS advance_tax_challans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fiscal_year VARCHAR(32) NOT NULL,
    quarter VARCHAR(2) NOT NULL,
    payment_date DATE NOT NULL,
    bsr_code VARCHAR(7) NOT NULL,
    challan_serial_no VARCHAR(10) NOT NULL,
    cin_number VARCHAR(30),
    amount_paid NUMERIC(15, 2) NOT NULL,
    s3_challan_receipt_key VARCHAR(500),
    bank_statement_line_id UUID REFERENCES bank_statement_lines(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tenant_challan UNIQUE (tenant_id, bsr_code, challan_serial_no)
);

CREATE INDEX IF NOT EXISTS idx_advance_tax_challans_tenant ON advance_tax_challans(tenant_id, fiscal_year);
ALTER TABLE advance_tax_challans ENABLE ROW LEVEL SECURITY;
ALTER TABLE advance_tax_challans FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_advance_tax_challans ON advance_tax_challans
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE TABLE IF NOT EXISTS gst_challans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fiscal_year VARCHAR(32) NOT NULL,
    period VARCHAR(32) NOT NULL,
    frequency VARCHAR(32) NOT NULL,
    challan_type VARCHAR(32) NOT NULL,
    cpin VARCHAR(20) NOT NULL,
    cin VARCHAR(30),
    payment_date DATE NOT NULL,
    bank_ref_no VARCHAR(50),
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00 NOT NULL,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00 NOT NULL,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00 NOT NULL,
    cess_amount NUMERIC(15, 2) DEFAULT 0.00 NOT NULL,
    interest_amount NUMERIC(15, 2) DEFAULT 0.00 NOT NULL,
    penalty_amount NUMERIC(15, 2) DEFAULT 0.00 NOT NULL,
    total_amount NUMERIC(15, 2) NOT NULL,
    s3_challan_receipt_key VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tenant_gst_cpin UNIQUE (tenant_id, cpin)
);

CREATE INDEX IF NOT EXISTS idx_gst_challans_tenant ON gst_challans(tenant_id, fiscal_year);
ALTER TABLE gst_challans ENABLE ROW LEVEL SECURITY;
ALTER TABLE gst_challans FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_gst_challans ON gst_challans
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- ============================================================================
-- 11. INDIAN TDS & SCHEDULE II FIXED ASSETS TABLES (PHASE 10)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tds_challans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fiscal_year VARCHAR(32) NOT NULL,
    quarter VARCHAR(2) NOT NULL,
    section VARCHAR(32) NOT NULL,
    bsr_code VARCHAR(7) NOT NULL,
    challan_serial_no VARCHAR(10) NOT NULL,
    payment_date DATE NOT NULL,
    tds_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    surcharge_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    cess_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    interest_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    fee_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    total_amount NUMERIC(15, 2) NOT NULL,
    cin VARCHAR(30),
    minor_head VARCHAR(10) DEFAULT '200',
    s3_challan_receipt_key VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tenant_tds_challan UNIQUE (tenant_id, bsr_code, challan_serial_no)
);

CREATE INDEX IF NOT EXISTS idx_tds_challans_tenant ON tds_challans(tenant_id, fiscal_year);
ALTER TABLE tds_challans ENABLE ROW LEVEL SECURITY;
ALTER TABLE tds_challans FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_tds_challans ON tds_challans
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE TABLE IF NOT EXISTS tds_deductions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    expense_id UUID REFERENCES expenses(id) ON DELETE SET NULL,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    deductee_name VARCHAR(255) NOT NULL,
    deductee_pan VARCHAR(10) NOT NULL,
    deductee_type VARCHAR(20) DEFAULT 'COMPANY',
    section VARCHAR(32) NOT NULL,
    rate_percentage NUMERIC(5, 2) NOT NULL,
    gross_amount NUMERIC(15, 2) NOT NULL,
    tds_amount NUMERIC(15, 2) NOT NULL,
    net_payable NUMERIC(15, 2) NOT NULL,
    deduction_date DATE NOT NULL,
    fiscal_year VARCHAR(32) NOT NULL,
    quarter VARCHAR(2) NOT NULL,
    tds_challan_id UUID REFERENCES tds_challans(id) ON DELETE SET NULL,
    certificate_number VARCHAR(50),
    status VARCHAR(32) DEFAULT 'PENDING_DEPOSIT',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tds_deductions_tenant ON tds_deductions(tenant_id, fiscal_year, quarter);
ALTER TABLE tds_deductions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tds_deductions FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_tds_deductions ON tds_deductions
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE TABLE IF NOT EXISTS fixed_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    asset_code VARCHAR(50) NOT NULL,
    asset_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    purchase_date DATE NOT NULL,
    capitalization_date DATE NOT NULL,
    gross_block NUMERIC(15, 2) NOT NULL,
    salvage_value NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    useful_life_years NUMERIC(5, 2) NOT NULL,
    depreciation_method VARCHAR(20) NOT NULL DEFAULT 'SLM',
    accumulated_depreciation NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    net_block NUMERIC(15, 2) NOT NULL,
    location VARCHAR(255),
    serial_number VARCHAR(100),
    status VARCHAR(50) DEFAULT 'ACTIVE',
    purchase_journal_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tenant_asset_code UNIQUE (tenant_id, asset_code)
);

CREATE INDEX IF NOT EXISTS idx_fixed_assets_tenant ON fixed_assets(tenant_id, status);
ALTER TABLE fixed_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE fixed_assets FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_fixed_assets ON fixed_assets
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE TABLE IF NOT EXISTS fixed_asset_depreciation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fiscal_year VARCHAR(32) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    run_date DATE NOT NULL,
    total_depreciation_amount NUMERIC(15, 2) NOT NULL,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'POSTED',
    details JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_depreciation_runs_tenant ON fixed_asset_depreciation_runs(tenant_id, fiscal_year);
ALTER TABLE fixed_asset_depreciation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE fixed_asset_depreciation_runs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_depreciation_runs ON fixed_asset_depreciation_runs
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- ==============================================================================
-- PHASE 11: E-INVOICING (IRN/QR) & MCA STATUTORY REGISTERS (MGT-1, MBP-1/2/4, SH-1)
-- ==============================================================================

-- 1. E-Invoicing columns on invoices
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS irn VARCHAR(64);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS ack_no VARCHAR(32);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS ack_date TIMESTAMPTZ;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS signed_qr_code TEXT;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS irn_status VARCHAR(32) DEFAULT 'PENDING';
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS einvoice_payload JSONB;

-- 2. Form MGT-1 Register of Members (Sec 88)
CREATE TABLE IF NOT EXISTS statutory_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    folio_number VARCHAR(64) NOT NULL,
    member_name VARCHAR(255) NOT NULL,
    father_or_spouse_name VARCHAR(255),
    pan VARCHAR(10),
    email VARCHAR(255),
    address TEXT,
    date_of_becoming_member DATE NOT NULL,
    date_of_cessation DATE,
    number_of_shares NUMERIC(15, 2) NOT NULL,
    distinctive_from BIGINT NOT NULL,
    distinctive_to BIGINT NOT NULL,
    nominal_value_per_share NUMERIC(10, 2) DEFAULT 10.00,
    amount_paid_per_share NUMERIC(10, 2) DEFAULT 10.00,
    certificate_number VARCHAR(64),
    status VARCHAR(32) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_tenant_folio UNIQUE(tenant_id, folio_number)
);

CREATE INDEX IF NOT EXISTS idx_members_tenant ON statutory_members(tenant_id);
ALTER TABLE statutory_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE statutory_members FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_members ON statutory_members
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- 3. Form MBP-2 Register of Loans & Guarantees (Sec 186)
CREATE TABLE IF NOT EXISTS statutory_loans_guarantees (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    transaction_type VARCHAR(32) NOT NULL,
    body_corporate_name VARCHAR(255) NOT NULL,
    cin_or_pan VARCHAR(32),
    amount NUMERIC(15, 2) NOT NULL,
    interest_rate_pct NUMERIC(5, 2),
    tenure_months INT,
    board_resolution_date DATE NOT NULL,
    special_resolution_date DATE,
    status VARCHAR(32) DEFAULT 'ACTIVE',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loans_tenant ON statutory_loans_guarantees(tenant_id);
ALTER TABLE statutory_loans_guarantees ENABLE ROW LEVEL SECURITY;
ALTER TABLE statutory_loans_guarantees FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_loans ON statutory_loans_guarantees
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- 4. Form MBP-4 Register of Contracts with Interested Directors (Sec 189)
CREATE TABLE IF NOT EXISTS statutory_contracts_interested_directors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    contract_date DATE NOT NULL,
    party_name VARCHAR(255) NOT NULL,
    nature_of_contract TEXT NOT NULL,
    contract_value NUMERIC(15, 2),
    director_name VARCHAR(255) NOT NULL,
    director_din VARCHAR(8),
    nature_of_interest TEXT NOT NULL,
    board_meeting_date DATE NOT NULL,
    voting_status VARCHAR(64) DEFAULT 'ABSTAINED',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contracts_tenant ON statutory_contracts_interested_directors(tenant_id);
ALTER TABLE statutory_contracts_interested_directors ENABLE ROW LEVEL SECURITY;
ALTER TABLE statutory_contracts_interested_directors FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_contracts ON statutory_contracts_interested_directors
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- 5. Director Annual Disclosures (MBP-1 & DIR-8)
CREATE TABLE IF NOT EXISTS director_annual_disclosures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    fiscal_year VARCHAR(10) NOT NULL,
    form_type VARCHAR(16) NOT NULL,
    director_name VARCHAR(255) NOT NULL,
    director_din VARCHAR(8) NOT NULL,
    filing_date DATE NOT NULL,
    disclosure_payload JSONB NOT NULL,
    is_digitally_signed BOOLEAN DEFAULT FALSE,
    signed_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_disclosures_tenant ON director_annual_disclosures(tenant_id, fiscal_year);
ALTER TABLE director_annual_disclosures ENABLE ROW LEVEL SECURITY;
ALTER TABLE director_annual_disclosures FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_disclosures ON director_annual_disclosures
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- 6. Form SH-1 Digital Share Certificates (Sec 46)
CREATE TABLE IF NOT EXISTS share_certificates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    certificate_number VARCHAR(64) NOT NULL,
    member_id UUID NOT NULL REFERENCES statutory_members(id) ON DELETE RESTRICT,
    number_of_shares INT NOT NULL,
    distinctive_from BIGINT NOT NULL,
    distinctive_to BIGINT NOT NULL,
    face_value NUMERIC(10, 2) DEFAULT 10.00,
    issue_date DATE NOT NULL,
    signatory_director_1 VARCHAR(255),
    signatory_director_2 VARCHAR(255),
    signatory_secretary_or_authorized VARCHAR(255),
    status VARCHAR(32) DEFAULT 'ISSUED',
    pdf_s3_key TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_tenant_cert_num UNIQUE(tenant_id, certificate_number)
);

CREATE INDEX IF NOT EXISTS idx_certs_tenant ON share_certificates(tenant_id);
ALTER TABLE share_certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE share_certificates FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_certs ON share_certificates
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- Grant table, sequence, and function privileges to non-superuser application role b00k5_app
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO b00k5_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO b00k5_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO b00k5_app;

