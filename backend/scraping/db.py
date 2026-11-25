"""Synchronous database access for Scrapy (which runs outside asyncio).

Uses the same database URL as the rest of the app, with the psycopg driver.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from backend.core.config import get_settings


def sync_url(url: str) -> str:
    # psycopg tries IPv6 (::1) first for "localhost"; Docker publishes the port on IPv4 only,
    # and on Windows that IPv6 attempt hangs instead of failing fast.
    return url.replace("+asyncpg", "+psycopg").replace("@localhost:", "@127.0.0.1:")


@lru_cache(maxsize=1)
def engine() -> Engine:
    return create_engine(sync_url(get_settings().database.url), pool_pre_ping=True, pool_size=2,
                         connect_args={"connect_timeout": 10})
