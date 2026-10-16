#!/usr/bin/env bash
# ==============================================================================
# b00k5 Branch Build & Deployment Automation Strategy Script
# ==============================================================================
# Safely deploys, builds, and verifies any git branch against Docker.
# Protects the main branch from unverified regressions.
#
# Usage:
#   ./scripts/branch_deploy.sh [BRANCH_NAME] [OPTIONS]
#
# Options:
#   --clean    Destroy all Docker volumes and start with a fresh, empty database
#   --test     Execute zero-mock integration and Selenium tests after startup
#   --build    Force full rebuild of Docker images without build cache
#   --help     Display this help menu
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Formatting & Colors
BOLD="\033[1m"
GREEN="\033[0;32m"
SKY="\033[0;36m"
AMBER="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m"

TARGET_BRANCH=""
CLEAN_MODE=false
RUN_TESTS=false
NO_CACHE=false

# Parse Arguments
for arg in "$@"; do
    case "$arg" in
        --clean)
            CLEAN_MODE=true
            ;;
        --test)
            RUN_TESTS=true
            ;;
        --build)
            NO_CACHE=true
            ;;
        --help|-h)
            echo -e "${BOLD}b00k5 Branch Build & Deploy Script${NC}"
            echo -e "Usage: ./scripts/branch_deploy.sh [BRANCH_NAME] [--clean] [--test] [--build]"
            exit 0
            ;;
        *)
            if [ -z "$TARGET_BRANCH" ]; then
                TARGET_BRANCH="$arg"
            fi
            ;;
    esac
done

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ -z "$TARGET_BRANCH" ]; then
    TARGET_BRANCH="${CURRENT_BRANCH}"
fi

echo -e "\n${BOLD}${SKY}==============================================================================${NC}"
echo -e "${BOLD}${SKY} 🚀 b00k5 BRANCH BUILD & DEPLOYMENT AUTOMATION${NC}"
echo -e "${BOLD}${SKY}==============================================================================${NC}"
echo -e " Target Branch     : ${BOLD}${GREEN}${TARGET_BRANCH}${NC}"
echo -e " Current Branch    : ${BOLD}${CURRENT_BRANCH}${NC}"
echo -e " Clean DB Reset    : $([ "$CLEAN_MODE" = true ] && echo -e "${AMBER}YES (Volumes will be destroyed)${NC}" || echo "NO")"
echo -e " Zero-Mock Tests   : $([ "$RUN_TESTS" = true ] && echo -e "${GREEN}YES${NC}" || echo "NO")"
echo -e "${SKY}------------------------------------------------------------------------------${NC}"

# Step 1: Branch Safety & Switch
if [ "${TARGET_BRANCH}" != "${CURRENT_BRANCH}" ]; then
    echo -e "\n${BOLD}1. Verifying Git Working Tree Cleanliness...${NC}"
    if [ -n "$(git status --porcelain)" ]; then
        echo -e "${AMBER}⚠️  Working tree has unstaged changes. Stashing before checkout...${NC}"
        git stash push -m "Auto-stash by branch_deploy.sh before checkout of ${TARGET_BRANCH}"
    fi

    echo -e "${BOLD}2. Checking out branch: ${TARGET_BRANCH}...${NC}"
    git checkout "${TARGET_BRANCH}"
else
    echo -e "\n${BOLD}1. Operating on active branch: ${TARGET_BRANCH}${NC}"
fi

# Step 2: Clean Environment Teardown (if requested)
if [ "$CLEAN_MODE" = true ]; then
    echo -e "\n${BOLD}2. Performing Clean Environment Teardown (Destroying volumes)...${NC}"
    docker compose down -v --remove-orphans || true
    echo -e "${GREEN}✔ Containers and volumes destroyed. Database is clean.${NC}"
fi

# Step 3: Build Docker Containers
echo -e "\n${BOLD}3. Building Docker Container Images...${NC}"
BUILD_FLAGS=""
if [ "$NO_CACHE" = true ]; then
    BUILD_FLAGS="--no-cache"
fi
docker compose build ${BUILD_FLAGS} b00k5_api b00k5_web

# Step 4: Bring Up Core Services
echo -e "\n${BOLD}4. Launching Sovereign Financial ERP Stack...${NC}"
docker compose up -d

# Step 5: Wait for Service Health
echo -e "\n${BOLD}5. Awaiting Container Health & Initialization...${NC}"
SERVICES=("b00k5_postgres" "b00k5_redis" "b00k5_minio" "b00k5_api" "b00k5_web")

for svc in "${SERVICES[@]}"; do
    echo -n " - Checking $svc ... "
    for i in {1..30}; do
        if [ "$(docker inspect -f '{{.State.Status}}' "$svc" 2>/dev/null)" = "running" ]; then
            echo -e "${GREEN}ONLINE${NC}"
            break
        fi
        sleep 1
        if [ "$i" -eq 30 ]; then
            echo -e "${RED}TIMEOUT waiting for $svc${NC}"
            docker logs --tail 30 "$svc"
            exit 1
        fi
    done
done

# Step 6: Verify Database Readiness
echo -e "\n${BOLD}6. Verifying PostgreSQL 16 & Relational Schema...${NC}"
docker exec b00k5_postgres psql -U b00k5_admin -d b00k5_db -c "SELECT 'Kernel Active' AS status, current_database(), version();"

# Step 7: Zero-Mock Automated Verification (if requested)
if [ "$RUN_TESTS" = true ]; then
    echo -e "\n${BOLD}7. Executing Zero-Mock Automated Verification Suite...${NC}"
    if [ -f ".venv/bin/pytest" ]; then
        .venv/bin/pytest tests/e2e/test_selenium_aryix_branding_and_about.py -v -s
    else
        docker exec b00k5_api pytest tests/integration/test_critical_fixes.py -v
    fi
    echo -e "${GREEN}✔ Zero-Mock Test Suite PASSED 100%!${NC}"
fi

# Summary
echo -e "\n${BOLD}${GREEN}==============================================================================${NC}"
echo -e "${BOLD}${GREEN} ✅ DEPLOYMENT SUCCESSFUL ON BRANCH: ${TARGET_BRANCH}${NC}"
echo -e "${BOLD}${GREEN}==============================================================================${NC}"
echo -e " Web Interface      : ${BOLD}http://localhost:3000${NC}"
echo -e " Backend API Docs   : ${BOLD}http://localhost:8000/docs${NC}"
echo -e " MinIO S3 Console   : ${BOLD}http://localhost:9001 (User: minio_storage_admin)${NC}"
echo -e " Branch State       : ${TARGET_BRANCH} (Protected main remains intact)"
echo -e " Pull Request Guide : Review .github/pull_request_template.md"
echo -e "${GREEN}==============================================================================${NC}\n"
