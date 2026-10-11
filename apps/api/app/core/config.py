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
    APP_ENV: str = os.getenv("APP_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "b00k5_default_dev_jwt_secret_key_change_in_prod_2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours
    DSC_MODE: str = os.getenv("DSC_MODE", "simulated") # 'hardware' or 'simulated'

    # Hardware DSC Bridge
    DSC_BRIDGE_URL: str = os.getenv("DSC_BRIDGE_URL", "http://127.0.0.1:28045")

    class Config:
        case_sensitive = True


KNOWN_INSECURE_SECRETS = {
    "",
    "changeme",
    "secret",
    "super-secret-jwt-key-change-in-prod",
    "change-this-to-a-secure-random-64-char-hex-secret-key-in-production",
    "b00k5_default_dev_jwt_secret_key_change_in_prod_2026",
    "e9b46e3d234857b64917a26f049a46399e52701979b0ccb0d6fbca295eefcd22",
    "b00k5_secure_vault_password_2026",
    "minio_storage_secret_key_2026",
}


def validate_production_security(env_override: Optional[dict] = None) -> dict:
    """
    SEC-01, SEC-06 & UAT-15: Fail-closed production configuration validator.
    Raises RuntimeError if APP_ENV == 'production' and any mandatory secret is missing,
    weak (< 32 characters), or matches a published default/placeholder credential,
    if uvicorn --reload is enabled, or if mock/simulated DSC signing is enabled.
    """
    env = env_override if env_override is not None else os.environ
    app_env = (env.get("APP_ENV") or "development").lower().strip()
    secret_key = (env.get("SECRET_KEY") or "").strip()
    db_url = (env.get("DATABASE_URL") or "").strip()
    minio_secret = (env.get("MINIO_SECRET_KEY") or env.get("MINIO_ROOT_PASSWORD") or "").strip()
    reload_flag = (env.get("UVICORN_RELOAD") or "false").lower().strip()
    dsc_mode = (env.get("DSC_MODE") or ("hardware" if app_env == "production" else "simulated")).lower().strip()
    dsc_bridge_url = (env.get("DSC_BRIDGE_URL") or "").lower().strip()

    violations = []
    if app_env == "production":
        if not secret_key or len(secret_key) < 32 or secret_key in KNOWN_INSECURE_SECRETS:
            violations.append("SECRET_KEY is missing, shorter than 32 chars, or uses a known published default.")
        if not db_url or "b00k5_secure_vault_password_2026" in db_url:
            violations.append("DATABASE_URL is missing or uses published default database password.")
        if not minio_secret or minio_secret in KNOWN_INSECURE_SECRETS:
            violations.append("MINIO_SECRET_KEY is missing or uses published default storage password.")
        if reload_flag == "true":
            violations.append("UVICORN_RELOAD cannot be enabled when APP_ENV=production.")
        if dsc_mode in ("simulated", "mock", "test"):
            violations.append("DSC_MODE cannot be 'simulated' or 'mock' when APP_ENV=production; must be 'hardware'.")
        if "bridge_mock" in dsc_bridge_url or "bridge-mock" in dsc_bridge_url:
            violations.append("DSC_BRIDGE_URL cannot point to mock signing bridge when APP_ENV=production.")

        if violations:
            raise RuntimeError(
                "FATAL [SEC-01 Fail-Closed]: Unsafe production startup blocked: " + "; ".join(violations)
            )

    return {
        "app_env": app_env,
        "dsc_mode": dsc_mode,
        "status": "secure" if not violations else "failed",
        "violations": violations,
    }


settings = Settings()
if (
    os.getenv("APP_ENV", "").lower().strip() == "production"
    or os.getenv("B00K5_STRICT_PROD", "false").lower() == "true"
):
    validate_production_security()

