"""
b00k5 - System Administration API Router
Endpoints:
- GET  /api/v1/system/fiscal-calendar: Dynamic Indian Fiscal Year (FY) & Assessment Year (AY) resolution
- POST /api/v1/system/backup-database: Run on-demand encrypted pg_dump backup to Google Drive
- GET  /api/v1/system/backup-logs: Audit ledger of past database backups
"""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.api.deps import get_db, get_current_tenant, get_current_user, oauth2_scheme
from app.models.tenant import Tenant
from app.models.backup import DatabaseBackupLog
from app.core.fiscal_year import resolve_fiscal_calendar
from app.services.db_backup import DatabaseBackupManager
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class BackupLogResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    filename: str
    file_size_bytes: int
    sha256_checksum: str
    encryption_algorithm: str
    gdrive_file_id: Optional[str] = None
    gdrive_folder_path: Optional[str] = None
    status: str
    duration_seconds: float
    error_message: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


async def get_optional_tenant(
    token: Optional[str] = Depends(oauth2_scheme),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db)
) -> Optional[Tenant]:
    if token:
        try:
            user = await get_current_user(token=token, db=db)
            return await get_current_tenant(x_tenant_id=x_tenant_id, token=token, current_user=user, db=db)
        except Exception:
            pass
    if x_tenant_id:
        try:
            res = await db.execute(select(Tenant).where(Tenant.id == uuid.UUID(x_tenant_id)))
            t = res.scalar_one_or_none()
            if t:
                return t
        except Exception:
            pass
    res = await db.execute(select(Tenant).limit(1))
    return res.scalar_one_or_none()


@router.get("/health")
async def system_health():
    return {
        "status": "healthy",
        "service": "b00k5 System Engine",
        "version": "1.0.0"
    }


@router.get("/fiscal-calendar")
async def get_fiscal_calendar(
    active_fy: Optional[str] = Query(None, description="Selected active financial year e.g. '2025-26'")
):
    """
    Returns the active Indian Financial Year (FY) and Assessment Year (AY)
    dynamically computed from system date and selected session period.
    """
    return resolve_fiscal_calendar(selected_fy=active_fy)


@router.post("/backup-database", response_model=BackupLogResponse)
async def trigger_database_backup(
    tenant: Optional[Tenant] = Depends(get_optional_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes on-demand pg_dump, compresses, encrypts with AES-256-GCM, and streams to Google Drive.
    """
    try:
        tenant_id = tenant.id if tenant else None
        log_record = await DatabaseBackupManager.run_backup_and_record(
            db=db,
            tenant_id=tenant_id
        )
        return BackupLogResponse(
            id=str(log_record.id),
            tenant_id=str(log_record.tenant_id) if log_record.tenant_id else None,
            filename=log_record.filename,
            file_size_bytes=log_record.file_size_bytes,
            sha256_checksum=log_record.sha256_checksum,
            encryption_algorithm=log_record.encryption_algorithm or "AES-256-GCM",
            gdrive_file_id=log_record.gdrive_file_id,
            gdrive_folder_path=log_record.gdrive_folder_path,
            status=log_record.status,
            duration_seconds=float(log_record.duration_seconds or 0.0),
            error_message=log_record.error_message,
            created_at=log_record.created_at.isoformat() if log_record.created_at else datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database backup failed: {str(e)}"
        )


@router.get("/backup-logs", response_model=List[BackupLogResponse])
async def list_database_backup_logs(
    limit: int = Query(20, ge=1, le=100),
    tenant: Optional[Tenant] = Depends(get_optional_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the recent audit logs of database backups.
    """
    query = select(DatabaseBackupLog).order_by(desc(DatabaseBackupLog.created_at)).limit(limit)
    res = await db.execute(query)
    logs = res.scalars().all()

    return [
        BackupLogResponse(
            id=str(l.id),
            tenant_id=str(l.tenant_id) if l.tenant_id else None,
            filename=l.filename,
            file_size_bytes=l.file_size_bytes,
            sha256_checksum=l.sha256_checksum,
            encryption_algorithm=l.encryption_algorithm or "AES-256-GCM",
            gdrive_file_id=l.gdrive_file_id,
            gdrive_folder_path=l.gdrive_folder_path,
            status=l.status,
            duration_seconds=float(l.duration_seconds or 0.0),
            error_message=l.error_message,
            created_at=l.created_at.isoformat() if l.created_at else datetime.utcnow().isoformat()
        )
        for l in logs
    ]
