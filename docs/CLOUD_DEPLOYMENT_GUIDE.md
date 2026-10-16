# b00k5 Cloud & Enterprise Deployment Guide

This guide details the production deployment architectures for **b00k5** (`https://github.com/aryix-hq/b00k5/`), the sovereign Indian financial ERP and MCA compliance platform.

---

## 1. Architectural Deployment Models

b00k5 supports two primary production deployment paradigms depending on organizational scale, compliance mandates, and throughput requirements:

```mermaid
flowchart TD
    subgraph ModeA ["Mode A: Standalone Full-Stack (Single VPS / Edge)"]
        A_User([User / CA]) --> A_Proxy["Caddy / Nginx Reverse Proxy (TLS)"]
        A_Proxy --> A_Web["b00k5_web (Next.js 15)"]
        A_Proxy --> A_API["b00k5_api (FastAPI)"]
        A_API --> A_DB[("Local PostgreSQL 16 (RLS)")]
        A_API --> A_Redis[("Local Redis 7")]
        A_API --> A_MinIO[("Local MinIO S3")]
    end

    subgraph ModeB ["Mode B: Enterprise Scale (Stateless Fleet + Managed Cloud)"]
        B_User([User / CA / Auditors]) --> B_LB["Cloud Load Balancer (AWS ALB / Cloudflare)"]
        B_LB --> B_WebFleet["Stateless Next.js 15 Fleet (K8s / ECS)"]
        B_LB --> B_APIFleet["Stateless FastAPI Fleet (K8s / ECS)"]
        B_APIFleet --> B_Workers["Dedicated Celery OCR Workers"]
        
        B_APIFleet -->|"Connection Pooling"| B_RDS[("BYO Database: AWS Aurora PostgreSQL 16")]
        B_APIFleet --> B_ElastiCache[("BYO Cache: AWS ElastiCache / Redis 7")]
        B_APIFleet --> B_S3[("BYO Storage: AWS S3 / Cloudflare R2")]
        B_Workers --> B_ElastiCache
        B_Workers --> B_S3
    end
```

---

## 2. Mode A: Standalone Full-Stack Deployment (VPS / Bare-Metal)

Ideal for startups, single-company founders, LLPs, or boutique Chartered Accountant firms managing up to 20 corporate entities.

### 2.1 One-Command Automated Installation
Run the official deployment script directly from the repository:
```bash
curl -fsSL https://raw.githubusercontent.com/aryix-hq/b00k5/main/scripts/install.sh | bash
```
*(On Windows PowerShell, run: `irm https://raw.githubusercontent.com/aryix-hq/b00k5/main/scripts/install.ps1 | iex`)*

### 2.2 Manual Step-by-Step Setup
```bash
# 1. Clone repository
git clone https://github.com/aryix-hq/b00k5.git /opt/b00k5
cd /opt/b00k5

# 2. Configure Environment Secrets
cp .env.example .env
chmod 600 .env

# Generate cryptographically secure passwords
DB_PASS=$(openssl rand -hex 24)
MINIO_PASS=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)

sed -i "s/b00k5_secure_vault_password_2026/$DB_PASS/" .env
sed -i "s/minio_storage_secret_key_2026/$MINIO_PASS/" .env
sed -i "s/b00k5_default_dev_jwt_secret_key_change_in_prod_2026/$JWT_SECRET/" .env
sed -i "s|NEXT_PUBLIC_API_URL=http://localhost:8000|NEXT_PUBLIC_API_URL=https://api.yourdomain.com|" .env

# 3. Launch Docker Compose Stack
docker compose -f docker-compose.yml up -d --build

# 4. Verify Stack Health
docker compose ps
curl -f http://localhost:8000/api/v1/system/telemetry
```

---

## 3. Mode B: Enterprise Scale — Bring Your Own (BYO) Infrastructure

For multi-tenant CA networks, high-volume fintech platforms, or large enterprises requiring high availability (HA), horizontal auto-scaling, and multi-region disaster recovery.

In this mode, the container stack runs stateless application tiers (`b00k5_api`, `b00k5_web`, and Celery workers) pointing to managed cloud backends.

### 3.1 Bring Your Own Database (PostgreSQL 16)

#### Supported Managed Services:
* **AWS Aurora Serverless v2 PostgreSQL 16** (Recommended)
* **GCP Cloud SQL for PostgreSQL 16**
* **Azure Database for PostgreSQL Flexible Server**
* **Supabase / Neon Enterprise PostgreSQL**

#### Database Configuration Requirements:
1. **Row Level Security (RLS) Enablement:**
   All tables must enforce RLS. Ensure your database user has permission to set session variables:
   ```sql
   SET LOCAL app.current_tenant = '<tenant-uuid>';
   SET LOCAL app.current_user_role = 'owner';
   ```
2. **Schema Migration:**
   Apply the initialization script `init_schema.sql` to your managed database instance:
   ```bash
   psql -h <aurora-cluster-endpoint> -U b00k5_admin -d b00k5_db -f init_schema.sql
   ```
3. **Connection Pooling (PgBouncer):**
   For high-concurrency environments, deploy PgBouncer in `transaction` pooling mode:
   ```ini
   [databases]
   b00k5_db = host=aurora-endpoint port=5432 dbname=b00k5_db pool_size=50

   [pgbouncer]
   pool_mode = transaction
   max_client_conn = 1000
   default_pool_size = 30
   server_reset_query = DISCARD ALL
   ```
4. **Environment Variables (`.env`):**
   ```env
   DATABASE_URL=postgresql+asyncpg://b00k5_admin:<PASSWORD>@<AURORA_HOST>:5432/b00k5_db
   SYNC_DATABASE_URL=postgresql://b00k5_admin:<PASSWORD>@<AURORA_HOST>:5432/b00k5_db
   DB_POOL_SIZE=25
   DB_MAX_OVERFLOW=15
   ```

---

### 3.2 Bring Your Own Cache & Message Broker (Redis 7)

#### Supported Managed Services:
* **AWS ElastiCache for Redis** (Cluster or Multi-AZ Replication Group)
* **GCP Memorystore for Redis**
* **Upstash Serverless Redis**

#### Configuration Requirements:
* Enable **Transit Encryption (TLS)**.
* Enable **Redis AUTH token**.
* Eviction policy: `noeviction` or `volatile-lru` (to ensure Celery task queues are never dropped).

#### Environment Variables (`.env`):
```env
# AWS ElastiCache with in-transit encryption
REDIS_URL=rediss://:<AUTH_TOKEN>@<ELASTICACHE_PRIMARY_ENDPOINT>:6379/0
CELERY_BROKER_URL=rediss://:<AUTH_TOKEN>@<ELASTICACHE_PRIMARY_ENDPOINT>:6379/1
CELERY_RESULT_BACKEND=rediss://:<AUTH_TOKEN>@<ELASTICACHE_PRIMARY_ENDPOINT>:6379/2
```

---

### 3.3 Bring Your Own Object Storage (AWS S3 / Cloudflare R2 / GCS)

Instead of local MinIO, b00k5 natively interfaces with any S3-compliant object store for document locker security.

#### Required Buckets:
Provision the following 4 dedicated buckets in your cloud provider:
* `b00k5-vault`: Statutory legal documents (COI, MOA, AOA, Form AOC-4, MGT-7A, Board Minutes).
* `b00k5-receipts`: Purchase bills, expense receipts, and vendor invoices.
* `b00k5-statements`: Authentic bank statement PDFs, CSVs, and camt.053 payloads.
* `b00k5-backups`: Encrypted AES-256-GCM database checkpoints.

#### AWS S3 Least-Privilege IAM Policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload"
      ],
      "Resource": [
        "arn:aws:s3:::b00k5-vault/*",
        "arn:aws:s3:::b00k5-receipts/*",
        "arn:aws:s3:::b00k5-statements/*",
        "arn:aws:s3:::b00k5-backups/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::b00k5-vault",
        "arn:aws:s3:::b00k5-receipts",
        "arn:aws:s3:::b00k5-statements",
        "arn:aws:s3:::b00k5-backups"
      ]
    }
  ]
}
```

#### Environment Variables (`.env`):
```env
# AWS S3 Configuration
MINIO_ENDPOINT=s3.ap-south-1.amazonaws.com
MINIO_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
MINIO_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
MINIO_SECURE=true

MINIO_BUCKET_STATUTORY=b00k5-vault
MINIO_BUCKET_RECEIPTS=b00k5-receipts
MINIO_BUCKET_STATEMENTS=b00k5-statements
MINIO_BUCKET_BACKUPS=b00k5-backups

# Cloudflare R2 Configuration (Alternative)
# MINIO_ENDPOINT=<ACCOUNT_ID>.r2.cloudflarestorage.com
# MINIO_ACCESS_KEY=<R2_ACCESS_KEY_ID>
# MINIO_SECRET_KEY=<R2_SECRET_ACCESS_KEY>
# MINIO_SECURE=true
```

---

## 4. Kubernetes (K8s) & Container Orchestration

Deploy stateless FastAPI and Next.js replicas behind an Ingress Controller with Horizontal Pod Autoscaling (HPA).

### 4.1 Deployment Manifest (`k8s/b00k5-api.yaml`)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: b00k5-api
  namespace: b00k5
  labels:
    app: b00k5-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: b00k5-api
  template:
    metadata:
      labels:
        app: b00k5-api
    spec:
      containers:
        - name: api
          image: ghcr.io/aryix-hq/b00k5-api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: b00k5-production-secrets
          readinessProbe:
            httpGet:
              path: /api/v1/system/health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /api/v1/system/health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "2048Mi"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: b00k5-api-hpa
  namespace: b00k5
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: b00k5-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 75
```

---

## 5. Site Reliability Engineering (SRE) & Observability

### 5.1 Telemetry & Health Monitoring
b00k5 exposes a deep diagnostic telemetry endpoint at `GET /api/v1/system/telemetry`:
* **Ledger Zero-Sum Invariant:** Validates that $|\sum \text{Debits} - \sum \text{Credits}| \equiv 0.00$ continuously across all posted journal entries.
* **Database Connection Latency:** Real-time query ping to PostgreSQL.
* **Redis Connection Pool Health:** Validates broker liveness.
* **Object Store Connectivity:** Validates bucket read/write permissions.

### 5.2 Backup Checkpointing & Disaster Recovery (DR)
* **Local MinIO / S3 Checkpointing:**
  Create an immediate encrypted checkpoint via:
  ```bash
  curl -X POST https://api.yourdomain.com/api/v1/system/backup/checkpoint \
    -H "Authorization: Bearer <SUPER_ADMIN_TOKEN>"
  ```
* **Automated Daily Encrypted Backups:**
  The system schedules continuous AES-256-GCM snapshots with 30-day retention pruning.
* **7-Point Staging Integrity Gate:**
  Before restoring any database snapshot into production, b00k5 executes a 7-point integrity gate validating:
  1. SHA-256 checksum authenticity
  2. AES-256-GCM authenticated decryption
  3. RPO freshness (prevents accidental overwrite with stale snapshots)
  4. Document vault completeness
  5. Multi-point accounting zero-sum verification
  6. Cross-tenant foreign key integrity
  7. Atomic cutover with automatic rollback on failure

---

## 6. SRE Maintenance Runbook

| Operation | Command / Procedure |
| :--- | :--- |
| **Check Telemetry** | `curl -f http://localhost:8000/api/v1/system/telemetry` |
| **Create Checkpoint** | `POST /api/v1/system/backup/checkpoint` |
| **List Snapshots** | `GET /api/v1/system/backup/snapshots` |
| **Restore Snapshot** | `POST /api/v1/system/backup/restore` with payload `{"object_key": "checkpoints/..."}` |
| **View Audit Logs** | `GET /api/v1/system/backup-logs` |
| **Zero-Downtime Update**| `git pull origin main && docker compose up -d --build --no-deps api web` |

Repository Source: [https://github.com/aryix-hq/b00k5/](https://github.com/aryix-hq/b00k5/)

