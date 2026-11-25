"""FastAPI application: the local HTTP API the dashboard talks to.

Run with:  .venv/Scripts/uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text

from backend.core.config import ENV_FILE
from backend.database.engine import AsyncSessionFactory, dispose_database_engine
from backend.database.models import RawProviderObservation

# Provider adapters read os.environ directly, so expose .env to them.
load_dotenv(ENV_FILE)

# Providers we plan to support, and the env var that holds each key.
PROVIDERS: list[dict[str, str]] = [
    {"name": "api_football", "label": "API-Football", "key_env": "API_FOOTBALL_API_KEY"},
    {"name": "football_data", "label": "football-data.org", "key_env": "FOOTBALL_DATA_API_KEY"},
    {"name": "thesportsdb", "label": "TheSportsDB", "key_env": "THESPORTSDB_API_KEY"},
    {"name": "odds_api", "label": "The Odds API", "key_env": "ODDS_API_KEY"},
    {"name": "stake", "label": "Stake", "key_env": "STAKE_ACCESS_TOKEN"},
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_database_engine()


app = FastAPI(title="SportsAnalyzer API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, object]:
    """Liveness plus a real database round-trip."""
    database_ok = True
    database_error: str | None = None
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # report, don't crash the endpoint
        database_ok = False
        database_error = type(exc).__name__

    return {
        "status": "ok" if database_ok else "degraded",
        "database": {"ok": database_ok, "error": database_error},
        "time": datetime.now(UTC).isoformat(),
    }


@app.get("/api/providers")
async def providers() -> list[dict[str, object]]:
    """Which providers have keys configured, and how much raw data each has stored."""
    counts: dict[str, int] = {}
    last_seen: dict[str, str] = {}
    async with AsyncSessionFactory() as session:
        rows = await session.execute(
            select(
                RawProviderObservation.provider_name,
                func.count(),
                func.max(RawProviderObservation.received_at),
            ).group_by(RawProviderObservation.provider_name)
        )
        for name, count, latest in rows:
            counts[name] = count
            last_seen[name] = latest.isoformat() if latest else None

    return [
        {
            "name": p["name"],
            "label": p["label"],
            "configured": bool(os.getenv(p["key_env"], "").strip()),
            "observations": counts.get(p["name"], 0),
            "last_received_at": last_seen.get(p["name"]),
        }
        for p in PROVIDERS
    ]
