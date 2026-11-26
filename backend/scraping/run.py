"""Run one Scrapy crawl as its own process, then load what it scraped.

Started by the dashboard (POST /api/scraper/runs), or by hand:
    .venv/Scripts/python -m backend.scraping.run --spider espn_matches --date-from 2026-11-01
    .venv/Scripts/python -m backend.scraping.run --run-id 12      # a run created by the API
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

from backend.core.config import PROJECT_ROOT
from backend.database.models import ScrapeRun
from backend.scraping.db import engine
from backend.scraping.settings import SCRAPE_DATA_DIR, SETTINGS

SPIDERS = {"espn_matches": "backend.scraping.spiders.espn_matches.EspnMatchesSpider",
           "espn_news": "backend.scraping.spiders.espn_news.EspnNewsSpider",
           "rss_news": "backend.scraping.spiders.rss_news.RssNewsSpider"}
LOG_DIR = SCRAPE_DATA_DIR / "logs"


def log_path(run_id: int) -> Path:
    return LOG_DIR / f"run_{run_id}.log"


def _set(run_id: int, **values: Any) -> None:
    with engine().begin() as connection:
        connection.execute(update(ScrapeRun).where(ScrapeRun.id == run_id).values(**values))


def create_run(spider: str, args: dict[str, str]) -> int:
    if spider not in SPIDERS:
        raise ValueError(f"Unknown spider {spider!r}; choose from {', '.join(SPIDERS)}")
    with engine().begin() as connection:
        return connection.execute(
            ScrapeRun.__table__.insert().values(spider=spider, args=args, status="queued").returning(ScrapeRun.id)
        ).scalar_one()


def launch(run_id: int) -> int:
    """Start the crawl in a background process. Returns its process id."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with open(log_path(run_id), "ab") as log:
        process = subprocess.Popen([sys.executable, "-m", "backend.scraping.run", "--run-id", str(run_id)],
                                   cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    _set(run_id, pid=process.pid)
    return process.pid


def stop(run_id: int) -> None:
    with engine().connect() as connection:
        run = connection.execute(select(ScrapeRun.pid, ScrapeRun.status).where(ScrapeRun.id == run_id)).one()
    if run.pid and run.status in ("queued", "running", "loading"):
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(run.pid), "/T", "/F"], capture_output=True, check=False)
            else:
                os.kill(run.pid, 15)
        except OSError:
            pass
    _set(run_id, status="stopped", finished_at=datetime.now(UTC), message="Stopped from the dashboard")


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _crawl(run_id: int, spider: str, args: dict[str, str]) -> None:
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.misc import load_object

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    settings = {**SETTINGS, "SA_RUN_ID": run_id, "LOG_FILE": str(log_path(run_id)), "LOG_FILE_APPEND": True}
    process = CrawlerProcess(settings)
    process.crawl(load_object(SPIDERS[spider]), **args)
    process.start()


async def _load(spider: str) -> dict[str, Any]:
    from backend.database.engine import AsyncSessionFactory, dispose_database_engine
    from backend.scraping.loaders import load_espn
    from backend.scraping.news_loader import load_news

    try:
        async with AsyncSessionFactory() as session:
            loaders = {"espn_matches": load_espn, "espn_news": load_news, "rss_news": load_news}
            result = await loaders[spider](session) if spider in loaders else {}
            await session.commit()
        return result
    finally:
        await dispose_database_engine()


def execute(run_id: int) -> None:
    with engine().connect() as connection:
        run = connection.execute(select(ScrapeRun.spider, ScrapeRun.args).where(ScrapeRun.id == run_id)).one()
    _set(run_id, status="running", started_at=datetime.now(UTC), pid=os.getpid())
    try:
        _crawl(run_id, run.spider, {k: str(v) for k, v in (run.args or {}).items() if v not in (None, "")})
        _set(run_id, status="loading")
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        loaded = asyncio.run(_load(run.spider))
        with engine().connect() as connection:
            stats = connection.execute(select(ScrapeRun.stats).where(ScrapeRun.id == run_id)).scalar_one()
        _set(run_id, status="finished", finished_at=datetime.now(UTC), stats={**(stats or {}), "loaded": loaded})
    except Exception as exc:  # recorded for the dashboard, then re-raised into the log
        _set(run_id, status="failed", finished_at=datetime.now(UTC), message=f"{type(exc).__name__}: {exc}")
        raise


def main() -> None:
    from dotenv import load_dotenv

    from backend.core.config import ENV_FILE

    load_dotenv(ENV_FILE)
    parser = argparse.ArgumentParser(prog="python -m backend.scraping.run")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--spider", default="espn_matches")
    parser.add_argument("--leagues", default="")
    parser.add_argument("--date-from", default="")
    parser.add_argument("--date-to", default="")
    parser.add_argument("--refetch", action="store_true")
    a = parser.parse_args()
    run_id = a.run_id or create_run(a.spider, {"leagues": a.leagues, "date_from": a.date_from,
                                               "date_to": a.date_to, "refetch": "1" if a.refetch else ""})
    print(f"Scrape run {run_id}: log at {log_path(run_id)}", flush=True)
    execute(run_id)
    print(f"Scrape run {run_id} finished.", flush=True)


if __name__ == "__main__":
    main()
