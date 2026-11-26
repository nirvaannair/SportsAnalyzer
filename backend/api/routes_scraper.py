"""Scraper control and visibility: start/stop Scrapy runs and see exactly what they collected."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from backend.core.leagues import LEAGUES_BY_CODE
from backend.database.engine import AsyncSessionFactory
from backend.database.models import MatchPlayer, Player, ScrapedItem, ScrapeRun
from backend.scraping import run as runner

router = APIRouter(prefix="/api/scraper")

SPIDER_INFO = {
    "espn_matches": {
        "label": "ESPN matches & lineups",
        "description": "Match lists, starting XIs, substitutions with minutes, goals, cards, "
                       "player and team stats from ESPN's public feed. Betting odds in the feed are discarded.",
    },
    "espn_news": {
        "label": "ESPN football news",
        "description": "Latest news per league (headline, summary, team and player tags), scored for good/bad "
                       "news and injuries. Runs automatically (Settings: news.every_minutes).",
    },
    "rss_news": {
        "label": "News feeds (RSS)",
        "description": "Football news from the RSS feeds in Settings (news.rss), linked to teams by name and "
                       "scored like the ESPN news.",
    },
}


class StartRun(BaseModel):
    spider: str = "espn_matches"
    leagues: list[str] = Field(default_factory=list)
    date_from: date
    date_to: date
    refetch: bool = False


def _run_json(run: ScrapeRun) -> dict[str, Any]:
    return {
        "id": run.id, "spider": run.spider, "args": run.args, "status": run.status, "stats": run.stats,
        "message": run.message, "created_at": run.created_at, "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


class AutoPatch(BaseModel):
    enabled: bool


@router.get("/auto")
async def get_auto() -> dict[str, Any]:
    from backend.scraping.auto import get_auto as read

    async with AsyncSessionFactory() as session:
        return await read(session)


@router.patch("/auto")
async def set_auto(body: AutoPatch) -> dict[str, Any]:
    from backend.scraping.auto import cycle
    from backend.scraping.auto import set_auto as write

    async with AsyncSessionFactory() as session:
        state = await write(session, enabled=body.enabled)
        if body.enabled:
            await cycle(session)  # start straight away rather than at the next 15-minute tick
        await session.commit()
        return state


@router.get("/spiders")
async def spiders() -> list[dict[str, Any]]:
    return [{"name": name, **info} for name, info in SPIDER_INFO.items()]


@router.get("/runs")
async def runs(limit: int = 30) -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(limit))).scalars().all()
        # A run whose process died without reporting back is marked failed.
        for run in rows:
            if run.status in ("running", "loading") and not await asyncio.to_thread(runner.pid_alive, run.pid):
                run.status, run.finished_at = "failed", datetime.now(UTC)
                run.message = run.message or "The scraper process ended unexpectedly (see log)."
        await session.commit()
    return [_run_json(r) for r in rows]


@router.post("/runs")
async def start_run(body: StartRun) -> dict[str, Any]:
    if body.spider not in SPIDER_INFO:
        raise HTTPException(400, f"Unknown spider {body.spider}")
    unknown = [c for c in body.leagues if c.upper() not in LEAGUES_BY_CODE]
    if unknown:
        raise HTTPException(400, f"Unknown leagues: {', '.join(unknown)}")
    if body.date_from > body.date_to:
        raise HTTPException(400, "date_from must be before date_to")
    async with AsyncSessionFactory() as session:
        busy = (await session.execute(select(func.count()).select_from(ScrapeRun).where(
            ScrapeRun.spider == body.spider, ScrapeRun.status.in_(["queued", "running", "loading"])))).scalar_one()
    if busy:
        raise HTTPException(409, "This scraper is already running. Stop it or wait for it to finish.")

    args = {"leagues": ",".join(c.upper() for c in body.leagues), "date_from": body.date_from.isoformat(),
            "date_to": body.date_to.isoformat(), "refetch": "1" if body.refetch else ""}
    run_id = await asyncio.to_thread(runner.create_run, body.spider, args)
    await asyncio.to_thread(runner.launch, run_id)
    return {"id": run_id}


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: int) -> dict[str, Any]:
    await asyncio.to_thread(runner.stop, run_id)
    return {"ok": True}


@router.get("/runs/{run_id}/log")
async def run_log(run_id: int, lines: int = Query(80, le=500)) -> dict[str, Any]:
    path = runner.log_path(run_id)
    if not path.exists():
        return {"lines": []}
    text = await asyncio.to_thread(path.read_text, "utf-8", "replace")
    noise = ("[scrapy.middleware]", "[scrapy.utils.log]", "[scrapy.addons]", "[scrapy.extensions.telnet]",
             "[scrapy.crawler]", "[py.warnings]")
    useful = [line for line in text.splitlines()
              if line[:4].isdigit() and not any(n in line for n in noise)]
    return {"lines": useful[-lines:]}


def _summary(item: ScrapedItem) -> str:
    d = item.data
    if item.item_type == "fixture":
        score = f"{d['home']['score']}–{d['away']['score']}" if d.get("completed") else "upcoming"
        return f"{d['date']} {d['league']}: {d['home']['name']} {score} {d['away']['name']}"
    if item.item_type == "match_detail":
        names = " v ".join(t["name"] or "?" for t in d.get("teams", []))
        players = sum(len(t["players"]) for t in d.get("teams", []))
        goals = sum(1 for e in d.get("events", []) if "goal" in e["kind"])
        subs = sum(1 for e in d.get("events", []) if e["kind"] == "sub")
        return f"{d.get('date')} {names}: {players} players, {goals} goals, {subs} substitutions"
    return item.key


@router.get("/items")
async def items(run_id: int | None = None, item_type: str | None = None, limit: int = Query(50, le=200),
                offset: int = 0) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        query = select(ScrapedItem)
        if run_id is not None:
            query = query.where(ScrapedItem.run_id == run_id)
        if item_type:
            query = query.where(ScrapedItem.item_type == item_type)
        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
        rows = (await session.execute(query.order_by(ScrapedItem.id.desc()).limit(limit).offset(offset))).scalars().all()
    return {"total": total, "items": [
        {"id": i.id, "run_id": i.run_id, "spider": i.spider, "type": i.item_type, "key": i.key,
         "url": i.source_url, "scraped_at": i.scraped_at, "loaded": i.loaded_at is not None, "summary": _summary(i)}
        for i in rows
    ]}


@router.get("/items/{item_id}")
async def item(item_id: int) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        row = await session.get(ScrapedItem, item_id)
    if row is None:
        raise HTTPException(404, "Item not found")
    return {"id": row.id, "type": row.item_type, "key": row.key, "url": row.source_url, "data": row.data}


@router.get("/totals")
async def totals() -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        by_type = dict((await session.execute(
            select(ScrapedItem.item_type, func.count()).group_by(ScrapedItem.item_type))).all())
        pending = (await session.execute(select(func.count()).select_from(ScrapedItem).where(
            ScrapedItem.item_type == "match_detail", ScrapedItem.loaded_at.is_(None)))).scalar_one()
        players = (await session.execute(select(func.count()).select_from(Player))).scalar_one()
        lineups = (await session.execute(select(func.count(func.distinct(MatchPlayer.match_id))))).scalar_one()
    return {"items_by_type": by_type, "details_waiting_for_team_links": pending,
            "players": players, "matches_with_lineups": lineups}
