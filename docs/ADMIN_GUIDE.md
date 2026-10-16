# b00k5 Administrator & Operations Manual

## 1. System Requirements & Fleet Topology

### 1.1 Minimum Hardware Specifications
* **CPU:** 2 vCPU cores (x86_64 or Apple Silicon ARM64; 4 cores recommended for production).
* **RAM:** 4 GB minimum (8 GB recommended for concurrent OCR image extraction and PDF generation).
* **Storage:** 20 GB NVMe / SSD for container images, PostgreSQL database, and MinIO document storage.

### 1.2 Host Software Requirements
* **Operating System:** Linux (Ubuntu 22.04+ LTS, Debian 12+, RHEL 9+), macOS (13+ Ventura/Sonoma/Sequoia), or Windows 11 with WSL2.
* **Container Engine:** Docker Engine v24.0+ or Docker Desktop.
* **Compose Engine:** Docker Compose v2.20+.
* **System Utilities:** `curl`, `bash`, `tar`, `gzip`.

### 1.3 Fleet Service Inventory
When launched via `docker compose up -d`, b00k5 boots 9 isolated services:
1. `b00k5_web`: Next.js 15 App Router web GUI (Port 3000).
2. `b00k5_api`: FastAPI core financial engine (Port 8000).
3. `b00k5_postgres`: PostgreSQL 16 database with RLS & kernel triggers (Port 5432).
4. `b00k5_redis`: Redis 7 in-memory cache and task broker (Port 6379).
5. `b00k5_minio`: Sovereign S3-compatible document vault (Ports 9000 API, 9001 Console).
6. `b00k5_worker_ocr`: Celery worker dedicated to OCR bill processing (`ocr_queue`).
7. `b00k5_worker_reconcile`: Celery worker dedicated to 3-tier bank matching (`reconcile_queue`).
8. `b00k5_worker_sync`: Celery worker dedicated to offsite backups and GDrive sync (`gdrive_queue`).
9. `b00k5_bridge_mock`: Hardware USB DSC PKCS#11 mock daemon for headless CI (Port 28045).

---

## 2. Environment Configuration Reference

The platform is configured via the root `.env` file. **Never commit `.env` into version control.**

| Environment Variable | Default / Example | Purpose & Security Recommendations |
| :--- | :--- | :--- |
| `POSTGRES_DB` | `b00k5_db` | Primary PostgreSQL database name. |
| `POSTGRES_USER` | `b00k5_admin` | Database administrative username. |
| `POSTGRES_PASSWORD` | *(Generated 32-char hex)* | Strong database password. |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Asynchronous connection string used by FastAPI core. |
| `SYNC_DATABASE_URL` | `postgresql://...` | Synchronous connection string used by migrations and seeders. |
| `REDIS_URL` | `redis://b00k5_redis:6379/0`| Redis broker URL for task queues and login rate limiting. |
| `MINIO_ROOT_USER` | `minio_storage_admin` | Administrative root user for MinIO S3 storage. |
| `MINIO_ROOT_PASSWORD` | *(Generated 40-char hex)* | Administrative secret key for MinIO. |
| `MINIO_ENDPOINT` | `http://b00k5_minio:9000` | Internal network endpoint for MinIO API. |
| `MINIO_BUCKET_VAULT` | `b00k5-vault` | S3 bucket for corporate constitutional documents. |
| `MINIO_BUCKET_RECEIPTS` | `b00k5-receipts` | S3 bucket for scanned expense receipts and vendor bills. |
| `MINIO_BUCKET_STATEMENTS` | `b00k5-statements`| S3 bucket for raw bank statements (PDF, CSV). |
| `MINIO_BUCKET_SIGNED` | `b00k5-signed` | S3 bucket for cryptographically sealed PDF minutes. |
| `MINIO_BUCKET_STATUTORY` | `b00k5-statutory` | S3 bucket for filed statutory returns (MGT-7, AOC-4, ITR-6). |
| `SECRET_KEY` | *(Generated 64-char hex)* | Symmetric HMAC key for signing and verifying JWT tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `1440` (24 Hours) | JWT session expiration interval in minutes. |
| `RATE_LIMIT_LOGIN_MAX` | `5` | Maximum login attempts per minute before HTTP 429 lockout. |
| `DSC_BRIDGE_URL` | `http://b00k5_bridge_mock:28045` | Docker network URI to hardware bridge mock service. |
| `NEXT_PUBLIC_BRIDGE_URL` | `http://127.0.0.1:28045` | Browser loopback URI connecting to director's USB token. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Browser public URL for FastAPI backend endpoints. |

---

## 3. Role-Based Access Control (RBAC) Permission Matrix

b00k5 implements 5 distinct security personas enforced via the `/iam` router and API security dependencies:

| Administrative & Financial Action | `owner` (Founder) | `admin` (Operations) | `accountant` (Bookkeeper) | `auditor_ca` (Chartered Accountant) | `viewer` (Investor / Board) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Manage Company Profile & CIN** | ✓ | ✓ | — | — | Read Only |
| **Invite & Manage Users (IAM)** | ✓ | ✓ | — | — | — |
| **Issue GST Tax Invoices** | ✓ | ✓ | ✓ | — | Read Only |
| **Upload Bills & Approve Expenses** | ✓ | ✓ | ✓ | — | Read Only |
| **Import & Reconcile Bank Statements** | ✓ | ✓ | ✓ | Read Only | Read Only |
| **Post Manual Journal Entries** | ✓ | ✓ | ✓ | ✓ (Audit Adjustments) | — |
| **Freeze / Close Financial Year** | ✓ | — | — | ✓ (Joint Approval) | — |
| **Execute Hardware USB DSC Signatures**| ✓ (Director Token) | — | — | — | — |
| **Calibrate Statutory Anchors** | ✓ | — | — | ✓ | Read Only |
| **Export Schedule III Auditor Dossier**| ✓ | ✓ | ✓ | ✓ | ✓ |
| **Trigger SRE Disaster Recovery Drills** | ✓ | ✓ | — | — | — |

---

## 4. Companies Act Section 128 Retention & Archiving

Under Section 128 of the Companies Act, 2013, Indian companies must preserve all books of account, vouchers, and statutory papers for at least **8 financial years**.

### 4.1 Soft Archiving vs. Tenant Deletion
* **Hard Deletion Blocked:** All core foreign keys (`journal_entries`, `invoices`, `expenses`, `document_vault`, `statutory_filing_anchors`) enforce `ON DELETE RESTRICT`. Calling `DELETE FROM tenants WHERE id = ...` on a tenant with existing financial records will raise a database constraint error.
* **Archiving Procedure:** To decommission a tenant while preserving legal compliance:
  ```bash
  # Soft-archive tenant via API or SQL
  docker exec b00k5_postgres psql -U b00k5_admin -d b00k5_db -c \
    "UPDATE tenants SET is_archived = TRUE, archived_at = NOW() WHERE id = '<TENANT_UUID>';"
  ```
* Archived tenants are barred from issuing new invoices or vouchers, while historical records remain read-only for auditors and tax authorities.

---

## 5. Automated Backup & Disaster Recovery (DR) Operations

### 5.1 Manual SRE Disaster Recovery Drill
To test business continuity and verify that your backup snapshots can be restored within the Recovery Time Objective SLA ($< 30\text{ seconds}$) with zero ledger drift:

```bash
docker exec b00k5_api python /app/scripts/dr_drill.py
```

*Expected Verification Output:*
```
================================================================================
  b00k5 SRE AUTOMATED DISASTER RECOVERY DRILL
================================================================================
[*] Target Database: b00k5_db
[*] RTO SLA Threshold: < 30.00 seconds
[*] Drift SLA Tolerance: Exact Parity (₹0.00)

[GATE 1/6] Validating Production Source Database...           [PASSED] (Balance: ₹74,694,900.38)
[GATE 2/6] Generating AES-256 Encrypted Database Dump...     [PASSED] (Dump: 842.1 KB)
[GATE 3/6] Provisioning Isolated Staging Sandbox...          [PASSED] (Container ready)
[GATE 4/6] Decrypting & Restoring Schema Payload...          [PASSED] (25 tables restored)
[GATE 5/6] Performing General Ledger Zero-Drift Audit...     [PASSED] (Restored: ₹74,694,900.38, Drift: ₹0.00)
[GATE 6/6] Evaluating Recovery Time Objective (RTO) SLA...   [PASSED] (0.58s elapsed, SLA: <30.00s)

>>> SRE DISASTER RECOVERY DRILL COMPLETED: 6/6 GATES PASSED <<<
```

### 5.2 Creating an Encrypted Manual Backup
```bash
docker exec b00k5_postgres pg_dump -U b00k5_admin -Fc b00k5_db > b00k5_manual_backup.dump
openssl enc -aes-256-gcm -salt -in b00k5_manual_backup.dump -out b00k5_manual_backup.dump.enc
```

### 5.3 Restoring from an Encrypted Backup
```bash
# 1. Decrypt dump
openssl enc -d -aes-256-gcm -in b00k5_manual_backup.dump.enc -out b00k5_restore.dump

# 2. Restore into PostgreSQL
docker exec -i b00k5_postgres pg_restore -U b00k5_admin -d b00k5_db --clean --if-exists < b00k5_restore.dump
```

---

## 6. SRE Health Checks & Telemetry

Check the health of all platform services using standard curl commands:

```bash
# 1. FastAPI Core Health Check
curl -s http://localhost:8000/api/v1/system/health | jq .

# 2. Redis Connection Pool Telemetry
docker exec b00k5_redis redis-cli info clients

# 3. MinIO Sovereign Storage Health
curl -s http://localhost:9000/minio/health/live

# 4. Celery Worker Queue Inspection
docker exec b00k5_worker_ocr celery -A app.core.celery_app inspect active
```
