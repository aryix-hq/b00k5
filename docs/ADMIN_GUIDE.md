# b00k5 Administrator & Operations Manual

## 1. System Requirements & Production Deployment

### 1.1 Minimum Hardware Specifications
* **CPU:** 2 vCPU cores (x86_64 or Apple Silicon ARM64)
* **RAM:** 4 GB minimum (8 GB recommended for simultaneous OCR processing and PDF rendering)
* **Disk:** 20 GB SSD storage for container images, PostgreSQL database, and MinIO object storage

### 1.2 Host Software Requirements
* **Operating System:** Linux (Ubuntu 22.04+, Debian 12+, RHEL 9+), macOS (13+ Ventura/Sonoma/Sequoia), or Windows 11 with WSL2
* **Container Engine:** Docker Engine v24.0+ or Docker Desktop
* **Compose:** Docker Compose v2.20+
* **Utilities:** `curl`, `bash`, `python3` (optional, for installer helpers)

### 1.3 Quickstart Installation
Execute the automated turnkey installer:
```bash
git clone https://github.com/your-org/b00k5.git
cd b00k5
./install.sh
```

---

## 2. Environment Variables & Secret Management

All configuration is driven by the root `.env` file. Never commit `.env` into version control.

| Environment Variable | Default / Example | Purpose & Security Recommendations |
| :--- | :--- | :--- |
| `POSTGRES_DB` | `b00k5_db` | Primary PostgreSQL database name. |
| `POSTGRES_USER` | `b00k5_admin` | Database administrative username. |
| `POSTGRES_PASSWORD` | *(Generated random 32-char hex)* | Cryptographically random database password. |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Asynchronous SQLAlchemy connection string used by FastAPI. |
| `SYNC_DATABASE_URL` | `postgresql://...` | Synchronous psycopg2 connection string used by migrations and seeders. |
| `REDIS_URL` | `redis://b00k5_redis:6379/0` | Redis broker URL for Celery task dispatch and caching. |
| `MINIO_ROOT_USER` | `minio_storage_admin` | Root administrative user for MinIO object store. |
| `MINIO_ROOT_PASSWORD` | *(Generated random 40-char hex)* | Root administrative secret key for MinIO. |
| `MINIO_ENDPOINT` | `http://b00k5_minio:9000` | Internal network URI for MinIO S3 API. |
| `MINIO_BUCKET_VAULT` | `b00k5-vault` | S3 bucket for corporate legal documents (COI, MOA, PAN). |
| `MINIO_BUCKET_RECEIPTS` | `b00k5-receipts` | S3 bucket for scanned expense receipts and vendor bills. |
| `MINIO_BUCKET_STATEMENTS` | `b00k5-statements` | S3 bucket for raw monthly bank statements (PDF, CSV). |
| `MINIO_BUCKET_SIGNED` | `b00k5-signed` | S3 bucket for cryptographically sealed PDF minutes. |
| `MINIO_BUCKET_STATUTORY` | `b00k5-statutory` | S3 bucket for MCA e-Forms and annual returns. |
| `SECRET_KEY` | *(Generated random 64-char hex)* | Symmetric HMAC key for signing and verifying JWT tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24 Hours) | JWT session validity duration in minutes. |
| `DSC_BRIDGE_URL` | `http://b00k5_bridge_mock:28045` | Docker network URI to hardware bridge mock service. |
| `NEXT_PUBLIC_BRIDGE_URL` | `http://127.0.0.1:28045` | Browser loopback URI connecting to director's USB token. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Public browser URI for FastAPI backend endpoints. |

---

## 3. Role-Based Access Control (RBAC) Permission Matrix

b00k5 implements five explicit security personas enforced via the `/iam` router and API dependencies:

| Action / Capability | `owner` (Founder) | `admin` (Operations) | `accountant` (Bookkeeper) | `auditor_ca` (Chartered Accountant) | `viewer` (Investor / Board) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Manage Company Profile & CIN** | ✓ | ✓ | — | — | Read Only |
| **Issue GST Tax Invoices** | ✓ | ✓ | ✓ | — | Read Only |
| **Approve Vendor Expenses** | ✓ | ✓ | — | — | — |
| **Settle Founder Reimbursements** | ✓ | ✓ | — | — | — |
| **Strike Off Expenses with Audit Reason** | ✓ | ✓ | ✓ | — | — |
| **Execute Bank Reconciliation** | ✓ | ✓ | ✓ | — | Read Only |
| **Sign Board Minutes via Hardware DSC** | ✓ | — | — | — | — |
| **Run Fiscal Year-End Close** | ✓ | ✓ | — | Review Only | Read Only |
| **View General Ledger & Trial Balance** | ✓ | ✓ | ✓ | ✓ | Read Only |
| **Export Statutory Auditor Pack** | ✓ | ✓ | ✓ | ✓ | — |
| **Manage Team Users & Roles (IAM)** | ✓ | ✓ | — | — | — |
| **Configure Google Drive Cloud Backups** | ✓ | ✓ | — | — | — |

---

## 4. Disaster Recovery & Google Drive Cloud Backup Runbook

### 4.1 Automated Database Dumps
The platform features an automated backup pipeline (`app/services/db_backup.py`) accessible via API or Celery beat:
```bash
# Trigger immediate database backup
curl -X POST http://localhost:8000/api/v1/system/backup-database \
  -H "Authorization: Bearer <ADMIN_JWT_TOKEN>"
```

* **Compression:** Backup files are piped through `gzip -9`.
* **Encryption:** AES-256 encrypted using the system `SECRET_KEY`.
* **Storage Destination:** Stored locally in `/tmp/b00k5_backups` and asynchronously mirrored to the company's designated Google Drive folder.

### 4.2 Disaster Recovery Restoration Runbook
To restore a snapshot into a new or repaired database container:

1. Locate the backup snapshot archive (e.g. `b00k5_backup_2026-10-03_120000.sql.gz`).
2. Copy the backup file into the running PostgreSQL container:
   ```bash
   docker cp b00k5_backup_2026-10-03_120000.sql.gz b00k5_postgres:/tmp/
   ```
3. Execute the restoration pipeline:
   ```bash
   docker exec -i b00k5_postgres bash -c "gunzip -c /tmp/b00k5_backup_2026-10-03_120000.sql.gz | psql -U b00k5_admin -d b00k5_db"
   ```
4. Verify data integrity and zero-drift ledger balance:
   ```bash
   docker exec b00k5_postgres psql -U b00k5_admin -d b00k5_db -c "SELECT COALESCE(SUM(debit_amount) - SUM(credit_amount), 0) FROM journal_items;"
   ```
   *Expected Result:* `0.00` net drift.

---

## 5. Hardware USB DSC Bridge Deployment on Director Workstations

To enable Class-3 DSC cryptographic signing for Board Minutes, the bridge daemon must run on the workstation where the physical USB token is plugged in:

### 5.1 macOS Setup
1. Install HyperPKI HYP2003 or ePass2003 driver software provided by Certifying Authority (eMudhra / VSign / Capricorn).
2. Verify token driver path exists: `/usr/local/lib/libespki.dylib` or `/Library/OpenSC/lib/opensc-pkcs11.so`.
3. Launch bridge daemon:
   ```bash
   cd bridge
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   bash run_bridge.sh
   ```
4. Confirm bridge health: `curl http://127.0.0.1:28045/status`.

### 5.2 Linux Setup (Ubuntu / Debian)
```bash
sudo apt-get update && sudo apt-get install -y pcscd pcsc-tools libpcsclite-dev opensc
sudo systemctl enable --now pcscd
cd bridge
pip install -r requirements.txt
bash run_bridge.sh
```

---

## 6. Service Supervision & Celery Worker Fleets

The asynchronous worker tier runs three dedicated Celery worker containers:
1. `b00k5_worker_ocr`: Consumes `ocr_queue` (concurrency: 2). Handles OCR ingestion, image thresholding, and regex parsing.
2. `b00k5_worker_reconcile`: Consumes `reconcile_queue` (concurrency: 2). Handles heavy bank statement reconciliation batches.
3. `b00k5_worker_sync`: Consumes `gdrive_queue` (concurrency: 2). Handles Google Drive cloud backups and file uploads.

To inspect live worker queue metrics:
```bash
docker exec b00k5_api celery -A app.core.celery_app inspect active
```
