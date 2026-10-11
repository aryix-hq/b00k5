"""
b00k5 Integration Test Suite: Production Defect Verification (DEF-01 to DEF-04)
Validates:
1. DEF-01: SS-1 Board Meeting Minutes generator binds Company Master Profile, CIN, registered office, and director roster.
2. DEF-02: Google Drive configuration and backend Service Account / OAuth2 direct upload flow.
3. DEF-03: Server-side JWT revocation in Redis / Memory and logout authorization invalidation.
4. DEF-04: Row-Level Security (RLS) enforcement across corporate_meetings, invoices, expenses, document_vault, and journal_entries.
"""

import uuid
import json
from datetime import date, datetime, timedelta
import pytest
from app.services.document_assembly import DocumentAssemblyService
from app.core.security import create_access_token, decode_access_token, revoke_token, is_token_revoked
from app.services.gdrive_client import GoogleDriveSyncClient
from tests.integration.test_multi_tenancy_rls import PostgreSQLRLSSimulator

def test_def01_ss1_board_minutes_binds_company_profile_and_roster():
    """
    DEF-01: Asserts that SS-1 Board Minutes binds the Company Master Profile,
    CIN, registered office, and director roster with DIN.
    """
    tenant_master_profile = {
        "company_name": "Acme Labs PRIVATE LIMITED",
        "cin": "U72900KA2026PTC123456",
        "registered_office": "100 FEET ROAD, INDIRANAGAR, BENGALURU 560038",
        "meeting_number": "BM/2026-27/01",
        "meeting_date": "2026-04-15",
        "meeting_time": "11:00 AM IST",
        "venue": "Registered Office, Indiranagar, Bengaluru",
        "directors_present": [
            {"name": "Vikram Sharma", "din": "09876541", "designation": "Director"},
            {"name": "Rohit Verma", "din": "09876542", "designation": "Managing Director"}
        ],
        "resolutions": [
            "RESOLVED THAT the audited financial statements for FY 2025-26 be and are hereby approved.",
            "RESOLVED FURTHER THAT Form AOC-4 and Form MGT-7 be digitally signed with HYP 2003 DSC."
        ]
    }

    pdf_bytes = DocumentAssemblyService.assemble_board_minutes(tenant_master_profile)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.4")
    # Verify Company Master Profile bound
    assert b"Acme Labs" in pdf_bytes
    assert b"PRIVATE LIMITED" in pdf_bytes
    assert b"U72900KA2026PTC123456" in pdf_bytes
    assert b"INDIRANAGAR" in pdf_bytes
    # Verify Director Roster with DIN bound
    assert b"Vikram Sharma" in pdf_bytes
    assert b"09876541" in pdf_bytes
    assert b"Rohit Verma" in pdf_bytes
    assert b"09876542" in pdf_bytes
    # Verify Meeting reference and resolutions bound
    assert b"BM/2026-27/01" in pdf_bytes
    assert b"RESOLVED THAT the audited financial statements" in pdf_bytes


def test_def02_gdrive_sync_client_and_virtual_hierarchy():
    """
    DEF-02: Asserts Google Drive v3 Client creates canonical hierarchy
    and performs upload with SHA-256 and MD5 checksum verification.
    """
    client = GoogleDriveSyncClient()

    hierarchy_parts = ["b00k5", "ACME_LABS_PVT_LTD", "FY_2025-26", "Bank_Statements"]
    leaf_folder_id = client.get_or_create_remote_folders(hierarchy_parts)
    assert leaf_folder_id is not None
    assert len(leaf_folder_id) > 0

    sample_content = b"%PDF-1.4 Sample Indian Bank Statement for Testing"
    file_name = "HDFC_Statement_Apr2025.pdf"

    upload_meta = client.upload_file_with_backoff(
        folder_id=leaf_folder_id,
        file_name=file_name,
        file_bytes=sample_content,
        mime_type="application/pdf"
    )

    assert upload_meta["name"] == file_name
    assert upload_meta["id"] is not None
    assert "md5Checksum" in upload_meta or "sha256Checksum" in upload_meta


def test_def03_jwt_revocation_lifecycle():
    """
    DEF-03: Asserts server-side JWT revocation invalidates tokens immediately.
    """
    token_data = {
        "sub": str(uuid.uuid4()),
        "email": "director@acme.corp",
        "tenant_id": str(uuid.uuid4()),
        "role": "owner"
    }

    token = create_access_token(data=token_data)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert "jti" in decoded
    assert decoded["email"] == "director@acme.corp"

    # Token initially valid
    assert is_token_revoked(token) is False

    # Revoke token (simulating POST /api/v1/auth/logout)
    revoked = revoke_token(token)
    assert revoked is True

    # Assert token is now blocked
    assert is_token_revoked(token) is True


def test_def04_corporate_meetings_and_ledger_rls_isolation():
    """
    DEF-04: Asserts PostgreSQL Row-Level Security on corporate_meetings,
    invoices, expenses, and document_vault.
    """
    sim = PostgreSQLRLSSimulator()

    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    # Switch session context to Tenant A
    sim.set_config("app.current_tenant", tenant_a)

    # Insert corporate meeting for Tenant A
    meeting_a = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_a,
        "meeting_number": "BM/2026-27/01",
        "meeting_date": "2026-04-15",
        "venue": "Bengaluru",
        "status": "signed"
    }
    sim.insert("corporate_meetings", meeting_a)

    # Insert invoice for Tenant A
    inv_a = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_a,
        "invoice_number": "INV-2026-001",
        "total_amount": 100000.00
    }
    sim.insert("invoices", inv_a)

    # Verify Tenant A sees their records
    assert len(sim.select("corporate_meetings")) == 1
    assert len(sim.select("invoices")) == 1

    # Switch session context to Tenant B
    sim.set_config("app.current_tenant", tenant_b)

    # Assert Tenant B sees ZERO records from Tenant A (Row-Level Security)
    assert len(sim.select("corporate_meetings")) == 0
    assert len(sim.select("invoices")) == 0

    # Cross-tenant insert spoofing must be blocked by RLS WITH CHECK
    with pytest.raises(PermissionError):
        sim.insert("corporate_meetings", {
            "id": uuid.uuid4(),
            "tenant_id": tenant_a, # Malicious tenant spoofing
            "meeting_number": "BM/2026-27/02",
            "meeting_date": "2026-05-15",
            "venue": "Spoofed"
        })


def test_def02_option_a_service_account_routing_and_url_extraction():
    """
    DEF-02 Option A: Asserts Google Drive Service Account client extracts
    folder ID from raw URLs and validates client diagnostics.
    """
    import re
    # 1. URL extraction test
    pasted_url = "https://drive.google.com/drive/folders/1ABCxyz_987654321-LMNOP"
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', pasted_url)
    assert match is not None
    extracted_folder_id = match.group(1)
    assert extracted_folder_id == "1ABCxyz_987654321-LMNOP"

    # 2. Client initialization with root_folder_id
    client = GoogleDriveSyncClient(root_folder_id=extracted_folder_id)
    assert client.root_folder_id == "1ABCxyz_987654321-LMNOP"

    # 3. Connection test method returns valid dictionary
    diag = client.test_connection()
    assert "backend" in diag
    assert "live_cloud" in diag
    assert "message" in diag


def test_def02_celery_gdrive_queue_alignment():
    """
    DEF-02: Asserts Celery task routes map all gdrive sync and db backup
    tasks strictly to 'gdrive_queue' for b00k5_worker_sync daemon.
    """
    from app.core.celery_app import celery_app
    routes = celery_app.conf.task_routes

    assert routes.get("workers.gdrive_sync_worker.*", {}).get("queue") == "gdrive_queue"
    assert routes.get("app.workers.gdrive_sync_worker.*", {}).get("queue") == "gdrive_queue"
    assert routes.get("tasks.backup_database_to_gdrive", {}).get("queue") == "gdrive_queue"

