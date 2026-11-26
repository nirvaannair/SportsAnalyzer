"""Keep the ESPN scraper running all the time (switch on the Scraper page; on by default).

Called by the automation loop every 15 minutes:
  * history backfill, NEWEST FIRST, in three chunks: the last 2 years, then mid-2021 to two
    years ago, then mid-2019 to mid-2021. Each chunk is resumed until it finishes (pages
    already fetched come from the cache, so a restart costs almost nothing);
  * otherwise, every 6 hours, scrape the last 10 days (new results, lineups) and the next 14
    (fixtures).
Only one scrape runs at a time; rate limits are waited out inside the crawl
(backend/scraping/middleware.py).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import cfg
from backend.database.models import AppSetting, ScrapeRun
from backend.scraping import run as runner

SETTING_KEY = "scraper_auto"
_last_load: dict[str, datetime] = {}
ACTIVE = ("queued", "running", "loading")


async def get_auto(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(AppSetting, SETTING_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    return {"enabled": bool(value.get("enabled", True)), "last_action": value.get("last_action")}


async def set_auto(session: AsyncSession, **values: Any) -> dict[str, Any]:
    current = await get_auto(session)
    current.update(values)
    statement = insert(AppSetting).values(key=SETTING_KEY, value=current)
    await session.execute(statement.on_conflict_do_update(index_elements=["key"],
                                                          set_={"value": statement.excluded.value}))
    return current


def backfill_chunks(today: date) -> list[tuple[date, date]]:
    """Newest first: the last `newest_first_years`, then `chunk_years` at a time back to `history_start`."""
    start = date.fromisoformat(cfg("scraper.history_start"))
    edge = max(start, today - timedelta(days=round(365.25 * cfg("scraper.newest_first_years"))))
    chunks = [(edge, today)]
    while edge > start:
        older = max(start, edge - timedelta(days=round(365.25 * cfg("scraper.chunk_years"))))
        chunks.append((older, edge))
        edge = older
    return chunks


def _covers(run: ScrapeRun, start: date, end: date) -> bool:
    args = run.args or {}
    if args.get("leagues"):
        return False
    try:
        covered_from, covered_to = date.fromisoformat(args["date_from"]), date.fromisoformat(args["date_to"])
        return covered_from <= start and covered_to >= end - timedelta(days=3)
    except (KeyError, ValueError):
        return False


def _is_backfill(run: ScrapeRun) -> bool:
    args = run.args or {}
    try:
        span = date.fromisoformat(args["date_to"]) - date.fromisoformat(args["date_from"])
        return not args.get("leagues") and span > timedelta(days=60)
    except (KeyError, ValueError):
        return False


async def _start(date_from: date, date_to: date) -> int:
    args = {"leagues": "", "date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "refetch": ""}
    return await _launch("espn_matches", args)


async def _launch(spider: str, args: dict[str, str]) -> int:
    run_id = await asyncio.to_thread(runner.create_run, spider, args)
    await asyncio.to_thread(runner.launch, run_id)
    return run_id


async def cycle(session: AsyncSession, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    auto = await get_auto(session)
    if not auto["enabled"]:
        return {"scraper": "auto off"}

    runs = (await session.execute(select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(200))).scalars().all()
    for run in runs:  # a process that died without reporting back
        if run.status in ACTIVE and not await asyncio.to_thread(runner.pid_alive, run.pid):
            run.status, run.finished_at = "failed", datetime.now(UTC)
            run.message = run.message or "The scraper process ended unexpectedly (see log)."
    report: dict[str, Any] = {}
    # News is quick (10 requests) and runs alongside the match scraper, once an hour.
    for spider in cfg("news.spiders"):
        news = [r for r in runs if r.spider == spider]
        due = not news or datetime.now(UTC) - news[0].created_at >= timedelta(minutes=cfg("news.every_minutes"))
        if due and not any(r.status in ACTIVE for r in news):
            report[spider] = f"run #{await _launch(spider, {})}"

    active = [r for r in runs if r.status in ACTIVE and r.spider == "espn_matches"]
    if active:
        last = _last_load.get("espn")
        if active[0].status == "running" and (last is None or datetime.now(UTC) - last >= timedelta(minutes=cfg("scraper.load_every_minutes"))):
            from backend.scraping.loaders import load_espn

            _last_load["espn"] = datetime.now(UTC)
            loaded = await load_espn(session)
            report["loaded_while_running"] = {k: v for k, v in loaded.items() if k in ("loaded", "waiting_for_links", "skipped")}
        return {**report, "scraper": f"run #{active[0].id} {active[0].status}"}

    finished = [r for r in runs if r.status == "finished" and r.spider == "espn_matches"]
    todo = [(a, b) for a, b in backfill_chunks(today) if not any(_covers(r, a, b) for r in finished)]
    if todo:
        start, end = todo[0]
        run_id = await _start(start, end)
        action = f"history backfill {start} to {end} as run #{run_id} (newest first)"
    else:
        last_recent = max((r.created_at for r in runs if r.spider == "espn_matches" and not _is_backfill(r)),
                          default=None)
        if last_recent and datetime.now(UTC) - last_recent < timedelta(hours=cfg("scraper.recent_every_hours")):
            return {**report, "scraper": "up to date"}
        run_id = await _start(today - timedelta(days=cfg("scraper.recent_days_back")),
                              today + timedelta(days=cfg("scraper.recent_days_ahead")))
        action = f"started run #{run_id} (recent and upcoming matches)"
    await set_auto(session, last_action={"at": datetime.now(UTC).isoformat(), "action": action})
    return {**report, "scraper": action}
