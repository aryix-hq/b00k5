import uuid
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Base session generator without tenant context (for auth, setup, public endpoints)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

get_db = get_db_session

async def set_tenant_context(session: AsyncSession, tenant_id: str | uuid.UUID) -> None:
    """
    Enforces PostgreSQL Row-Level Security (RLS) for the current session transaction.
    Uses SET LOCAL to strictly isolate queries to the given tenant_id.
    """
    tenant_str = str(tenant_id)
    # Validate UUID format to prevent SQL injection in session setting
    uuid.UUID(tenant_str)
    await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_str}'"))
