"""Scrapy spider: latest football news per league from ESPN's public JSON feed.

One request per league (10 per run). Each article carries ESPN's own team and player tags,
so it links to our teams/players through the same IDs as the match scraper. Only the
headline, summary, date, link and tags are kept; nothing about betting.
"""

from __future__ import annotations

from typing import Any

import scrapy

from backend.core.leagues import LEAGUES, LEAGUES_BY_CODE

NEWS_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/news?limit=100"


def parse_articles(payload: dict[str, Any], league_code: str) -> list[dict[str, Any]]:
    out = []
    for a in payload.get("articles") or []:
        if not a.get("id") or not a.get("headline") or not a.get("published"):
            continue
        teams, players, topics = [], [], []
        for c in a.get("categories") or []:
            kind = c.get("type")
            if kind == "team":
                team_id = c.get("teamId") or (c.get("team") or {}).get("id")
                if team_id:
                    teams.append({"id": str(team_id), "name": c.get("description") or ""})
            elif kind == "athlete":
                athlete_id = c.get("athleteId") or (c.get("athlete") or {}).get("id")
                if athlete_id:
                    players.append({"id": str(athlete_id), "name": c.get("description") or ""})
            elif kind == "topic" and c.get("description"):
                topics.append(c["description"])
        link = ((a.get("links") or {}).get("web") or {}).get("href")
        out.append({
            "id": str(a["id"]), "league": league_code, "published": a["published"],
            "headline": a["headline"], "summary": a.get("description"), "url": link,
            "teams": teams, "players": players, "topics": topics,
        })
    return out


class EspnNewsSpider(scrapy.Spider):
    name = "espn_news"
    custom_settings = {"DOWNLOAD_DELAY": 2.0, "HTTPCACHE_ENABLED": False}  # news changes all the time

    def __init__(self, leagues: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        codes = [c.strip().upper() for c in leagues.split(",") if c.strip()]
        self.leagues = [LEAGUES_BY_CODE[c] for c in codes] if codes else list(LEAGUES)

    async def start(self):  # Scrapy 2.13+ entry point
        for league in self.leagues:
            yield scrapy.Request(NEWS_URL.format(slug=league.espn_slug), callback=self.parse,
                                 cb_kwargs={"league_code": league.code})

    def parse(self, response, league_code: str):
        for article in parse_articles(response.json(), league_code):
            yield {"item_type": "news", "key": article["id"], "source_url": response.url, "data": article}
