from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import asyncpg
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from backend.core.config import get_settings
from backend.database.models import Base


def _database_reachable(url: str) -> bool:
    parsed = urlparse(url.replace("+asyncpg", ""))
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 5432), 1):
            return True
    except OSError:
        return False


def _test_url() -> str | None:
    """Same server as the app, separate database: <name>_test. Real data is never touched."""
    url = get_settings().database.url
    if not url or not _database_reachable(url):
        return None
    app_url = make_url(url)
    return app_url.set(database=f"{app_url.database}_test").render_as_string(hide_password=False)


async def _recreate_test_database(test_url: str) -> None:
    url = make_url(test_url)
    admin = await asyncpg.connect(
        host=url.host, port=url.port, user=url.username, password=url.password, database="postgres"
    )
    try:
        exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", url.database)
        if not exists:
            await admin.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await admin.close()

    engine = create_async_engine(test_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> str | None:
    url = _test_url()
    if url is not None:
        asyncio.run(_recreate_test_database(url))
    return url


@pytest.fixture
async def db_session(test_database_url: str | None) -> AsyncIterator[AsyncSession]:
    """A session on the empty test database, inside a transaction that is always rolled back."""
    if test_database_url is None:
        pytest.skip("Docker Postgres is not running (docker compose up -d db)")

    engine = create_async_engine(test_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def settings_override(monkeypatch):
    """Override values from config/settings.toml for one test, e.g.
    settings_override({"training": {"xgb": {"rounds": 60}}})."""
    from backend.core import settings as settings_module

    def apply(patch):
        merged = settings_module.deep_merge(settings_module.settings(), patch)
        monkeypatch.setattr(settings_module, "settings", lambda: merged)

    return apply
