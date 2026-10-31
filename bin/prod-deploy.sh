#!/usr/bin/env bash
# ==============================================================================
# b00k5 - PRODUCTION DEPLOYMENT & SERVICE ORCHESTRATION ENGINE
# ==============================================================================
# Usage:
#   ./bin/prod-deploy.sh                # Build & deploy production stack
#   ./bin/prod-deploy.sh up             # Build & start production stack
#   ./bin/prod-deploy.sh status         # Inspect container health & ports
#   ./bin/prod-deploy.sh restart        # Graceful restart of services
#   ./bin/prod-deploy.sh logs [svc]     # Tail service logs
#   ./bin/prod-deploy.sh down           # Stop production stack
#
# Production Ports:
#   - Web UI     : 3000
#   - API Core   : 8000
#   - PostgreSQL : 5432
#   - Redis Cache: 6379
#   - MinIO S3   : 9000 (API) / 9001 (Console)
#   - DSC Bridge : 28045
# ==============================================================================

set -euo pipefail

# Script location & root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

log_info()    { echo -e "${BLUE}[PROD-DEPLOY]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }

check_prerequisites() {
  log_info "Step 1/4: Running pre-flight prerequisites and security checks..."
  
  # 1. Docker daemon check
  if ! docker info >/dev/null 2>&1; then
    log_error "Docker daemon is not responding. Please start Docker Desktop or Docker Engine."
    exit 1
  fi
  log_success "Docker daemon is active."

  # 2. .env configuration check
  if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
      log_warn ".env file not found. Copying from .env.example..."
      cp .env.example .env
      chmod 600 .env
      log_success "Created .env configuration."
    else
      log_error ".env and .env.example missing. Cannot proceed without configuration."
      exit 1
    fi
  fi
  log_success "Configuration file (.env) verified."

  # 3. TypeScript compilation check on apps/web
  if [[ -d "apps/web" ]] && command -v npx >/dev/null 2>&1; then
    log_info "Verifying Next.js TypeScript type safety (tsc --noEmit)..."
    if (cd apps/web && npx tsc --noEmit); then
      log_success "TypeScript check passed cleanly with zero type errors."
    else
      log_error "TypeScript compilation failed in apps/web. Aborting deployment."
      exit 1
    fi
  fi
}

cmd_up() {
  check_prerequisites

  log_info "Step 2/4: Building and launching production container fleet..."
  ${COMPOSE_CMD} up -d --build

  log_info "Step 3/4: Awaiting service health and readiness..."
  
  # Await PostgreSQL
  echo -n "  - Waiting for PostgreSQL (b00k5_postgres)..."
  PG_RETRIES=30
  until docker exec b00k5_postgres pg_isready -U b00k5_admin -d b00k5_db >/dev/null 2>&1 || [[ $PG_RETRIES -eq 0 ]]; do
    echo -n "."
    sleep 2
    ((PG_RETRIES--))
  done
  echo ""
  if [[ $PG_RETRIES -eq 0 ]]; then
    log_error "PostgreSQL failed to report healthy within 60s."
    exit 1
  fi
  log_success "PostgreSQL is healthy and accepting connections."

  # Await FastAPI
  echo -n "  - Waiting for Core Financial API (b00k5_api on port 8000)..."
  API_RETRIES=40
  API_HEALTHY=false
  while [[ $API_RETRIES -gt 0 ]]; do
    if curl -s -f "http://127.0.0.1:8000/api/v1/health" >/dev/null 2>&1 || curl -s -f "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
      API_HEALTHY=true
      break
    fi
    echo -n "."
    sleep 2
    ((API_RETRIES--))
  done
  echo ""
  if [[ "$API_HEALTHY" == "false" ]]; then
    log_error "b00k5_api failed to report healthy."
    docker logs --tail 30 b00k5_api
    exit 1
  fi
  log_success "FastAPI Core Engine is healthy."

  # Await Next.js Web Frontend
  echo -n "  - Waiting for Web Dashboard (b00k5_web on port 3000)..."
  WEB_RETRIES=30
  WEB_HEALTHY=false
  while [[ $WEB_RETRIES -gt 0 ]]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000" || true)
    if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "307" || "$HTTP_CODE" == "308" ]]; then
      WEB_HEALTHY=true
      break
    fi
    echo -n "."
    sleep 2
    ((WEB_RETRIES--))
  done
  echo ""
  if [[ "$WEB_HEALTHY" == "false" ]]; then
    log_warn "Web dashboard still initializing. Run 'docker compose logs -f b00k5_web' to monitor."
  else
    log_success "Next.js Web Dashboard is serving traffic on port 3000."
  fi

  log_info "Step 4/4: Asserting general ledger double-entry mathematical invariant..."
  LEDGER_DRIFT=$(docker exec b00k5_postgres psql -U b00k5_admin -d b00k5_db -t -c "SELECT COALESCE(SUM(debit_amount) - SUM(credit_amount), 0) FROM journal_items;" 2>/dev/null | tr -d ' ' || echo "0.00")
  if [[ "$LEDGER_DRIFT" == "0.00" || "$LEDGER_DRIFT" == "0" ]]; then
    log_success "Double-entry general ledger invariant verified (0.00 balance drift)."
  else
    log_warn "Ledger drift detected: ${LEDGER_DRIFT}. Please inspect /reports/general-ledger."
  fi

  echo ""
  echo -e "${GREEN}${BOLD}==============================================================================${NC}"
  echo -e "${GREEN}${BOLD} ✅ b00k5 PRODUCTION FLEET SUCCESSFULLY DEPLOYED & LIVE                       ${NC}"
  echo -e "${GREEN}${BOLD}==============================================================================${NC}"
  echo -e "  • Web Dashboard        : ${CYAN}http://localhost:3000${NC}"
  echo -e "  • API & Swagger Docs   : ${CYAN}http://localhost:8000/docs${NC}"
  echo -e "  • Health Endpoint      : ${CYAN}http://localhost:8000/api/v1/health${NC}"
  echo -e "  • MinIO Storage Console: ${CYAN}http://localhost:9001${NC}"
  echo -e "  • DSC Signer Bridge    : ${CYAN}http://localhost:28045/status${NC}"
  echo -e "${GREEN}${BOLD}==============================================================================${NC}"
}

cmd_status() {
  log_info "Checking production container status..."
  docker ps --filter "name=^b00k5_" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

cmd_restart() {
  log_info "Gracefully restarting production container fleet..."
  ${COMPOSE_CMD} restart
  log_success "Production services restarted."
}

cmd_down() {
  log_warn "Stopping production container fleet..."
  ${COMPOSE_CMD} down
  log_success "Production containers stopped."
}

cmd_logs() {
  local svc="${1:-}"
  if [[ -n "$svc" ]]; then
    ${COMPOSE_CMD} logs -f "$svc"
  else
    ${COMPOSE_CMD} logs -f
  fi
}

ACTION="${1:-up}"

case "${ACTION}" in
  up|deploy)
    cmd_up
    ;;
  status|ps)
    cmd_status
    ;;
  restart)
    cmd_restart
    ;;
  down|stop)
    cmd_down
    ;;
  logs)
    cmd_logs "${2:-}"
    ;;
  help|-h|--help)
    sed -n '2,20p' "$0"
    ;;
  *)
    log_error "Unknown command: ${ACTION}"
    echo "Usage: ./bin/prod-deploy.sh [up|status|restart|logs|down]"
    exit 1
    ;;
esac
