"""Background loop inside the API server: keeps fixtures, predictions and strategies moving.

Every 15 minutes: settle finished bets, apply drawdown stops, let enabled strategies place bets.
Every 6 hours (and at start-up): refresh upcoming fixtures and re-predict them.
Every cycle: retrain the ML models if the last run is older than training.retrain_every_days.
Every cycle: forward test (mock bets on upcoming matches, settle finished ones, re-learn calibration).
Every 15 minutes: keep the ESPN scraper going (backend/scraping/auto.py), if its switch is on.

Nothing here can send a real bet by itself: real orders only go out through the Stake
helper while Execution is ON on the Stake page, and within the .env caps.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from backend.core.settings import cfg
from backend.database.engine import AsyncSessionFactory
from backend.database.models import AppSetting

log = logging.getLogger("sportsanalyzer.automation")



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


async def retrain_cycle() -> dict[str, Any]:
    """Start a training run (all models, auto-selected data) when the last one is older than
    training.retrain_every_days. Runs in its own process; one at a time."""
    from sqlalchemy import select

    from backend import training
    from backend.database.models import TrainingRun

    days = cfg("training.retrain_every_days")
    if not days:
        return {"retrain": "off"}
    async with AsyncSessionFactory() as session:
        runs = (await session.execute(select(TrainingRun).order_by(TrainingRun.id.desc()).limit(20))).scalars().all()
    if any(r.status in training.ACTIVE for r in runs):
        return {"retrain": "a run is in progress"}
    last = next((r for r in runs if r.status == "finished"), None)
    if last and datetime.now(UTC) - (last.finished_at or last.created_at) < timedelta(days=days):
        return {"retrain": f"next after {((last.finished_at or last.created_at) + timedelta(days=days)).date()}"}
    from backend.models.ml import ML_MODELS

    run_id = await asyncio.to_thread(training.create_run, list(ML_MODELS))
    await asyncio.to_thread(training.launch, run_id)
    return {"retrain": f"started training run #{run_id}"}


async def forward_cycle() -> dict[str, Any]:
    from backend.forward import cycle

    async with AsyncSessionFactory() as session:
        report = await cycle(session)
        await session.commit()
    return report


async def scraper_cycle() -> dict[str, Any]:
    from backend.scraping.auto import cycle

    async with AsyncSessionFactory() as session:
        report = await cycle(session)
        await session.commit()
    return report


async def loop() -> None:
    state: dict[str, Any] = {"started_at": datetime.now(UTC).isoformat()}
    last_refresh: datetime | None = None
    await asyncio.sleep(20)  # let the server finish starting
    while True:
        now = datetime.now(UTC)
        try:
            if last_refresh is None or now - last_refresh >= timedelta(hours=cfg("automation.refresh_hours")):
                state["last_refresh"] = {"at": now.isoformat(), **(await refresh_fixtures_and_predictions())}
                last_refresh = now
            state["last_cycle"] = {"at": datetime.now(UTC).isoformat(), **(await strategy_cycle())}
            try:
                state["last_cycle"].update(await retrain_cycle())
            except Exception as exc:
                log.exception("retrain check failed")
                state["last_cycle"]["retrain"] = f"error: {type(exc).__name__}: {exc}"
            try:
                state["last_cycle"]["forward"] = await forward_cycle()
            except Exception as exc:
                log.exception("forward test cycle failed")
                state["last_cycle"]["forward"] = f"error: {type(exc).__name__}: {exc}"
            try:
                state["last_cycle"].update(await scraper_cycle())
            except Exception as exc:  # the scraper must never stop betting automation
                log.exception("scraper cycle failed")
                state["last_cycle"]["scraper"] = f"error: {type(exc).__name__}: {exc}"
            state["last_error"] = None
        except Exception as exc:  # keep the loop alive; show the problem on the dashboard
            log.exception("automation cycle failed")
            state["last_error"] = {"at": datetime.now(UTC).isoformat(), "error": f"{type(exc).__name__}: {exc}"}
        state["next_cycle_at"] = (datetime.now(UTC) + timedelta(minutes=cfg("automation.cycle_minutes"))).isoformat()
        try:
            await _save(state)
        except Exception:
            log.exception("could not save automation state")
        await asyncio.sleep(cfg("automation.cycle_minutes") * 60)
