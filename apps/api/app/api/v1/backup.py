"""
b00k5 Sovereign Backup & Snapshot Router
Canonical & Alias endpoints for:
- POST /api/v1/backup/trigger -> Trigger on-demand encrypted pg_dump backup (with Cloudflare R2 / S3 mirroring)
- GET  /api/v1/backup/logs -> List backup audit logs
- GET  /api/v1/backup/minio-snapshots -> List MinIO snapshots
- POST /api/v1/backup/minio-checkpoint -> Create instant safety checkpoint
- POST /api/v1/backup/restore -> Restore database snapshot
"""
import uuid
from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.core.database import get_db
from app.core.iam import require_super_admin_or_owner
from app.models.tenant import User, Tenant
from app.models.backup import DatabaseBackupLog
from app.services.db_backup import DatabaseBackupManager
from app.api.v1.system import (
    trigger_database_backup,
    list_database_backup_logs,
    list_backup_snapshots,
    create_minio_checkpoint,
    restore_minio_checkpoint,
    RestoreCheckpointRequest,
    BackupLogResponse,
    get_optional_tenant
)

router = APIRouter()


@router.post("/trigger", response_model=BackupLogResponse)
@router.post("/backup-database", response_model=BackupLogResponse)
async def backup_trigger_alias(
    current_admin: User = Depends(require_super_admin_or_owner),
    tenant: Optional[Tenant] = Depends(get_optional_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Alias for /api/v1/system/backup-database."""
    return await trigger_database_backup(current_admin=current_admin, tenant=tenant, db=db)


@router.get("/logs", response_model=List[BackupLogResponse])
@router.get("/backup-logs", response_model=List[BackupLogResponse])
async def backup_logs_alias(
    limit: int = Query(20, ge=1, le=100),
    tenant: Optional[Tenant] = Depends(get_optional_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Alias for /api/v1/system/backup-logs."""
    return await list_database_backup_logs(limit=limit, tenant=tenant, db=db)


@router.get("/minio-snapshots")
@router.get("/snapshots")
async def backup_snapshots_alias(
    current_admin: User = Depends(require_super_admin_or_owner)
):
    """Alias for /api/v1/system/backup/snapshots."""
    return await list_backup_snapshots(current_admin=current_admin)


@router.post("/minio-checkpoint")
@router.post("/checkpoint")
async def backup_checkpoint_alias(
    tenant: Optional[Tenant] = Depends(get_optional_tenant),
    current_admin: User = Depends(require_super_admin_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """Alias for /api/v1/system/backup/checkpoint."""
    return await create_minio_checkpoint(tenant=tenant, current_admin=current_admin, db=db)


@router.post("/restore")
async def backup_restore_alias(
    payload: RestoreCheckpointRequest,
    current_admin: User = Depends(require_super_admin_or_owner)
):
    """Alias for /api/v1/system/backup/restore."""
    return await restore_minio_checkpoint(payload=payload, current_admin=current_admin)
