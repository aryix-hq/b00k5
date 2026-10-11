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


from fastapi import APIRouter, Depends, Query, HTTPException, status, Header, Request


async def get_optional_tenant(
    request: Request = None,
    token: Optional[str] = Depends(oauth2_scheme),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db)
) -> Optional[Tenant]:
    if token:
        user = await get_current_user(token=token, db=db)
        return await get_current_tenant(
            request=request,
            x_tenant_id=x_tenant_id,
            token=token,
            current_user=user,
            db=db
        )
    if x_tenant_id:
        try:
            from app.core.database import set_tenant_context
            tid = uuid.UUID(x_tenant_id)
            await set_tenant_context(db, tid)
            res = await db.execute(select(Tenant).where(Tenant.id == tid))
            t = res.scalar_one_or_none()
            if t:
                return t
        except HTTPException:
            raise
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
    active_fy: Optional[str] = Query(None, description="Selected active financial year e.g. '2025-26'"),
    reference_date: Optional[str] = Query(None, description="Optional ISO date (YYYY-MM-DD) for statutory regime evaluation")
):
    """
    Returns the active Indian Financial Year (FY) and Assessment Year (AY)
    dynamically computed from system date and selected session period.
    """
    from app.core.fiscal_year import calculate_indian_fy_ay
    from datetime import date as dt_date
    ref_dt = None
    if reference_date:
        try:
            ref_dt = dt_date.fromisoformat(reference_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid reference_date format; expected YYYY-MM-DD")
    cal = resolve_fiscal_calendar(current_date=ref_dt, selected_fy=active_fy)
    if ref_dt:
        fy_ay = calculate_indian_fy_ay(ref_dt)
        cal["reference_date_evaluation"] = {
            "fy_label": cal["system_fy"],
            "fy_full": fy_ay["fy_label"],
            "ay_label": cal["system_ay"],
            "tax_year_label": fy_ay["tax_year_label"],
            "governing_income_tax_act": fy_ay["governing_direct_tax_act"],
            "is_income_tax_act_2025": fy_ay["is_income_tax_act_2025"],
            "ca_transition_advisory": (
                "CA Review Required: Transaction falls on/after 1 April 2026 under Income-tax Act, 2025 (Tax Year TY 2026-27); verify transitional TDS/carry-forward provisions."
                if fy_ay["is_income_tax_act_2025"]
                else "Governed by Income-tax Act, 1961 (Previous Year / Assessment Year framework)."
            ),
        }
    return cal


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
    except HTTPException:
        raise
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
    Returns the recent audit logs of database backups scoped to the active tenant.
    """
    query = select(DatabaseBackupLog)
    if tenant:
        query = query.where(DatabaseBackupLog.tenant_id == tenant.id)
    query = query.order_by(desc(DatabaseBackupLog.created_at)).limit(limit)
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
