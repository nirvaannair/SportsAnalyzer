"""Scrapy spider: matches, lineups, substitutions, events and team stats from ESPN's public feed.

Arguments (all optional):
    leagues    comma-separated league codes, e.g. "ENG1,ESP1" (default: all 10)
    date_from  YYYY-MM-DD (default: 14 days ago)
    date_to    YYYY-MM-DD (default: today)
    refetch    "1" to fetch match details again even if already scraped

Run from the dashboard's Scraper page, or:
    .venv/Scripts/python -m backend.scraping.run --spider espn_matches --date-from 2026-11-01
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import scrapy
from sqlalchemy import select

from backend.core.leagues import LEAGUES, LEAGUES_BY_CODE, League
from backend.core.settings import cfg
from backend.database.models import ScrapedItem
from backend.scraping import espn_parse
from backend.scraping.db import engine


def months_between(start: date, end: date) -> Iterator[str]:
    """Every calendar month touching [start, end], as YYYYMM."""
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield f"{year}{month:02d}"
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def recency_priority(day: str) -> int:
    """Scrapy runs higher priorities first: newer months/matches get higher numbers,
    so the most recent seasons are collected before older ones."""
    digits = day.replace("-", "")[:6]  # YYYYMM
    return (int(digits[:4]) - 2000) * 12 + int(digits[4:6])


class EspnMatchesSpider(scrapy.Spider):
    name = "espn_matches"
    custom_settings = {"DOWNLOAD_DELAY": cfg("scraper.download_delay_seconds")}

    def __init__(self, leagues: str = "", date_from: str = "", date_to: str = "",
                 refetch: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.leagues: list[League] = (
            [LEAGUES_BY_CODE[c.strip().upper()] for c in leagues.split(",") if c.strip()] or list(LEAGUES)
        )
        self.date_to = date.fromisoformat(date_to) if date_to else date.today()
        self.date_from = date.fromisoformat(date_from) if date_from else self.date_to - timedelta(days=14)
        self.refetch = refetch == "1"
        self.already_scraped: set[str] = set()

    async def start(self):
        if not self.refetch:
            with engine().connect() as connection:
                self.already_scraped = set(connection.execute(
                    select(ScrapedItem.key).where(ScrapedItem.spider == self.name,
                                                  ScrapedItem.item_type == "match_detail")
                ).scalars())
        self.logger.info("Leagues %s, %s to %s, %d matches already have details",
                         ",".join(lg.code for lg in self.leagues), self.date_from, self.date_to,
                         len(self.already_scraped))
        # Newest months first (and higher priority), across all leagues.
        months = sorted(months_between(self.date_from, self.date_to), reverse=True)
        for month in months:
            for league in self.leagues:
                yield scrapy.Request(espn_parse.scoreboard_url(league, month), priority=recency_priority(month),
                                     callback=self.parse_scoreboard, cb_kwargs={"league": league})

    def parse_scoreboard(self, response, league: League):
        for fixture in espn_parse.parse_scoreboard(response.json(), league):
            if not (self.date_from.isoformat() <= fixture["date"] <= self.date_to.isoformat()):
                continue
            yield {"item_type": "fixture", "key": fixture["event_id"], "source_url": response.url,
                   "data": fixture}
            if fixture["completed"] and fixture["event_id"] not in self.already_scraped:
                yield scrapy.Request(
                    espn_parse.summary_url(league, fixture["event_id"]),
                    priority=recency_priority(fixture["date"]) + 1,  # finish a month's matches before older months
                    callback=self.parse_summary,
                    cb_kwargs={"league": league, "fixture": fixture},
                )

    def parse_summary(self, response, league: League, fixture: dict[str, Any]):
        detail = espn_parse.parse_summary(response.json(), fixture["event_id"], league)
        detail["date"] = fixture["date"]
        detail["score"] = {"home": fixture["home"]["score"], "away": fixture["away"]["score"]}
        yield {"item_type": "match_detail", "key": fixture["event_id"], "source_url": response.url,
               "data": detail}
