from __future__ import annotations

import socket
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from backend.core.config import get_settings


def _database_reachable(url: str) -> bool:
    parsed = urlparse(url.replace("+asyncpg", ""))
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 5432), 1):
            return True
    except OSError:
        return False


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is always rolled back."""
    url = get_settings().database.url
    if not url or not _database_reachable(url):
        pytest.skip("Docker Postgres is not running (docker compose up -d db)")

    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
