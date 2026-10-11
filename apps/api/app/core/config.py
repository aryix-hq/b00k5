import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    class BaseSettings:
        pass

class Settings(BaseSettings):
    PROJECT_NAME: str = "b00k5"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://b00k5_admin:b00k5_secure_vault_password_2026@localhost:5432/b00k5_db"
    )
    
    # Sync DB URL for Alembic or Celery tasks if needed
    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL",
        "postgresql://b00k5_admin:b00k5_secure_vault_password_2026@localhost:5432/b00k5_db"
    )

    # Redis & Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # MinIO / S3
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minio_storage_admin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minio_storage_secret_key_2026")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    
    # Phase 0 S3 Buckets
    BUCKET_STATEMENTS: str = os.getenv("MINIO_BUCKET_STATEMENTS", "b00k5-statements")
    BUCKET_RECEIPTS: str = os.getenv("MINIO_BUCKET_RECEIPTS", "b00k5-receipts")
    BUCKET_STATUTORY: str = os.getenv("MINIO_BUCKET_STATUTORY", "b00k5-statutory")

    # Compatibility Aliases
    BUCKET_VAULT: str = os.getenv("MINIO_BUCKET_STATUTORY", "b00k5-statutory")
    BUCKET_EXPENSES: str = os.getenv("MINIO_BUCKET_RECEIPTS", "b00k5-receipts")
    BUCKET_INVOICES: str = os.getenv("MINIO_BUCKET_RECEIPTS", "b00k5-receipts")

    # Security & Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "e9b46e3d234857b64917a26f049a46399e52701979b0ccb0d6fbca295eefcd22")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours

    # Hardware DSC Bridge
    DSC_BRIDGE_URL: str = os.getenv("DSC_BRIDGE_URL", "http://127.0.0.1:28045")

    class Config:
        case_sensitive = True

settings = Settings()
