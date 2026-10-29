from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings, validate_production_security
from app.core.s3 import ensure_buckets_exist
from app.api.v1 import auth, setup, invoices, ledger, vault, compliance, dsc, reconciliation, storage, iam, expenses, pricing, system, batch_ingest, reports, tenant_iam, tds, assets, registers, payroll

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("b00k5_api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting b00k5 Financial OS Backend...")
    validate_production_security()
    try:
        ensure_buckets_exist()
    except Exception as e:
        logger.warning(f"Could not initialize S3 buckets at startup: {e}")
    try:
        from app.core.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE invoice_items ADD COLUMN IF NOT EXISTS uqc VARCHAR(10) DEFAULT 'OTH'"))
    except Exception as e:
        logger.warning(f"Could not initialize uqc column on invoice_items: {e}")
    yield
    logger.info("Shutting down b00k5 API...")
    try:
        from app.core.database import engine
        await engine.dispose()
    except Exception as e:
        logger.warning(f"Error disposing engine pool: {e}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Open-Source, Local-First ERP, Compliance Engine, and Document Vault for Indian Startups",
    lifespan=lifespan
)

from fastapi import Request
from fastapi.responses import JSONResponse

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error processing {request.method} {request.url.path}: {exc}", exc_info=True)
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    )

# Include v1 routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(setup.router, prefix=f"{settings.API_V1_STR}/setup", tags=["First-Run Setup & CIN"])
app.include_router(invoices.router, prefix=f"{settings.API_V1_STR}/invoices", tags=["Invoicing & GST Engine"])
app.include_router(ledger.router, prefix=f"{settings.API_V1_STR}/ledger", tags=["General Ledger & Double-Entry"])
app.include_router(reconciliation.router, prefix=f"{settings.API_V1_STR}/reconciliation", tags=["Bank Statements & 3-Tier Reconciliation"])
app.include_router(vault.router, prefix=f"{settings.API_V1_STR}/vault", tags=["Document Locker (Vault)"])
app.include_router(compliance.router, prefix=f"{settings.API_V1_STR}/compliance", tags=["Statutory Compliance Watchdog"])
app.include_router(dsc.router, prefix=f"{settings.API_V1_STR}/dsc", tags=["Hardware Token DSC & Audit"])
app.include_router(storage.router, prefix=f"{settings.API_V1_STR}/storage", tags=["Storage & Cloud Sync"])
app.include_router(iam.router, prefix=f"{settings.API_V1_STR}/iam", tags=["Identity & Access Management (IAM)"])
app.include_router(expenses.router, prefix=f"{settings.API_V1_STR}/expenses", tags=["Expenses & Personal Reimbursements"])
app.include_router(pricing.router, prefix=f"{settings.API_V1_STR}/pricing", tags=["Pricing & GST Calculator"])
app.include_router(system.router, prefix=f"{settings.API_V1_STR}/system", tags=["System & Administration"])
app.include_router(batch_ingest.router, prefix=f"{settings.API_V1_STR}/batch", tags=["Batch Ingestion"])
app.include_router(reports.router, prefix=f"{settings.API_V1_STR}/reports", tags=["Financial Statements & Schedule III Reports"])
app.include_router(reconciliation.router, prefix=f"{settings.API_V1_STR}/banking", tags=["Banking & Reconciliation (Alias)"])
app.include_router(tenant_iam.router, prefix=f"{settings.API_V1_STR}/tenants", tags=["Multi-Company Tenant Context & IAM"])
app.include_router(tds.router, prefix=f"{settings.API_V1_STR}/tds", tags=["Indian TDS/TCS Withholding (FEAT-08)"])
app.include_router(assets.router, prefix=f"{settings.API_V1_STR}/assets", tags=["Schedule II Fixed Assets & Depreciation (FEAT-09)"])
app.include_router(registers.router, prefix=f"{settings.API_V1_STR}/registers", tags=["MCA Statutory Registers & Disclosures (FEAT-12)"])
app.include_router(payroll.router, prefix=f"{settings.API_V1_STR}/payroll", tags=["Sovereign Payroll & Statutory Withholdings (FEAT-PAY-01)"])

@app.get("/")
@app.get("/health")
@app.get("/healthz")
@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    return {
        "status": "healthy",
        "system": "b00k5 Core Engine",
        "jurisdiction": "India (MCA / GSTN / Income Tax)",
        "version": settings.VERSION
    }
