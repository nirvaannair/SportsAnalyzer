"""Background loop inside the API server: keeps fixtures, predictions and strategies moving.

Every 15 minutes: settle finished bets, apply drawdown stops, let enabled strategies place bets.
Every 6 hours (and at start-up): refresh upcoming fixtures and re-predict them.

Nothing here can send a real bet by itself: real orders only go out through the Stake
helper while Execution is ON on the Stake page, and within the .env caps.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from backend.database.engine import AsyncSessionFactory
from backend.database.models import AppSetting

log = logging.getLogger("sportsanalyzer.automation")

CYCLE_EVERY = timedelta(minutes=15)
REFRESH_EVERY = timedelta(hours=6)


async def _save(state: dict[str, Any]) -> None:
    async with AsyncSessionFactory() as session:
        statement = insert(AppSetting).values(key="automation", value=state)
        await session.execute(statement.on_conflict_do_update(index_elements=["key"],
                                                              set_={"value": statement.excluded.value}))
        await session.commit()


async def refresh_fixtures_and_predictions() -> dict[str, Any]:
    from backend.ingestion.fdcuk import import_fixtures
    from backend.pipeline import predict_and_store

    counts = await import_fixtures(AsyncSessionFactory)
    async with AsyncSessionFactory() as session:
        predicted = await predict_and_store(session, date.today())
        await session.commit()
    return {"fixtures": sum(counts.values()), "predicted": predicted}


async def strategy_cycle() -> dict[str, Any]:
    from backend.strategies.engine import run_cycle

    async with AsyncSessionFactory() as session:
        report = await run_cycle(session)
        await session.commit()
    return report


async def loop() -> None:
    state: dict[str, Any] = {"started_at": datetime.now(UTC).isoformat()}
    last_refresh: datetime | None = None
    await asyncio.sleep(20)  # let the server finish starting
    while True:
        now = datetime.now(UTC)
        try:
            if last_refresh is None or now - last_refresh >= REFRESH_EVERY:
                state["last_refresh"] = {"at": now.isoformat(), **(await refresh_fixtures_and_predictions())}
                last_refresh = now
            state["last_cycle"] = {"at": datetime.now(UTC).isoformat(), **(await strategy_cycle())}
            state["last_error"] = None
        except Exception as exc:  # keep the loop alive; show the problem on the dashboard
            log.exception("automation cycle failed")
            state["last_error"] = {"at": datetime.now(UTC).isoformat(), "error": f"{type(exc).__name__}: {exc}"}
        state["next_cycle_at"] = (datetime.now(UTC) + CYCLE_EVERY).isoformat()
        try:
            await _save(state)
        except Exception:
            log.exception("could not save automation state")
        await asyncio.sleep(CYCLE_EVERY.total_seconds())
