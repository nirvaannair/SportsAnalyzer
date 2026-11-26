"""Scrapy settings shared by all SportsAnalyzer spiders. Polite by default."""

from __future__ import annotations

from backend.core.config import PROJECT_ROOT
from backend.core.settings import cfg

SCRAPE_DATA_DIR = PROJECT_ROOT / "data" / "scraper"

SETTINGS: dict = {
    "BOT_NAME": "sportsanalyzer",
    "USER_AGENT": cfg("app.user_agent"),
    "ROBOTSTXT_OBEY": True,
    # Polite by default: request gaps and concurrency come from [scraper] in config/settings.toml.
    "CONCURRENT_REQUESTS": cfg("scraper.concurrent_requests"),
    "CONCURRENT_REQUESTS_PER_DOMAIN": cfg("scraper.concurrent_requests_per_site"),
    "DOWNLOAD_DELAY": cfg("scraper.download_delay_seconds"),
    "AUTOTHROTTLE_ENABLED": True,
    "AUTOTHROTTLE_START_DELAY": cfg("scraper.download_delay_seconds"),
    "AUTOTHROTTLE_MAX_DELAY": cfg("scraper.autothrottle_max_delay_seconds"),
    "AUTOTHROTTLE_TARGET_CONCURRENCY": cfg("scraper.concurrent_requests_per_site"),
    "RETRY_TIMES": cfg("scraper.retry_times"),
    # 429/503 are not retried immediately: the crawl pauses until the site is ready again.
    "RETRY_HTTP_CODES": cfg("scraper.retry_codes"),
    "DOWNLOADER_MIDDLEWARES": {
        "backend.scraping.middleware.RateLimitWaitMiddleware": cfg("scraper.component_order.rate_limit_wait")},
    # Each page is downloaded once and kept on disk, so re-runs and re-parsing cost nothing.
    "HTTPCACHE_ENABLED": True,
    "HTTPCACHE_DIR": str(SCRAPE_DATA_DIR / "httpcache"),
    "HTTPCACHE_EXPIRATION_SECS": cfg("scraper.cache_expiry_seconds"),
    "HTTPCACHE_IGNORE_HTTP_CODES": cfg("scraper.never_cache_codes"),
    "HTTPCACHE_POLICY": "backend.scraping.settings.CacheFinishedOnly",
    "ITEM_PIPELINES": {"backend.scraping.pipeline.SaveItemsPipeline": cfg("scraper.component_order.save_items")},
    "EXTENSIONS": {"backend.scraping.pipeline.RunStatsExtension": cfg("scraper.component_order.run_stats")},
    "SPIDER_MODULES": ["backend.scraping.spiders"],
    "LOG_LEVEL": "INFO",
    "TELNETCONSOLE_ENABLED": False,
}


from scrapy.extensions.httpcache import DummyPolicy  # noqa: E402


class CacheFinishedOnly(DummyPolicy):
    """Cache match details forever, but always re-download scoreboards (they change as games finish)."""

    def should_cache_request(self, request):
        return "/summary?" in request.url and super().should_cache_request(request)
