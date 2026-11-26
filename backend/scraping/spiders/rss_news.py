"""Scrapy spider: football news from RSS feeds listed in config/settings.toml ([[news.rss]]).

RSS is published for automated readers; each feed's robots.txt allows it. Only the headline,
summary, date and link are kept. Teams are linked later by name (backend/scraping/news_loader.py).
"""

from __future__ import annotations

import hashlib
from email.utils import parsedate_to_datetime
from typing import Any

import scrapy

from backend.core.settings import cfg


def parse_feed(xml_items: list[dict[str, str]], feed: str) -> list[dict[str, Any]]:
    """Items as {title, description, link, guid, pubDate} -> our article records."""
    out = []
    for item in xml_items:
        title, published = (item.get("title") or "").strip(), item.get("pubDate")
        if not title or not published:
            continue
        try:
            when = parsedate_to_datetime(published).isoformat()
        except (TypeError, ValueError):
            continue
        link = (item.get("link") or "").strip() or None
        key = item.get("guid") or link or title
        out.append({
            "id": f"{feed}:{hashlib.sha1(key.encode()).hexdigest()[:20]}", "source": feed, "league": None,
            "published": when, "headline": title, "summary": (item.get("description") or "").strip() or None,
            "url": link, "teams": [], "players": [], "topics": [],
        })
    return out


class RssNewsSpider(scrapy.Spider):
    name = "rss_news"
    custom_settings = {"DOWNLOAD_DELAY": cfg("scraper.download_delay_seconds"), "HTTPCACHE_ENABLED": False}

    async def start(self):
        for feed in cfg("news.rss"):
            yield scrapy.Request(feed["url"], callback=self.parse, cb_kwargs={"feed": feed["name"]})

    def parse(self, response, feed: str):
        response.selector.remove_namespaces()
        items = [{field: node.xpath(f"string({field})").get() for field in ("title", "description", "link", "guid", "pubDate")}
                 for node in response.xpath("//item")]
        for article in parse_feed(items, feed):
            yield {"item_type": "news", "key": article["id"], "source_url": response.url, "data": article}
