"""
b00k5 - Celery Worker for Automated PostgreSQL Database Backup to Google Drive
Scheduled nightly via Celery Beat (02:00 AM IST) and available on-demand.
"""

import asyncio
import uuid
import logging
from typing import Optional, Dict, Any

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.services.db_backup import DatabaseBackupManager

logger = logging.getLogger("b00k5_backup_worker")


async def _run_backup_async(tenant_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        log_record = await DatabaseBackupManager.run_backup_and_record(
            db=session,
            tenant_id=tenant_id
        )
        return {
            "backup_id": str(log_record.id),
            "filename": log_record.filename,
            "file_size_bytes": log_record.file_size_bytes,
            "sha256_checksum": log_record.sha256_checksum,
            "gdrive_file_id": log_record.gdrive_file_id,
            "gdrive_folder_path": log_record.gdrive_folder_path,
            "status": log_record.status,
            "duration_seconds": float(log_record.duration_seconds or 0.0),
            "created_at": log_record.created_at.isoformat() if log_record.created_at else None
        }


@celery_app.task(name="tasks.backup_database_to_gdrive", bind=True, max_retries=3)
def backup_database_to_gdrive_task(self, tenant_id: Optional[str] = None):
    """
    Executes pg_dump, AES-256-GCM encryption, and streams encrypted backup to Google Drive.
    """
    try:
        t_uuid = uuid.UUID(tenant_id) if tenant_id else None
        result = asyncio.run(_run_backup_async(tenant_id=t_uuid))
        logger.info(f"Database backup completed successfully: {result['filename']}")
        return result
    except Exception as exc:
        logger.error(f"Database backup task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)
