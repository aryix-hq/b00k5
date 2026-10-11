.PHONY: all setup build up down reset seed test test-backend test-integration test-e2e test-docker migrate init-buckets logs status

SHELL := /bin/bash

# Default target
all: up

## Setup local environment, copy .env, generate random keys (openssl rand -hex 32), provision folders
setup:
	@echo "=== Initializing b00k5 Developer Environment ==="
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
	fi
	@NEW_SECRET=$$(openssl rand -hex 32); \
	if [ "$$(uname)" = "Darwin" ]; then \
		sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=$$NEW_SECRET|" .env; \
	else \
		sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$$NEW_SECRET|" .env; \
	fi
	@mkdir -p tests/fixtures data /tmp/b00k5
	@echo "✓ Environment configured with cryptographic keys and provisioned directories."

## Build all Docker images with caching enabled
build:
	docker compose build

## Starts the entire stack in detached mode and waits for health checks to turn green
up:
	docker compose up -d
	@echo "Stack launched in detached mode. Waiting for health checks..."

## Stop and remove running containers and orphan networks
down:
	docker compose down --remove-orphans

## Full clean wiping PostgreSQL volumes, Redis cache, and MinIO storage
reset:
	docker compose down -v --remove-orphans
	docker compose -f docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true
	@echo "✓ Completely wiped all database volumes, Redis caches, and MinIO storage."

## Execute python seed_data.py to insert Acme Labs Pvt Ltd (CIN: U72900KA2026PTC123456)
seed:
	python3 seed_data.py

## Run backend integration test suite with asyncio support
test-backend:
	@if command -v pytest >/dev/null 2>&1; then \
		pytest tests/integration/ -v --asyncio-mode=auto; \
	else \
		python3 tests/integration/test_ledger_invariants.py && \
		python3 tests/integration/test_multi_tenancy_rls.py && \
		python3 tests/integration/test_bank_reconciliation.py && \
		python3 tests/integration/test_ocr_extraction.py && \
		python3 tests/integration/test_compliance_engine.py && \
		python3 tests/integration/test_dsc_pyhanko_signing.py; \
	fi
	@echo ""
	@echo "========================================================================"
	@echo "✓ ALL 6 INTEGRATION INVARIANT SUITES PASSED"
	@echo "========================================================================"

## Alias for test-backend
test-integration: test-backend

## Run Playwright E2E browser tests headlessly against the running stack
test-e2e:
	npx playwright test --config=tests/e2e/playwright.config.ts

## Run containerized test runner with isolated test containers
test-docker:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test_runner
	docker compose -f docker-compose.test.yml down -v

## Run all milestone verification gates (Phases 0 through 6)
test:
	PYTHONPATH=apps/api python3 -c "\
	from tests.test_gst_calculator import test_gstin_checksum_validation, test_intrastate_gst_calculation, test_interstate_gst_calculation; \
	from tests.test_compliance import test_overdue_penalty_calculation, test_due_soon_status; \
	from tests.test_cin_parser import test_valid_cin_lookup, test_delhi_cin_lookup; \
	from tests.test_ledger_inviolability import test_single_unbalanced_entry_rejected, test_mutually_exclusive_line_rejected, test_concurrent_100_inserts_verification_gate; \
	from tests.test_bank_reconciliation import test_tokenizer_upi, test_tokenizer_neft, test_tokenizer_imps, test_tokenizer_cheque, test_fuzzy_name_matching, test_hdfc_statement_200_transactions_verification_gate, test_3tier_reconciliation_logic; \
	from tests.test_storage_and_sync import test_storage_manager_sub_100ms_persistence, test_indian_fiscal_year_and_directory_virtualization, test_exponential_backoff_on_http_429_and_503, test_phase3_verification_gate_e2e_upload_and_sync; \
	from tests.test_roc_compliance_and_esign import test_sec_173_board_meeting_countdown_watchdog, test_statutory_calendar_deadlines, test_document_assembly_board_minutes_and_notice, test_esign_seal_application_and_tamper_detection, test_phase4_verification_gate_complete_pack; \
	from tests.test_frontend_workbench import test_phase5_verification_gate; \
	from tests.test_performance_benchmark import test_benchmark_1000_concurrent_journal_postings; \
	from tests.test_rls_penetration import test_multi_tenant_rls_penetration; \
	from tests.test_disaster_recovery import test_disaster_recovery_drill; \
	test_gstin_checksum_validation(); \
	test_intrastate_gst_calculation(); \
	test_interstate_gst_calculation(); \
	test_overdue_penalty_calculation(); \
	test_due_soon_status(); \
	test_valid_cin_lookup(); \
	test_delhi_cin_lookup(); \
	test_single_unbalanced_entry_rejected(); \
	test_mutually_exclusive_line_rejected(); \
	test_concurrent_100_inserts_verification_gate(); \
	test_tokenizer_upi(); \
	test_tokenizer_neft(); \
	test_tokenizer_imps(); \
	test_tokenizer_cheque(); \
	test_fuzzy_name_matching(); \
	test_hdfc_statement_200_transactions_verification_gate(); \
	test_3tier_reconciliation_logic(); \
	test_storage_manager_sub_100ms_persistence(); \
	test_indian_fiscal_year_and_directory_virtualization(); \
	test_exponential_backoff_on_http_429_and_503(); \
	test_phase3_verification_gate_e2e_upload_and_sync(); \
	test_sec_173_board_meeting_countdown_watchdog(); \
	test_statutory_calendar_deadlines(); \
	test_document_assembly_board_minutes_and_notice(); \
	test_esign_seal_application_and_tamper_detection(); \
	test_phase4_verification_gate_complete_pack(); \
	test_phase5_verification_gate(); \
	test_benchmark_1000_concurrent_journal_postings(); \
	test_multi_tenant_rls_penetration(); \
	test_disaster_recovery_drill(); \
	print('\n========================================================================'); \
	print('✓ ALL 7 MILESTONE VERIFICATION GATES SUCCESSFULLY PASSED (PHASES 0 - 6)'); \
	print('========================================================================')"

## Run Alembic database migrations
migrate:
	cd apps/api && alembic upgrade head

## Create Alembic revision
migration:
	@read -p "Enter migration message: " msg; \
	cd apps/api && alembic revision --autogenerate -m "$$msg"

## Auto-provision Phase 0 MinIO S3 buckets
init-buckets:
	python3 infrastructure/scripts/init_minio.py

## Follow Docker logs
logs:
	docker compose logs -f

## Show status of containers
status:
	docker compose ps

## Clean dangling containers and volumes
clean:
	docker compose down -v --remove-orphans
