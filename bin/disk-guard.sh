#!/usr/bin/env bash
# ==============================================================================
# b00k5 - DOCKER DISK CAPACITY & DATABASE RECOVERY GUARD ENGINE
# ==============================================================================
# Usage:
#   ./bin/disk-guard.sh              # Check disk capacity & database recovery status
#   ./bin/disk-guard.sh status       # Detailed telemetry of Docker disk, cache, and DB
#   ./bin/disk-guard.sh prune        # Reclaim BuildKit cache and dangling image layers
#   ./bin/disk-guard.sh fix-recovery # Diagnose and release PostgreSQL from ENOSPC recovery loops
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

log_info()    { echo -e "${BLUE}[DISK-GUARD]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }

check_docker() {
  if ! docker info >/dev/null 2>&1; then
    log_error "Docker daemon is not responding. Please start Docker Desktop or Docker Engine."
    exit 1
  fi
}

get_docker_disk_usage() {
  # Inspect Docker VM overlay filesystem using a lightweight alpine probe
  local usage_line
  usage_line=$(docker run --rm alpine df -k / 2>/dev/null | awk 'NR==2 {print $2, $3, $4, $5}' || echo "0 0 0 0%")
  echo "${usage_line}"
}

cmd_status() {
  check_docker
  log_info "Inspecting Docker VM storage and database recovery telemetry..."
  echo ""

  # 1. Host storage
  echo -e "${BOLD}1. Host Machine Storage (macOS)${NC}"
  df -h / | awk 'NR==1 || NR==2'
  echo ""

  # 2. Docker VM Virtual Storage
  echo -e "${BOLD}2. Docker Desktop VM Virtual Storage (/dev/vda1)${NC}"
  local disk_info
  disk_info=$(get_docker_disk_usage)
  local total_kb used_kb avail_kb pct
  total_kb=$(echo "${disk_info}" | awk '{print $1}')
  used_kb=$(echo "${disk_info}" | awk '{print $2}')
  avail_kb=$(echo "${disk_info}" | awk '{print $3}')
  pct=$(echo "${disk_info}" | awk '{print $4}')

  local total_gb=$(( total_kb / 1024 / 1024 ))
  local used_gb=$(( used_kb / 1024 / 1024 ))
  local avail_gb=$(( avail_kb / 1024 / 1024 ))

  echo "  - Total Allocated : ${total_gb} GB"
  echo "  - Space Used      : ${used_gb} GB (${pct})"
  echo "  - Space Available : ${avail_gb} GB"

  if [[ "${avail_kb}" -lt 5242880 ]]; then
    log_warn "Docker virtual disk capacity is dangerously low (< 5GB free). PostgreSQL recovery operations risk ENOSPC crash loops."
  else
    log_success "Docker virtual disk has healthy operating headroom."
  fi
  echo ""

  # 3. Docker Component Space Breakdown
  echo -e "${BOLD}3. Docker Resource Footprint (system df)${NC}"
  docker system df
  echo ""

  # 4. PostgreSQL Health and Recovery State
  echo -e "${BOLD}4. PostgreSQL Recovery & Operational Status${NC}"
  local pg_container
  pg_container=$(docker ps -q --filter "name=^b00k5_postgres$" || true)
  if [[ -z "${pg_container}" ]]; then
    log_warn "Container 'b00k5_postgres' is not running."
  else
    local pg_status
    pg_status=$(docker inspect --format '{{.State.Status}} (Health: {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}})' b00k5_postgres)
    echo "  - Container State : ${pg_status}"

    local pg_recovery
    pg_recovery=$(docker exec b00k5_postgres psql -U b00k5_admin -d b00k5_db -tAc "SELECT pg_is_in_recovery();" 2>/dev/null || echo "unreachable")
    if [[ "${pg_recovery}" == "f" ]]; then
      log_success "PostgreSQL is active in NORMAL read/write mode (pg_is_in_recovery = false)."
    elif [[ "${pg_recovery}" == "t" ]]; then
      log_warn "PostgreSQL is currently in RECOVERY mode (read-only transactions only). If stuck, check logs for ENOSPC."
    else
      log_error "Could not query PostgreSQL (status: ${pg_recovery})."
    fi
  fi
}

cmd_prune() {
  check_docker
  log_info "Reclaiming Docker VM storage without touching database or MinIO data volumes..."

  # 1. Prune BuildKit cache (often 10GB-25GB)
  log_info "Pruning Docker BuildKit build cache..."
  docker builder prune -a -f

  # 2. Prune dangling image layers
  log_info "Pruning dangling container images..."
  docker image prune -f

  log_success "Docker storage cleanup completed."
  echo ""
  cmd_status
}

cmd_fix_recovery() {
  check_docker
  log_info "Diagnosing PostgreSQL recovery state and clearing potential ENOSPC blocks..."

  # Check disk headroom
  local disk_info
  disk_info=$(get_docker_disk_usage)
  local avail_kb
  avail_kb=$(echo "${disk_info}" | awk '{print $3}')

  if [[ "${avail_kb}" -lt 5242880 ]]; then
    log_warn "Low Docker disk space detected (${avail_kb} KB). Automatically executing aggressive build cache prune..."
    docker builder prune -a -f
    docker image prune -f
  fi

  # Check postgres logs for ENOSPC panics
  local has_enospc
  has_enospc=$(docker logs --tail 50 b00k5_postgres 2>&1 | grep -i "No space left on device" || true)
  if [[ -n "${has_enospc}" ]]; then
    log_warn "Found 'No space left on device' PANIC in recent PostgreSQL logs."
    log_info "Restarting b00k5_postgres with clean disk headroom to complete WAL checkpoint recovery..."
    docker restart b00k5_postgres
  fi

  # Await recovery completion
  log_info "Awaiting PostgreSQL recovery completion..."
  local retries=30
  local recovered=false
  while [[ ${retries} -gt 0 ]]; do
    local is_rec
    is_rec=$(docker exec b00k5_postgres psql -U b00k5_admin -d b00k5_db -tAc "SELECT pg_is_in_recovery();" 2>/dev/null || echo "t")
    if [[ "${is_rec}" == "f" ]]; then
      recovered=true
      break
    fi
    sleep 2
    ((retries--))
    echo -n "."
  done
  echo ""

  if [[ "${recovered}" == "true" ]]; then
    log_success "PostgreSQL is healthy and verified OUT of recovery mode (pg_is_in_recovery = false)!"
  else
    log_error "PostgreSQL did not exit recovery mode within 60s. Inspect 'docker logs b00k5_postgres'."
    exit 1
  fi
}

ACTION="${1:-status}"

case "${ACTION}" in
  status)
    cmd_status
    ;;
  prune)
    cmd_prune
    ;;
  fix-recovery)
    cmd_fix_recovery
    ;;
  *)
    echo "Usage: $0 {status|prune|fix-recovery}"
    exit 1
    ;;
esac
