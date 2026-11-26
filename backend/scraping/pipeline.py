"""Scrapy item pipeline and stats extension: every scraped item is saved and visible on the dashboard."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from scrapy import signals
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from twisted.internet import task

from backend.database.models import ScrapedItem, ScrapeRun
from backend.scraping.db import engine

_BETTING = re.compile(r"odd|pickcenter|betting|bookmaker|moneyline|spread|overunder", re.I)


def assert_no_betting_data(data: Any, path: str = "") -> None:
    """Scraped football data must never carry odds into the database (README §5.0)."""
    if isinstance(data, dict):
        for key, value in data.items():
            if _BETTING.search(str(key)):
                raise ValueError(f"Betting field {path}{key!r} in scraped item")
            assert_no_betting_data(value, f"{path}{key}.")
    elif isinstance(data, list):
        for value in data:
            assert_no_betting_data(value, path)


class SaveItemsPipeline:
    """Upsert each item into scraped_items (one row per spider/type/key)."""

    def __init__(self, run_id: int | None) -> None:
        self.run_id = run_id

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.getint("SA_RUN_ID") or None)

    def process_item(self, item: dict[str, Any], spider):
        assert_no_betting_data(item["data"])
        statement = insert(ScrapedItem).values(
            run_id=self.run_id, spider=spider.name, item_type=item["item_type"], key=item["key"],
            source_url=item["source_url"], data=item["data"],
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_scraped_items_key",
            set_={"run_id": statement.excluded.run_id, "data": statement.excluded.data,
                  "source_url": statement.excluded.source_url, "scraped_at": datetime.now(UTC),
                  "loaded_at": None},
        )
        with engine().begin() as connection:
            connection.execute(statement)
        spider.crawler.stats.inc_value(f"sa/items/{item['item_type']}")
        return item


class RunStatsExtension:
    """Copies Scrapy's live counters into scrape_runs.stats every few seconds."""

    def __init__(self, crawler) -> None:
        self.crawler = crawler
        self.run_id = crawler.settings.getint("SA_RUN_ID") or None
        self.loop = task.LoopingCall(self.flush)

    @classmethod
    def from_crawler(cls, crawler):
        extension = cls(crawler)
        crawler.signals.connect(extension.opened, signal=signals.spider_opened)
        crawler.signals.connect(extension.closed, signal=signals.spider_closed)
        return extension

    def opened(self, spider) -> None:
        if self.run_id:
            self.loop.start(3.0, now=True)

    def closed(self, spider, reason) -> None:
        if self.loop.running:
            self.loop.stop()
        self.flush(reason)

    def flush(self, reason: str | None = None) -> None:
        if not self.run_id:
            return
        raw = self.crawler.stats.get_stats()
        stats = {
            "requests": raw.get("downloader/request_count", 0),
            "responses": raw.get("downloader/response_count", 0),
            "cached": raw.get("httpcache/hit", 0),
            "items": raw.get("item_scraped_count", 0),
            "items_by_type": {k.split("/")[-1]: v for k, v in raw.items() if k.startswith("sa/items/")},
            "errors": raw.get("log_count/ERROR", 0),
            "rate_limit_waits": raw.get("rate_limit_waits", 0),
            "http_errors": {k.split("/")[-1]: v for k, v in raw.items()
                            if k.startswith("downloader/response_status_count/") and not k.endswith("/200")},
            "finish_reason": reason,
        }
        with engine().begin() as connection:
            connection.execute(update(ScrapeRun).where(ScrapeRun.id == self.run_id)
                               .values(stats=json.loads(json.dumps(stats, default=str))))
