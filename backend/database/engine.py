from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import get_settings


def create_database_engine() -> AsyncEngine:
    """
    Create the application's asynchronous SQLAlchemy engine.

    The database URL and pool configuration come entirely from application
    settings. No database credentials or connection details are hard-coded.
    """
    settings = get_settings()
    database = settings.database

    if not database.url.strip():
        raise ValueError(
            "Database URL is not configured. "
            "Set SPORTSANALYZER_DB_URL in the environment."
        )

    return create_async_engine(
        database.url,
        pool_size=database.pool_size,
        max_overflow=database.max_overflow,
        pool_timeout=database.pool_timeout_seconds,
        pool_recycle=database.pool_recycle_seconds,
        pool_pre_ping=True,
    )


engine = create_database_engine()

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Provide one database session for an application operation.

    The session is automatically closed when the operation finishes.
    Transaction ownership remains with the caller.
    """
    async with AsyncSessionFactory() as session:
        yield session


async def dispose_database_engine() -> None:
    """
    Dispose all pooled database connections.

    This should be called during application shutdown.
    """
    await engine.dispose()