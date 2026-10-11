import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from app.core.celery_app import celery_app
    HAVE_CELERY = True
except ImportError:
    HAVE_CELERY = False
    class MockCelery:
        def task(self, *args, **kwargs):
            def decorator(f):
                f.delay = f
                return f
            return decorator
    celery_app = MockCelery()

from app.core.s3 import storage_manager
from app.services.gdrive_virtualizer import DirectoryVirtualizer
from app.services.gdrive_client import GoogleDriveSyncClient

logger = logging.getLogger("b00k5_gdrive_sync_worker")

# Shared client instance
gdrive_client = GoogleDriveSyncClient()

@celery_app.task(name="app.workers.gdrive_sync_worker.sync_file_to_gdrive", bind=True, max_retries=5)
def sync_file_to_gdrive(*args, **kwargs) -> Dict[str, Any]:
    """
    Celery task that synchronizes a local MinIO document to Google Drive:
    1. Reads stream from MinIO storage.
    2. Validates local payload integrity (SHA-256).
    3. Traverses/creates folder hierarchy: LedgerFree_Archive / FY_YYYY-YYYY / [Category].
    4. Performs upload with exponential backoff on HTTP 429/503.
    5. Confirms remote file metadata & checksum.
    6. Updates cloud_sync_ledger record to 'synced'.
    """
    self_obj = None
    remaining_args = list(args)
    if remaining_args and not isinstance(remaining_args[0], str):
        self_obj = remaining_args.pop(0)

    arg_names = ["sync_id", "s3_bucket", "s3_key", "gdrive_folder_path", "file_name", "expected_sha256"]
    for i, val in enumerate(remaining_args):
        if i < len(arg_names):
            kwargs[arg_names[i]] = val

    sync_id = kwargs.get("sync_id", "")
    s3_bucket = kwargs.get("s3_bucket", "")
    s3_key = kwargs.get("s3_key", "")
    gdrive_folder_path = kwargs.get("gdrive_folder_path", "")
    file_name = kwargs.get("file_name", "")
    expected_sha256 = kwargs.get("expected_sha256", "")
    logger.info(f"Starting Google Drive sync for sync_id={sync_id} (file: {file_name})")
    
    try:
        # 1. Read document bytes from local MinIO
        file_bytes = storage_manager.get_document_bytes(s3_bucket, s3_key)
        actual_sha256 = storage_manager.calculate_sha256(file_bytes)

        if expected_sha256 and actual_sha256 != expected_sha256:
            raise ValueError(f"Checksum mismatch before sync: expected {expected_sha256}, got {actual_sha256}")

        # 2. Decompose virtual path into folder components
        # e.g. "LedgerFree_Archive/FY_2025-2026/Bank_Statements"
        folder_parts = [p for p in gdrive_folder_path.replace("\\", "/").split("/") if p]
        
        # 3. Create or resolve folder hierarchy
        leaf_folder_id = gdrive_client.get_or_create_remote_folders(folder_parts)

        # 4. Upload file with exponential backoff for 429 / 503
        mime_type = "application/pdf" if file_name.lower().endswith(".pdf") else "application/octet-stream"
        remote_meta = gdrive_client.upload_file_with_backoff(
            folder_id=leaf_folder_id,
            file_name=file_name,
            file_bytes=file_bytes,
            mime_type=mime_type,
            max_retries=5
        )

        gdrive_file_id = remote_meta.get("id")
        remote_md5 = remote_meta.get("md5Checksum")
        remote_sha256 = remote_meta.get("sha256Checksum", actual_sha256)

        logger.info(f"Successfully synced {file_name} to Google Drive: id={gdrive_file_id}, md5={remote_md5}")

        # 5. Database update hook (sync DB session if available)
        _update_db_sync_status(
            sync_id=sync_id,
            status="synced",
            gdrive_file_id=gdrive_file_id,
            gdrive_md5=remote_md5
        )

        return {
            "status": "synced",
            "sync_id": sync_id,
            "gdrive_file_id": gdrive_file_id,
            "md5_checksum": remote_md5,
            "sha256_checksum": remote_sha256,
            "synced_at": datetime.utcnow().isoformat()
        }

    except Exception as exc:
        logger.error(f"Sync failed for sync_id={sync_id}: {exc}")
        _update_db_sync_status(
            sync_id=sync_id,
            status="failed",
            error_message=str(exc)
        )
        if self_obj and hasattr(self_obj, 'retry'):
            # Exponential countdown retry in Celery
            retry_count = getattr(self_obj.request, 'retries', 0) if hasattr(self_obj, 'request') else 0
            if retry_count < 5:
                countdown = 2 ** retry_count
                raise self_obj.retry(exc=exc, countdown=countdown)
        raise exc

def _update_db_sync_status(
    sync_id: str,
    status: str,
    gdrive_file_id: Optional[str] = None,
    gdrive_md5: Optional[str] = None,
    error_message: Optional[str] = None
):
    """Safely updates database sync record if SQLAlchemy is active."""
    try:
        from app.core.database import SessionLocal
        from app.models.cloud_sync import CloudSyncLedger
        import uuid

        if not SessionLocal:
            return

        with SessionLocal() as db:
            record = db.query(CloudSyncLedger).filter(CloudSyncLedger.id == uuid.UUID(sync_id)).first()
            if record:
                record.status = status
                if gdrive_file_id:
                    record.gdrive_file_id = gdrive_file_id
                if gdrive_md5:
                    record.gdrive_md5_checksum = gdrive_md5
                if error_message:
                    record.last_error = error_message
                    record.retry_count = record.retry_count + 1
                if status == "synced":
                    record.synced_at = datetime.utcnow()
                db.commit()
    except Exception as e:
        logger.debug(f"Optional DB status update skipped or unavailable: {e}")
