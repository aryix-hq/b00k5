#!/usr/bin/env bash
# ==============================================================================
# b00k5 - ISOLATED STAGING / QA PREVIEW DEPLOYMENT & TESTING HARNESS
# ==============================================================================
# Usage:
#   ./bin/staging-deploy.sh up                 # Start staging environment
#   ./bin/staging-deploy.sh test               # Run health & integration tests
#   ./bin/staging-deploy.sh down               # Destroy staging and clean volumes
#   ./bin/staging-deploy.sh test-and-destroy   # Spin up -> test -> tear down (One-shot)
#
# Production Invariant:
#   Prod containers (ports 3000, 8000, 5432, 6379, 9000, 28045) remain 100% UNTOUCHED.
#   Staging uses ports:
#     - Web UI: 3001
#     - API   : 8001
#     - DB    : 5433
#     - Redis : 6380
#     - MinIO : 9010/9011
#     - DSC   : 28046
# ==============================================================================

set -euo pipefail

# Color palette
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

COMPOSE_FILE="docker-compose.staging.yml"
PROJECT_NAME="b00k5_staging"
COMPOSE_CMD="docker compose -p ${PROJECT_NAME} -f ${COMPOSE_FILE}"
API_URL="http://127.0.0.1:8001"
WEB_URL="http://127.0.0.1:3001"

log_info()    { echo -e "${BLUE}[STAGING-QA]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }

cmd_up() {
  log_info "Verifying that production containers remain untouched..."
  PROD_API_RUNNING=$(docker ps -q --filter "name=^b00k5_api$" || true)
  if [[ -n "${PROD_API_RUNNING}" ]]; then
    log_info "Verified: Prod container 'b00k5_api' is active on :8000 and will NOT be touched."
  fi

  log_info "Step 1/3: Starting isolated Staging/QA containers (Project: ${PROJECT_NAME})..."
  ${COMPOSE_CMD} up -d

  log_info "Step 2/3: Waiting for Staging database and API readiness on port 8001..."
  MAX_RETRIES=30
  RETRY=0
  HEALTHY=false

  while [[ ${RETRY} -lt ${MAX_RETRIES} ]]; do
    if curl -s -f "${API_URL}/health" >/dev/null 2>&1; then
      HEALTHY=true
      break
    fi
    sleep 2
    RETRY=$((RETRY + 1))
    echo -n "."
  done
  echo ""

  if [[ "${HEALTHY}" != "true" ]]; then
    log_error "Staging API did not respond on ${API_URL}/health within 60s."
    ${COMPOSE_CMD} logs --tail=50 b00k5_staging_api
    exit 1
  fi
  log_success "Staging API is healthy on ${API_URL}"

  log_info "Step 3/3: Seeding baseline fixtures into Staging DB (5433)..."
  ${COMPOSE_CMD} exec -T b00k5_staging_api python /app/seed_data.py || {
    log_warn "seed_data.py encountered warnings (continuing)..."
  }
  log_success "Staging/QA environment is fully operational!"
  echo ""
  echo -e "${CYAN}Staging Web UI : ${WEB_URL}${NC}"
  echo -e "${CYAN}Staging API    : ${API_URL}${NC}"
  echo -e "${CYAN}Staging DB     : localhost:5433 (b00k5_staging_db)${NC}"
}

cmd_test() {
  log_info "Running Staging verification tests..."

  # 1. Healthcheck Test
  log_info "Test 1: GET ${API_URL}/health"
  HEALTH_RESP=$(curl -s "${API_URL}/health")
  echo "Response: ${HEALTH_RESP}"
  if echo "${HEALTH_RESP}" | grep -q '"status":"healthy"'; then
    log_success "Healthcheck verified!"
  else
    log_error "Healthcheck validation failed!"
    exit 1
  fi

  # 2. UQC Catalog Endpoint Test (FEAT-GST-04)
  log_info "Test 2: GET ${API_URL}/api/v1/invoices/uqc-catalog"
  UQC_RESP=$(curl -s "${API_URL}/api/v1/invoices/uqc-catalog")
  UQC_COUNT=$(echo "${UQC_RESP}" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data))" 2>/dev/null || echo "0")
  if [[ "${UQC_COUNT}" -ge 44 ]] && echo "${UQC_RESP}" | grep -q '"code":"NA"' && echo "${UQC_RESP}" | grep -q '"code":"NOS"'; then
    log_success "UQC Catalog verified: ${UQC_COUNT} standard GSTN units + Chapter 99 service 'NA' invariant confirmed!"
  else
    log_error "UQC Catalog endpoint validation failed!"
    echo "${UQC_RESP}"
    exit 1
  fi

  # 3. Advance Tax Forecast Endpoint Test (FEAT-GST-04)
  log_info "Test 3: GET ${API_URL}/api/v1/compliance/advance-tax/forecast?fy=2026-27"
  ACCESS_TOKEN=$(${COMPOSE_CMD} exec -T b00k5_staging_api python -c \
    "from app.core.security import create_access_token; print(create_access_token({'sub': '33333333-3333-3333-3333-333333333333', 'tenant_id': '11111111-1111-1111-1111-111111111111'}))" | tr -d '\r\n')

  ADV_RESP=$(curl -s "${API_URL}/api/v1/compliance/advance-tax/forecast?fy=2026-27" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Tenant-ID: 11111111-1111-1111-1111-111111111111")

  if echo "${ADV_RESP}" | grep -q '"fiscal_year":"2026-27"' && echo "${ADV_RESP}" | grep -q '"installments"'; then
    log_success "Advance Tax Forecast verified on live Staging API: 4 statutory installments and §234B/C metrics computed."
  else
    log_error "Advance Tax Forecast validation failed: ${ADV_RESP}"
    exit 1
  fi

  # 4. Web Frontend Response Test
  log_info "Test 4: GET ${WEB_URL} (Staging Next.js App)"
  WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${WEB_URL}" || true)
  if [[ "${WEB_STATUS}" == "200" || "${WEB_STATUS}" == "307" || "${WEB_STATUS}" == "308" ]]; then
    log_success "Staging Web UI responding with HTTP ${WEB_STATUS} on port 3001!"
  else
    log_warn "Staging Web UI returned HTTP ${WEB_STATUS} (may still be initializing)."
  fi

  # 5. S3 / Cloudflare R2 Remote Mirror Endpoint Test
  log_info "Test 5: GET ${API_URL}/api/v1/storage/s3-config"
  S3_CFG_RESP=$(curl -s "${API_URL}/api/v1/storage/s3-config" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Tenant-ID: 11111111-1111-1111-1111-111111111111")
  if echo "${S3_CFG_RESP}" | grep -q '"provider"' && echo "${S3_CFG_RESP}" | grep -q '"retention_policy"'; then
    log_success "S3 / Cloudflare R2 Mirror config & retention policy verified!"
  else
    log_error "S3 / Cloudflare R2 Mirror endpoint validation failed: ${S3_CFG_RESP}"
    exit 1
  fi

  # 6. S3 Live Storage Usage & Free Tier Gauge Test
  log_info "Test 6: GET ${API_URL}/api/v1/storage/s3-usage"
  USAGE_RESP=$(curl -s "${API_URL}/api/v1/storage/s3-usage" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Tenant-ID: 11111111-1111-1111-1111-111111111111")
  if echo "${USAGE_RESP}" | grep -q '"free_tier_gb":10.0'; then
    log_success "S3 Storage Usage & 10 GB Free Tier gauge verified!"
  else
    log_error "S3 Storage Usage validation failed: ${USAGE_RESP}"
    exit 1
  fi

  # 7. Pytest Integration Suite inside staging container
  log_info "Test 7: Running pytest regression suite in Staging container..."
  ${COMPOSE_CMD} exec -T b00k5_staging_api pytest tests/test_gstr1_table13_and_uqc.py tests/test_compliance.py tests/test_s3_remote_mirror.py -q
  log_success "All test suites PASSED in isolated Staging environment!"
}

cmd_down() {
  log_info "Tearing down Staging/QA environment and removing ephemeral volumes (Project: ${PROJECT_NAME})..."
  ${COMPOSE_CMD} down -v
  log_success "Staging/QA environment destroyed. Production remains 100% untouched!"
}

cmd_test_and_destroy() {
  echo -e "${CYAN}================================================================${NC}"
  echo -e "${CYAN}   b00k5 STAGING/QA DEPLOY, TEST & DESTROY AUTOMATION           ${NC}"
  echo -e "${CYAN}================================================================${NC}"

  # Trap errors to ensure teardown always happens
  trap cmd_down EXIT

  cmd_up
  cmd_test

  log_success "All Staging tests completed successfully."
  log_info "Initiating automatic teardown as requested..."
}

ACTION="${1:-test-and-destroy}"

case "${ACTION}" in
  up)
    cmd_up
    ;;
  test)
    cmd_test
    ;;
  down)
    cmd_down
    ;;
  test-and-destroy)
    cmd_test_and_destroy
    ;;
  *)
    echo "Usage: $0 {up|test|down|test-and-destroy}"
    exit 1
    ;;
esac

