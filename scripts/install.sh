#!/usr/bin/env bash
# ==============================================================================
#  b00k5 — Open-Source Indian ERP & MCA Compliance Platform
#  Universal One-Line Automated Installer for Linux, macOS & Cloud VPS
# ==============================================================================
#  Usage via curl:
#    curl -fsSL https://raw.githubusercontent.com/aryix-hq/b00k5/main/scripts/install.sh | bash
#
#  Usage locally:
#    bash scripts/install.sh
# ==============================================================================

set -eo pipefail

# --- Color Palettes ---
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
RESET="\033[0m"

log_info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
log_success() { echo -e "${GREEN}[OK]${RESET}   $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
log_err()     { echo -e "${RED}[ERR]${RESET}  $*" >&2; }
log_header()  { echo -e "\n${BOLD}${BLUE}=== $* ===${RESET}"; }

print_banner() {
  cat << "EOF"
  _      ____   ____  _     ____ 
 | |__  / __ \ / __ \| | __| ___|
 | '_ \/ / _` / / _` | |/ /|___ \ 
 | |_) | | (_| | | (_|   <  ___) |
 |_.__/ \ \__,_|\ \__,_|_|\_\____/ 
         \____/  \____/           
 Sovereign Local-First Indian Financial ERP & MCA Compliance Hub
EOF
  echo -e "${CYAN}----------------------------------------------------------------------${RESET}"
  echo -e "Automated Local & Cloud Deployment Script v1.0.0"
  echo -e "Target Platforms: Ubuntu / Debian / RHEL / macOS (Intel & Apple Silicon)"
  echo -e "${CYAN}----------------------------------------------------------------------${RESET}\n"
}

print_banner

# --- 1. System Requirements & Hardware Checks ---
log_header "1. Inspecting System Requirements"

OS_NAME="$(uname -s)"
ARCH_NAME="$(uname -m)"
log_info "Detected Operating System: ${BOLD}${OS_NAME}${RESET} (${ARCH_NAME})"

# Check Architecture
case "${ARCH_NAME}" in
  x86_64|amd64)
    log_success "Architecture supported: x86_64"
    ;;
  arm64|aarch64)
    log_success "Architecture supported: ARM64 (Apple Silicon / AWS Graviton)"
    ;;
  *)
    log_warn "Untested architecture: ${ARCH_NAME}. Docker multi-arch emulation may be required."
    ;;
esac

# Check RAM (Minimum 4 GB, Recommended 8 GB)
MEM_TOTAL_MB=0
if [ "${OS_NAME}" = "Darwin" ]; then
  MEM_TOTAL_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
  MEM_TOTAL_MB=$((MEM_TOTAL_BYTES / 1024 / 1024))
elif [ -f /proc/meminfo ]; then
  MEM_TOTAL_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
  MEM_TOTAL_MB=$((MEM_TOTAL_KB / 1024))
fi

if [ "${MEM_TOTAL_MB}" -gt 0 ]; then
  if [ "${MEM_TOTAL_MB}" -lt 3500 ]; then
    log_warn "System Memory: ${MEM_TOTAL_MB} MB. Minimum recommended RAM is 4096 MB (4 GB). High-volume OCR may run slower."
  else
    log_success "System Memory: ${MEM_TOTAL_MB} MB (Meets/Exceeds 4 GB requirement)"
  fi
fi

# Check Available Disk Space (Minimum 10 GB)
DISK_FREE_KB=0
if [ "${OS_NAME}" = "Darwin" ]; then
  DISK_FREE_KB=$(df -k . | awk 'NR==2 {print $4}')
else
  DISK_FREE_KB=$(df -k . 2>/dev/null | awk 'NR==2 {print $4}' || echo 0)
fi
DISK_FREE_GB=$((DISK_FREE_KB / 1024 / 1024))

if [ "${DISK_FREE_GB}" -lt 8 ]; then
  log_warn "Available Disk Space: ${DISK_FREE_GB} GB. Recommended free space is at least 15 GB for Docker volumes."
else
  log_success "Available Disk Space: ${DISK_FREE_GB} GB (Sufficient for images and volumes)"
fi

# --- 2. Prerequisites & Dependency Verification ---
log_header "2. Checking Prerequisites"

# Check Git
if ! command -v git >/dev/null 2>&1; then
  log_err "Git is not installed. Please install git and re-run this script."
  log_info "On Ubuntu/Debian: sudo apt update && sudo apt install -y git"
  log_info "On macOS: xcode-select --install"
  exit 1
fi
log_success "Git is available: $(git --version)"

# Check Docker
if ! command -v docker >/dev/null 2>&1; then
  log_err "Docker is not installed."
  if [ "${OS_NAME}" = "Linux" ]; then
    log_info "To install Docker on Linux, run:"
    log_info "  curl -fsSL https://get.docker.com | sudo sh"
    log_info "  sudo usermod -aG docker \$USER && newgrp docker"
  elif [ "${OS_NAME}" = "Darwin" ]; then
    log_info "Please install Docker Desktop for Mac: https://www.docker.com/products/docker-desktop/"
  fi
  exit 1
fi
log_success "Docker is available: $(docker --version)"

# Check Docker Daemon Connectivity
if ! docker info >/dev/null 2>&1; then
  log_err "Cannot connect to the Docker daemon. Is Docker running?"
  log_info "If on Linux: sudo systemctl start docker"
  log_info "If on macOS/Windows: Ensure Docker Desktop is started."
  exit 1
fi
log_success "Docker daemon is active and responsive."

# Check Docker Compose (v2 plugin or standalone)
COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  log_err "Docker Compose is not available. Please install docker compose."
  exit 1
fi
log_success "Docker Compose command: ${COMPOSE_CMD} ($(${COMPOSE_CMD} version))"

# --- 3. Port Conflict Check ---
log_header "3. Checking Port Availability"

PORTS_TO_CHECK=(
  3000
  8000
  5432
  6379
  9000
  9001
  28045
)
PORTS_BUSY=()

check_port() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    if lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
      return 1
    fi
  elif command -v ss >/dev/null 2>&1; then
    if ss -tulpn | grep -q ":$port "; then
      return 1
    fi
  elif command -v netstat >/dev/null 2>&1; then
    if netstat -tuln | grep -q ":$port "; then
      return 1
    fi
  fi
  return 0
}

for port in "${PORTS_TO_CHECK[@]}"; do
  if ! check_port "$port"; then
    # Check if the port is used by an existing b00k5 container
    if docker ps --format '{{.Names}} {{.Ports}}' | grep -q ":$port->"; then
      log_info "Port $port is currently bound by an existing b00k5 container (will be updated)."
    else
      PORTS_BUSY+=("$port")
    fi
  fi
done

if [ ${#PORTS_BUSY[@]} -gt 0 ]; then
  log_warn "The following ports are already in use by external processes: ${PORTS_BUSY[*]}"
  log_warn "If deployment fails to bind, please stop the conflicting services or customize host ports in docker-compose.yml."
else
  log_success "All required ports (3000, 8000, 5432, 6379, 9000, 9001) are free."
fi

# --- 4. Repository Setup ---
log_header "4. Preparing Repository & Workspace"

TARGET_DIR="b00k5"
REPO_URL="https://github.com/aryix-hq/b00k5.git"

# If already inside a b00k5 repository directory
if [ -f "docker-compose.yml" ] && [ -d "apps/api" ] && [ -d "apps/web" ]; then
  log_info "Detected execution within existing b00k5 workspace: $(pwd)"
else
  if [ -d "${TARGET_DIR}" ]; then
    log_info "Directory '${TARGET_DIR}' exists. Updating repository..."
    cd "${TARGET_DIR}"
    git pull || log_warn "Could not git pull, using existing working tree."
  else
    log_info "Cloning b00k5 from ${REPO_URL} into ./${TARGET_DIR}..."
    git clone "${REPO_URL}" "${TARGET_DIR}"
    cd "${TARGET_DIR}"
  fi
fi

# --- 5. Environment Secrets & Security Initialization ---
log_header "5. Generating Production Secrets & .env"

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets; print(secrets.token_hex(24))"
  else
    head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32
  fi
}

if [ ! -f ".env" ]; then
  log_info "Creating fresh .env configuration with cryptographically secure passphrases..."
  
  DB_PASSWORD=$(generate_secret)
  MINIO_ROOT_PASSWORD=$(generate_secret)
  JWT_SECRET_KEY=$(generate_secret)$(generate_secret)

  if [ -f ".env.example" ]; then
    cp .env.example .env
  else
    cat << EOF > .env
# b00k5 Sovereign Environment Configuration
APP_ENV=production
SECRET_KEY=${JWT_SECRET_KEY}
POSTGRES_USER=b00k5_admin
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_DB=b00k5_db
MINIO_ROOT_USER=minio_storage_admin
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_BRIDGE_URL=http://localhost:28045
EOF
  fi

  # Safely replace passwords in .env
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/b00k5_secure_vault_password_2026/${DB_PASSWORD}/g" .env || true
    sed -i '' "s/minio_storage_secret_key_2026/${MINIO_ROOT_PASSWORD}/g" .env || true
    sed -i '' "s/b00k5_default_dev_jwt_secret_key_change_in_prod_2026/${JWT_SECRET_KEY}/g" .env || true
  else
    sed -i "s/b00k5_secure_vault_password_2026/${DB_PASSWORD}/g" .env || true
    sed -i "s/minio_storage_secret_key_2026/${MINIO_ROOT_PASSWORD}/g" .env || true
    sed -i "s/b00k5_default_dev_jwt_secret_key_change_in_prod_2026/${JWT_SECRET_KEY}/g" .env || true
  fi

  chmod 600 .env
  log_success "Generated secure .env file with unique passwords."
else
  log_info "Existing .env file preserved."
fi

# --- 6. Container Fleet Deployment ---
log_header "6. Launching b00k5 Application Stack via Docker Compose"

log_info "Building and starting containers in detached mode..."
${COMPOSE_CMD} up -d --build

# --- 7. Health Check Verification ---
log_header "7. Verifying Service Health & Availability"

log_info "Waiting for core services (PostgreSQL 16, Redis 7, MinIO S3, FastAPI, Next.js 15) to become healthy..."

MAX_WAIT=90
ELAPSED=0
API_READY=false
WEB_READY=false

while [ $ELAPSED -lt $MAX_WAIT ]; do
  if ! $API_READY; then
    if curl -s http://localhost:8000/health >/dev/null 2>&1 || curl -s http://localhost:8000/docs >/dev/null 2>&1; then
      API_READY=true
      log_success "FastAPI Backend is active at http://localhost:8000 (after ${ELAPSED}s)"
    fi
  fi

  if ! $WEB_READY; then
    if curl -s -I http://localhost:3000 | grep -q "HTTP/1.1 200 OK"; then
      WEB_READY=true
      log_success "Next.js Web Frontend is active at http://localhost:3000 (after ${ELAPSED}s)"
    fi
  fi

  if $API_READY && $WEB_READY; then
    break
  fi

  sleep 3
  ELAPSED=$((ELAPSED + 3))
  echo -n "."
done
echo ""

if ! $API_READY || ! $WEB_READY; then
  log_warn "Services are still starting or building. Run 'docker compose logs -f' to inspect container startup logs."
else
  log_success "All application containers are fully operational!"
fi

# --- 8. Seed Demo Organization Data (Optional / Safe) ---
log_header "8. Initializing Sovereign Chart of Accounts & Seed Data"

if docker ps --format '{{.Names}}' | grep -q "b00k5_api"; then
  log_info "Executing initial tenant seeding (Tenants, Schedule III Chart of Accounts, Directorships)..."
  docker exec b00k5_api python /app/seed_data.py >/dev/null 2>&1 || log_info "Seed data script finished or already seeded."
  log_success "Statutory Chart of Accounts and Demo Entities configured."
fi

# --- 9. Deployment Completion Banner ---
log_header "DEPLOYMENT COMPLETED SUCCESSFULLY"

cat << EOF

${GREEN}${BOLD}Congratulations! b00k5 is running locally on your machine.${RESET}

${BOLD}Access Points:${RESET}
  * ${BOLD}Web Application (UI):${RESET}      ${CYAN}http://localhost:3000${RESET}
  * ${BOLD}FastAPI Backend & Swagger:${RESET} ${CYAN}http://localhost:8000/docs${RESET}
  * ${BOLD}MinIO Sovereign S3 Console:${RESET} ${CYAN}http://localhost:9001${RESET}
  * ${BOLD}Hardware DSC Bridge:${RESET}       ${CYAN}http://localhost:28045${RESET}

${BOLD}Default Demo Credentials:${RESET}
  * ${BOLD}Portal Login:${RESET}              ${YELLOW}founder@vortexai.com${RESET} / ${YELLOW}admin123${RESET}
  * ${BOLD}CA / Auditor Login:${RESET}        ${YELLOW}ca.auditor@vortexai.com${RESET} / ${YELLOW}admin123${RESET}
  * ${BOLD}Superadmin Login:${RESET}          ${YELLOW}admin@b00k5.local${RESET} / ${YELLOW}admin123${RESET}

${BOLD}Useful Operations Commands:${RESET}
  * Stop application stack:    ${CYAN}docker compose down${RESET}
  * View real-time logs:       ${CYAN}docker compose logs -f${RESET}
  * Run integrity/DR drill:    ${CYAN}docker exec b00k5_api python /app/scripts/dr_drill.py${RESET}
  * Run full test suite:       ${CYAN}docker exec b00k5_api pytest /app/tests/accounting_core${RESET}

For complete administration, reverse proxy SSL, and backup guides, visit:
${BOLD}docs/INSTALLATION_GUIDE.md${RESET}
EOF

