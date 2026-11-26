"""Scrapy settings shared by all SportsAnalyzer spiders. Polite by default."""

from __future__ import annotations

from backend.core.config import PROJECT_ROOT

SCRAPE_DATA_DIR = PROJECT_ROOT / "data" / "scraper"

SETTINGS: dict = {
    "BOT_NAME": "sportsanalyzer",
    "USER_AGENT": "SportsAnalyzer/0.1 (personal research tool)",
    "ROBOTSTXT_OBEY": True,
    # One request at a time per site, at least 2 s apart, slowing down if the site is slow.
    "CONCURRENT_REQUESTS": 4,
    "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    "DOWNLOAD_DELAY": 2.0,
    "AUTOTHROTTLE_ENABLED": True,
    "AUTOTHROTTLE_START_DELAY": 2.0,
    "AUTOTHROTTLE_MAX_DELAY": 30.0,
    "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
    "RETRY_TIMES": 3,
    # 429/503 are not retried immediately: the crawl pauses until the site is ready again.
    "RETRY_HTTP_CODES": [500, 502, 504, 522, 524, 408],
    "DOWNLOADER_MIDDLEWARES": {"backend.scraping.middleware.RateLimitWaitMiddleware": 560},
    # Each page is downloaded once and kept on disk, so re-runs and re-parsing cost nothing.
    "HTTPCACHE_ENABLED": True,
    "HTTPCACHE_DIR": str(SCRAPE_DATA_DIR / "httpcache"),
    "HTTPCACHE_EXPIRATION_SECS": 0,
    "HTTPCACHE_IGNORE_HTTP_CODES": [403, 404, 429, 500, 502, 503, 504],
    "HTTPCACHE_POLICY": "backend.scraping.settings.CacheFinishedOnly",
    "ITEM_PIPELINES": {"backend.scraping.pipeline.SaveItemsPipeline": 300},
    "EXTENSIONS": {"backend.scraping.pipeline.RunStatsExtension": 500},
    "SPIDER_MODULES": ["backend.scraping.spiders"],
    "LOG_LEVEL": "INFO",
    "TELNETCONSOLE_ENABLED": False,
}


from scrapy.extensions.httpcache import DummyPolicy  # noqa: E402


class CacheFinishedOnly(DummyPolicy):
    """Cache match details forever, but always re-download scoreboards (they change as games finish)."""

    def should_cache_request(self, request):
        return "/summary?" in request.url and super().should_cache_request(request)
