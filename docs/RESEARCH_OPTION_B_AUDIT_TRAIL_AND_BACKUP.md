# Option B Research Specification: MCA Rule 3(1) Immutable Audit Trail & Local Air-Gapped Backup

> **Document Type:** Research & Feature Specification (Deferred Milestone)  
> **Feature IDs:** `FEAT-AUDIT-01` (MCA Audit Trail) & `FEAT-SYS-02` (Air-Gapped Local Backup)  
> **Status:** Documented for Future Implementation  
> **Target Audience:** Indian Private Limited Companies, LLPs, CAs, and System Architects

---

## 1. Executive Summary

Option B addresses statutory audit compliance under Indian corporate law and data resilience for air-gapped or locally-hosted deployments. It comprises two distinct pillars:
1. **MCA Rule 3(1) Companies (Accounts) Rules, 2014 Amendment**: Mandatory immutable audit trail (edit log) for any electronic accounting software used by an Indian legal entity, effective 1 April 2023.
2. **Local Air-Gapped Encrypted Backup & Restore**: Automated cryptographic snapshotting of PostgreSQL and S3 MinIO storage into an encrypted archive file (`.b00k5.enc`), ensuring zero cloud vendor dependency and disaster recovery on local hardware.

---

## 2. Pillar 1: MCA Rule 3(1) Companies (Accounts) Rules, 2014 Mandate

### 2.1 Statutory Invariants & Legal Background
Under the notification issued by the Ministry of Corporate Affairs (MCA) amending Rule 3(1) of the Companies (Accounts) Rules, 2014:
* Every company that uses accounting software for maintaining books of account must use software with a feature of recording an **audit trail of each and every transaction, creating an edit log of each change made in the books of account along with the date when such changes were made**.
* The software must ensure that the audit trail **cannot be disabled or tampered with**.
* Under Section 143(3)(b) and Rule 11(g) of the Companies (Audit and Auditors) Rules, 2014, statutory auditors must explicitly report:
  > *"Whether the company has used such accounting software for maintaining its books of account which has a feature of recording audit trail (edit log) facility and the same has operated throughout the year for all transactions recorded in the software, and the audit trail feature has not been tampered with and the audit trail has been preserved by the company as per the statutory requirements for record retention."*

### 2.2 Architectural Blueprint & Invariants
```
┌────────────────────────────────────────────────────────────────────────┐
│                   b00k5 MCA Rule 3(1) Audit Architecture               │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   [ Transaction Execution: Invoices, Vouchers, Payments ]              │
│                           │                                            │
│                           ▼                                            │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │   PostgreSQL Kernel-Level Trigger: on_change_audit_trigger   │     │
│   │   - Fires BEFORE/AFTER INSERT, UPDATE, DELETE                │     │
│   │   - Cannot be bypassed by application-level logic            │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                           │                                            │
│                           ▼                                            │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │   Table: accounting_audit_trail                              │     │
│   │   - id (UUID), tenant_id, table_name, record_id              │     │
│   │   - action ('INSERT', 'UPDATE', 'DELETE')                    │     │
│   │   - user_id, user_email, ip_address, timestamp (UTC)         │     │
│   │   - old_state (JSONB), new_state (JSONB), changed_fields     │     │
│   │   - prev_hash (SHA-256), current_hash (SHA-256 Merkle Link)  │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                           │                                            │
│                           ▼                                            │
│   [ REVOKE UPDATE, DELETE ON accounting_audit_trail FROM b00k5_app ]   │
│   (Immutable Append-Only Guarantee: Even app role cannot alter log)     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Proposed Database DDL
```sql
CREATE TABLE IF NOT EXISTS accounting_audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    table_name VARCHAR(64) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(16) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    performed_by UUID REFERENCES users(id),
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    old_state JSONB,
    new_state JSONB,
    changed_fields TEXT[],
    prev_hash VARCHAR(64) NOT NULL,
    current_hash VARCHAR(64) NOT NULL
);

-- Kernel Level Inviolability: Prohibit UPDATE or DELETE on audit trail
CREATE OR REPLACE FUNCTION prevent_audit_tampering()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'MCA Rule 3(1) Violation: Modification or deletion of audit logs is strictly prohibited by law.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_trail_immutability_trigger
BEFORE UPDATE OR DELETE ON accounting_audit_trail
FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();
```

---

## 3. Pillar 2: Air-Gapped Local Encrypted Backup & Restore

### 3.1 Problem Statement for Local Deployments
When running `b00k5` on local machines (macOS, Linux workstation, or private on-prem NAS):
1. No managed cloud backups (like AWS RDS automated daily snapshots or Point-in-Time Recovery).
2. Hardware failures, disk corruption, or accidental `docker compose down -v` can result in total data loss.
3. Unencrypted database dumps (like raw `pg_dump.sql`) leak sensitive corporate payroll, PANs, bank accounts, and profit margins to local workstation storage.

### 3.2 Backup Architecture Specification
```
┌────────────────────────────────────────────────────────────────────────┐
│                   Air-Gapped Backup Pipeline Architecture              │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   1. CLI / UI Trigger: "Create Sovereign Backup Snapshot"              │
│                           │                                            │
│                           ▼                                            │
│   2. Atomic Snapshot Generation:                                       │
│      - pg_dump: PostgreSQL relational database state                   │
│      - minio_export: Attached invoice PDFs, vouchers & signed docs     │
│      - manifest.json: Commit SHA, schema version, record counts        │
│                           │                                            │
│                           ▼                                            │
│   3. Cryptographic Packaging:                                          │
│      - Tarball creation -> TAR stream                                  │
│      - Symmetric Encryption: AES-256-GCM using Master Passphrase       │
│      - Authentication Tag: 128-bit GCM MAC for tamper detection        │
│                           │                                            │
│                           ▼                                            │
│   4. Output Artifact: b00k5-backup-YYYYMMDD-HHMMSS.b00k5.enc           │
│      (Saved to local directory or external USB media)                  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.3 CLI & API Contract
* **Backup Command:** `bin/b00k5-backup.sh --output /path/to/backup.b00k5.enc --passphrase-env BACKUP_KEY`
* **Restore Command:** `bin/b00k5-restore.sh --input /path/to/backup.b00k5.enc --verify-only`
* **UI Action:** Located under `/vault` -> **"Local Backup & Disaster Recovery"**. Single-click download of `.b00k5.enc` file.

---

## 4. Why Deferred in Favor of Option A
* **Current Operational Priority:** `b00k5` is already running on a local Docker volume with persistent bind mounts (`b00k5_postgres_data` and `minio_data`).
* Option A (Bank CMS & GSTR-1 JSON) provides immediate monthly cash-flow and filing utility. Option B can be implemented prior to statutory annual audit closing.
