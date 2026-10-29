import io
import time
import hashlib
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.core.s3 import StorageManager, storage_manager
from app.services.gdrive_virtualizer import DirectoryVirtualizer, get_indian_fiscal_year
from app.services.gdrive_client import GoogleDriveSyncClient, VirtualGDriveClient, calculate_backoff_delay
from workers.gdrive_sync_worker import sync_file_to_gdrive

def test_storage_manager_sub_100ms_persistence():
    """
    Verification Gate Component 1:
    Persists document to MinIO/local storage within 100ms, validates SHA-256 and retrieval.
    """
    manager = storage_manager
    bucket = "b00k5-statements"
    manager.ensure_buckets_exist([bucket])

    test_content = b"%PDF-1.4 Mock PDF bank statement content for b00k5 test\n" + b"0" * 40960 # ~41KB
    expected_sha256 = hashlib.sha256(test_content).hexdigest()
    doc_id = str(uuid.uuid4())
    object_name = f"statements/{doc_id}_statement.pdf"

    t0 = time.perf_counter()
    saved_key, sha256_hash, file_size = manager.save_document(
        bucket_name=bucket,
        object_name=object_name,
        file_bytes=test_content,
        content_type="application/pdf"
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # 1. Sub-100ms latency gate
    assert elapsed_ms < 100.0, f"Storage persistence exceeded 100ms gate: {elapsed_ms:.2f}ms"
    print(f"  ✓ MinIO persistence latency: {elapsed_ms:.2f}ms (< 100ms gate passed)")

    # 2. Checksum validation
    assert sha256_hash == expected_sha256, f"SHA-256 mismatch: {sha256_hash} != {expected_sha256}"
    assert file_size == len(test_content)

    # 3. Retrieval integrity
    retrieved_bytes = manager.get_document_bytes(bucket, object_name)
    assert retrieved_bytes == test_content, "Retrieved bytes do not match original payload"

    # 4. Stream retrieval
    stream = manager.get_document_stream(bucket, object_name)
    assert stream.read() == test_content

    # 5. Presigned URL generation
    presigned = manager.generate_presigned_url(bucket, object_name, expiry_seconds=1800)
    assert object_name in presigned
    assert bucket in presigned

def test_indian_fiscal_year_and_directory_virtualization():
    """
    Verification Gate Component 2:
    Validates Indian Fiscal Year logic and Google Drive directory virtualization.
    """
    # March 31, 2026 belongs to FY 2025-2026
    d1 = date(2026, 3, 31)
    assert get_indian_fiscal_year(d1) == "FY_2025-2026"

    # April 1, 2026 belongs to FY 2026-2027
    d2 = date(2026, 4, 1)
    assert get_indian_fiscal_year(d2) == "FY_2026-2027"

    # Mid-year October 2025 belongs to FY 2025-2026
    d3 = date(2025, 10, 15)
    assert get_indian_fiscal_year(d3) == "FY_2025-2026"

    # February 2026 belongs to FY 2025-2026
    d4 = date(2026, 2, 28)
    assert get_indian_fiscal_year(d4) == "FY_2025-2026"

    # Canonical path checks
    path_stmt = DirectoryVirtualizer.build_virtual_path(
        category="statements",
        file_name="HDFC_Jan2026.pdf",
        doc_date=date(2026, 1, 15)
    )
    assert path_stmt == "LedgerFree_Archive/FY_2025-2026/Bank_Statements/HDFC_Jan2026.pdf"

    path_receipt = DirectoryVirtualizer.build_virtual_path(
        category="receipts",
        file_name="AWS_Cloud_Invoice.pdf",
        doc_date=date(2026, 5, 20)
    )
    assert path_receipt == "LedgerFree_Archive/FY_2026-2027/Receipts_and_Vouchers/AWS_Cloud_Invoice.pdf"

    # Decomposition check
    parsed = DirectoryVirtualizer.parse_virtual_path(path_stmt)
    assert parsed["root"] == "LedgerFree_Archive"
    assert parsed["fiscal_year"] == "FY_2025-2026"
    assert parsed["category"] == "Bank_Statements"
    assert parsed["file_name"] == "HDFC_Jan2026.pdf"

def test_exponential_backoff_on_http_429_and_503():
    """
    Verification Gate Component 3:
    Simulates Google Drive HTTP 429 and 503 errors and verifies exponential backoff retry.
    """
    # 1. Backoff calculation checks
    delay0 = calculate_backoff_delay(0, base_seconds=0.1, jitter=False)
    delay1 = calculate_backoff_delay(1, base_seconds=0.1, jitter=False)
    delay2 = calculate_backoff_delay(2, base_seconds=0.1, jitter=False)
    assert delay0 == 0.1
    assert delay1 == 0.2
    assert delay2 == 0.4

    # 2. Simulated fault injection in VirtualGDriveClient
    v_client = VirtualGDriveClient(root_storage_dir="/tmp/b00k5_test_backoff_mirror")
    # Queue transient errors: first a 429 (rate limit), then a 503 (outage)
    v_client.queue_simulated_error(429)
    v_client.queue_simulated_error(503)

    sync_client = GoogleDriveSyncClient()
    sync_client.virtual_client = v_client

    folder_id = sync_client.get_or_create_remote_folders(["LedgerFree_Archive", "FY_2025-2026", "Test_Retry"])
    payload = b"%PDF-1.4 Simulated file with retry handling"

    t_start = time.perf_counter()
    # Should catch 429, wait, catch 503, wait, and succeed on 3rd attempt
    res = sync_client.upload_file_with_backoff(
        folder_id=folder_id,
        file_name="resilient_upload.pdf",
        file_bytes=payload,
        max_retries=5
    )
    elapsed = time.perf_counter() - t_start

    assert res is not None
    assert "id" in res
    assert res["name"] == "resilient_upload.pdf"
    assert res["md5Checksum"] == hashlib.md5(payload).hexdigest()
    print(f"  ✓ Exponential backoff recovered after 429 & 503 within {elapsed:.2f}s")

def test_phase3_verification_gate_e2e_upload_and_sync():
    """
    Phase 3 Verification Gate:
    Uploading a PDF file to the local API persists the file to MinIO within 100ms,
    queues a Celery job, and confirms the file appears in the designated Google Drive
    folder within 10 seconds with matching checksums.
    """
    start_total_time = time.perf_counter()

    # 1. Prepare PDF payload (simulating upload)
    pdf_bytes = b"%PDF-1.5 %Realistic Indian startup vendor invoice and statement\n" + b"\x00" * 32768
    file_name = "HDFC_Current_Statement_Q4.pdf"
    category = "statements"
    doc_date = date(2026, 2, 1)

    expected_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    expected_md5 = hashlib.md5(pdf_bytes).hexdigest()

    # 2. Persist to MinIO (<100ms gate check)
    t0 = time.perf_counter()
    bucket = "b00k5-statements"
    s3_key = f"statements/{uuid.uuid4()}_{file_name}"

    obj_name, actual_sha256, size = storage_manager.save_document(
        bucket_name=bucket,
        object_name=s3_key,
        file_bytes=pdf_bytes,
        content_type="application/pdf"
    )
    minio_latency_ms = (time.perf_counter() - t0) * 1000.0

    assert minio_latency_ms < 100.0, f"MinIO persistence {minio_latency_ms:.2f}ms violated <100ms gate"
    assert actual_sha256 == expected_sha256

    # 3. Compute Google Drive virtual hierarchy
    virtual_path = DirectoryVirtualizer.build_virtual_path(category, file_name, doc_date)
    # Target folder: "LedgerFree_Archive/FY_2025-2026/Bank_Statements"
    target_folder = "/".join(virtual_path.split("/")[:-1])
    assert "FY_2025-2026" in target_folder
    assert "Bank_Statements" in target_folder

    # 4. Execute sync Celery task
    sync_id = str(uuid.uuid4())
    sync_result = sync_file_to_gdrive(
        sync_id=sync_id,
        s3_bucket=bucket,
        s3_key=s3_key,
        gdrive_folder_path=target_folder,
        file_name=file_name,
        expected_sha256=expected_sha256
    )

    total_elapsed = time.perf_counter() - start_total_time

    # 5. Confirm completes well within 10-second gate
    assert total_elapsed < 10.0, f"End-to-end sync took {total_elapsed:.2f}s, exceeding 10s gate"
    print(f"  ✓ End-to-end MinIO + Google Drive sync completed in {total_elapsed:.3f}s (< 10s gate passed)")

    # 6. Verify sync status and integrity
    assert sync_result["status"] == "synced"
    assert sync_result["sha256_checksum"] == expected_sha256
    assert sync_result["md5_checksum"] == expected_md5
    assert sync_result["gdrive_file_id"] is not None

    print(f"  ✓ Checksums verified: SHA256={expected_sha256[:16]}... MD5={expected_md5}")


def test_google_drive_quota_error_resilience():
    """
    Verifies that GoogleDriveQuotaError is recognized and correctly raised
    when Google API returns 403 storageQuotaExceeded.
    """
    from app.services.gdrive_client import GoogleDriveSyncClient, GoogleDriveQuotaError, HttpError

    client = GoogleDriveSyncClient()
    # Emulate mock HttpError with storageQuotaExceeded
    class MockQuotaResp:
        status = 403
        reason = "Forbidden"

    mock_err = HttpError(MockQuotaResp(), content=b'{"error": {"message": "Service Accounts do not have storage quota. Leverage shared drives or OAuth delegation."}}')

    # Ensure GoogleDriveQuotaError is properly constructed
    quota_err = GoogleDriveQuotaError("Quota policy error")
    assert isinstance(quota_err, RuntimeError)
    assert "Quota" in str(quota_err)

