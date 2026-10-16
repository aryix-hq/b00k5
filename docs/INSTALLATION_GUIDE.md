# b00k5 — Universal Installation & Deployment Guide
### Sovereign, Local-First Indian Financial ERP & MCA Statutory Compliance Platform

---

## 1. System Requirements & Hardware Sizing

b00k5 is architected to run completely self-hosted without any external vendor telemetry or third-party cloud lock-in. All financial records, bills, bank statements, and DSC cryptographic audit signatures reside strictly on your local machine or private cloud server.

### 1.1 Hardware Specifications Matrix

| Specification | Minimum (Development / Small Entity) | Recommended (Production / Multi-Company CA Practice) |
| :--- | :--- | :--- |
| **Processor (CPU)** | 2 CPU Cores (x86_64 or ARM64) | 4+ CPU Cores (e.g. AMD EPYC, Intel Xeon, Apple M-Series) |
| **Memory (RAM)** | **4 GB RAM** (with 2 GB swap) | **8 GB – 16 GB RAM** (Enables high-throughput concurrent OCR parsing) |
| **Storage (Disk)** | **20 GB** available SSD storage | **50 GB – 200 GB** High-IOPS NVMe SSD |
| **Operating System** | Linux (Ubuntu/Debian/RHEL), macOS 13+, Windows 10/11 (WSL2) | Ubuntu 22.04/24.04 LTS, Debian 12, or Rocky Linux 9 |
| **Docker Engine** | Docker 24.0+ & Docker Compose v2.20+ | Docker Engine 26.0+ & Docker Compose v2.27+ |

### 1.2 Network & Port Allocation Table

Ensure the following default host ports are available or allowed through your firewall:

| Port | Service | Container | Purpose | Access Perimeter |
| :--- | :--- | :--- | :--- | :--- |
| **`3000`** | Next.js 15 Web UI | `b00k5_web` | Modern Web Frontend Portal | Public or Internal LAN |
| **`8000`** | FastAPI Backend | `b00k5_api` | Core Accounting & Compliance REST API | Reverse Proxy / Internal |
| **`5432`** | PostgreSQL 16 | `b00k5_postgres` | Relational Financial Ledger & RLS Vault | Bound to `127.0.0.1` |
| **`6379`** | Redis 7 | `b00k5_redis` | Cache & Celery Background Queue | Bound to `127.0.0.1` |
| **`9000`** | MinIO S3 API | `b00k5_minio` | Content-Addressed Sovereign Storage | Bound to `127.0.0.1` |
| **`9001`** | MinIO Web Console | `b00k5_minio` | S3 Storage Administrative UI | Bound to `127.0.0.1` |
| **`28045`**| DSC Hardware Bridge | `b00k5_bridge_mock` | PKCS#11 USB Token Daemon Bridge | Bound to `127.0.0.1` |

---

## 2. Quick One-Line Automated Installation

### 2.1 Linux, macOS & Cloud VPS (Bash / Curl)
Open your terminal and run:
```bash
curl -fsSL https://raw.githubusercontent.com/aryix-hq/b00k5/main/scripts/install.sh | bash
```
> **What this script does automatically:**
> 1. Probes your OS architecture, CPU, RAM, and disk space.
> 2. Verifies Docker daemon connectivity and Compose v2.
> 3. Checks for host port conflicts (3000, 8000, 5432, 6379, 9000, 9001).
> 4. Clones the repository into `./b00k5` (if not already inside the repo).
> 5. Generates cryptographically secure, high-entropy secrets for PostgreSQL, MinIO, and JWT in `.env`.
> 6. Builds and boots the 9-container fleet in detached mode (`docker compose up -d --build`).
> 7. Polls backend and frontend health checks until operational.
> 8. Executes initial chart of accounts seeding and displays access URLs.

### 2.2 Windows 10 & 11 (PowerShell)
Open **PowerShell as Administrator** or standard user and execute:
```powershell
irm https://raw.githubusercontent.com/aryix-hq/b00k5/main/scripts/install.ps1 | iex
```
*(Requires Docker Desktop with WSL2 backend active).*

---

## 3. Platform-Specific Manual Installation Instructions

---

### 3.1 macOS (Apple Silicon M1/M2/M3/M4 & Intel x86_64)

#### Prerequisites
1. Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/).
   - Ensure **Use Virtualization framework** and **Use Rosetta for x86/amd64 emulation** are checked in Settings -> General.
   - Allocate at least **4 GB RAM** (8 GB recommended) in Docker Desktop -> Settings -> Resources.
2. Install Git (if not already installed via Xcode Command Line Tools):
   ```bash
   xcode-select --install
   ```

#### Step-by-Step Execution
```bash
# 1. Clone the repository
git clone https://github.com/aryix-hq/b00k5.git
cd b00k5

# 2. Configure Environment Passphrases
cp .env.example .env
chmod 600 .env

# Generate high-entropy secrets
DB_PASS=$(openssl rand -hex 24)
MINIO_PASS=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)$(openssl rand -hex 32)

sed -i '' "s/b00k5_secure_vault_password_2026/$DB_PASS/g" .env
sed -i '' "s/minio_storage_secret_key_2026/$MINIO_PASS/g" .env
sed -i '' "s/b00k5_default_dev_jwt_secret_key_change_in_prod_2026/$JWT_SECRET/g" .env

# 3. Launch the Sovereign Fleet
docker compose up -d --build

# 4. Verify Container Health
docker compose ps

# 5. Initialize Seed Data (Chart of Accounts & Demo Companies)
docker exec b00k5_api python /app/seed_data.py
```

Access the Web Portal at: `http://localhost:3000`

---

### 3.2 Linux (Ubuntu 22.04 / 24.04 LTS & Debian 12)

#### Prerequisites
```bash
# Update repositories and install core utilities
sudo apt update && sudo apt install -y curl git ufw ca-certificates gnupg

# Install official Docker Engine & Docker Compose Plugin
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable Docker and add current user to docker group
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

#### Step-by-Step Execution
```bash
# 1. Clone to destination directory
git clone https://github.com/aryix-hq/b00k5.git /opt/b00k5
cd /opt/b00k5

# 2. Configure .env with Production Secrets
cp .env.example .env
chmod 600 .env

DB_PASS=$(openssl rand -hex 24)
MINIO_PASS=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)$(openssl rand -hex 32)

sed -i "s/b00k5_secure_vault_password_2026/$DB_PASS/g" .env
sed -i "s/minio_storage_secret_key_2026/$MINIO_PASS/g" .env
sed -i "s/b00k5_default_dev_jwt_secret_key_change_in_prod_2026/$JWT_SECRET/g" .env

# 3. Boot Application Stack
docker compose up -d --build

# 4. Seed Database
docker exec b00k5_api python /app/seed_data.py
```

---

### 3.3 Windows 10 & 11 (WSL2 / Docker Desktop)

#### Prerequisites
1. Ensure **WSL 2** is enabled:
   ```powershell
   wsl --install
   ```
2. Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
3. In Docker Desktop Settings:
   - Go to **General** -> check **Use the WSL 2 based engine**.
   - Go to **Resources** -> **WSL Integration** -> enable integration with your default distro (e.g. Ubuntu).

#### Execution via PowerShell
```powershell
# 1. Clone repository
git clone https://github.com/aryix-hq/b00k5.git
cd b00k5

# 2. Run PowerShell installer
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Or execute directly inside your **WSL2 Ubuntu terminal** using the Linux instructions above for maximum performance.

---

### 3.4 Cloud VPS Deployment (Hetzner, AWS EC2, DigitalOcean, Linode)

For hosting b00k5 on a remote public cloud virtual machine with TLS (HTTPS) termination:

#### 1. Recommended Cloud VPS Spec:
- **Provider Recommendation:** Hetzner Cloud CPX21/CPX31 (Europe) or AWS EC2 `t4g.xlarge` / `c7g.large` (Mumbai `ap-south-1`).
- **OS:** Ubuntu 22.04 LTS.

#### 2. Firewall Security Configuration (UFW)
Only expose ports `80` (HTTP), `443` (HTTPS), and `22` (SSH). Never expose internal ports (`5432`, `6379`, `9000`) to the public internet:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

#### 3. Reverse Proxy & Automated SSL (Caddy 2)
Caddy automatically provisions and renews Let's Encrypt certificates with zero configuration.

Install Caddy:
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

Create `/etc/caddy/Caddyfile`:
```caddy
# Frontend UI
app.yourcompany.in {
    reverse_proxy localhost:3000
}

# Backend REST API & Swagger Docs
api.yourcompany.in {
    reverse_proxy localhost:8000
}

# MinIO Storage S3 API
s3.yourcompany.in {
    reverse_proxy localhost:9000
}
```

Reload Caddy:
```bash
sudo systemctl reload caddy
```

In your `.env` file on the server, update the public endpoints:
```ini
NEXT_PUBLIC_API_URL=https://api.yourcompany.in
NEXT_PUBLIC_BRIDGE_URL=http://127.0.0.1:28045
```
Rebuild the web container:
```bash
docker compose build b00k5_web && docker compose up -d b00k5_web
```

---

## 4. Default Credentials & Initial Login

Once deployed, sign in to the portal at `http://localhost:3000` (or your domain):

| Role | Username / Email | Password | Scope & Responsibilities |
| :--- | :--- | :--- | :--- |
| **Founder / Entity Owner** | `founder@vortexai.com` | `admin123` | Full access to books, billing, banking, and governance. |
| **Forensic CA / Auditor** | `ca.auditor@vortexai.com` | `admin123` | Audit trail verification, period closing, Form 26Q, Schedule III. |
| **Company Secretary (CS)**| `cs.secretary@vortexai.com` | `admin123` | Board minutes, statutory registers (MGT-1, MBP-1, DIR-8). |
| **Platform Superadmin** | `admin@b00k5.local` | `admin123` | Multi-tenant tenant management and system infrastructure telemetry. |

> [!IMPORTANT]
> Change the default passwords immediately after initial onboarding in **Settings -> Security & Team**.

---

## 5. Operations, Backups & Disaster Recovery

### 5.1 Real-Time Container Monitoring
```bash
# View live logs across all containers
docker compose logs -f

# Inspect specific service logs
docker compose logs -f b00k5_api
docker compose logs -f b00k5_worker_ocr

# Check resource usage (CPU/RAM)
docker stats
```

### 5.2 Automated Disaster Recovery & Ledger Drift Drill
Run the built-in SRE integrity check to verify zero-drift on your ledger:
```bash
docker exec b00k5_api python /app/scripts/dr_drill.py
```
This drill:
1. Performs an encrypted AES-256-GCM database snapshot.
2. Validates SHA-256 integrity.
3. Tests PostgreSQL 16 relational integrity.
4. Verifies the fundamental ledger equation:
   $$\left\vert{}\sum \text{Debits} - \sum \text{Credits}\right\vert{} \equiv \text{₹0.00}$$
5. Verifies PostgreSQL Row-Level Security (RLS) enforcement.
6. Emits a verifiable audit artifact (`DR_DRILL_REPORT.json`).

### 5.3 Automated Database Backups (Cron)
Add a daily encrypted backup job:
```bash
crontab -e
```
Add the following line (runs daily at 02:00 AM IST):
```cron
0 2 * * * cd /opt/b00k5 && docker compose exec -T b00k5_postgres pg_dump -U b00k5_admin b00k5_db | gzip > /opt/backups/b00k5_backup_$(date +\%Y\%m\%d).sql.gz
```

---

## 6. Common Troubleshooting & FAQs

### Q1: `permission denied while trying to connect to the Docker daemon socket`
**Solution:** Your user does not have permission to access `/var/run/docker.sock`.
Run:
```bash
sudo usermod -aG docker $USER
newgrp docker
```
Or on macOS/Windows, ensure Docker Desktop application is launched and running.

### Q2: Port 3000 or Port 8000 is already in use
**Solution:** Change host ports in `docker-compose.yml`:
```yaml
ports:
  - "3001:3000"  # Web UI accessible on http://localhost:3001
  - "8001:8000"  # API accessible on http://localhost:8001
```

### Q3: How to reset the database to clean demo state?
```bash
docker compose down -v
docker compose up -d
docker exec b00k5_api python /app/seed_data.py
```
*(Warning: `-v` removes all database and MinIO persistent volumes).*

---
**Maintained by the b00k5 Open-Source Community.**
For statutory questions or bug reports, submit an issue on GitHub.

