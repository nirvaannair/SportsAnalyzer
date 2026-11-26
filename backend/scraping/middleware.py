"""Wait out rate limits instead of failing.

When a site answers 429 (too many requests) or 503 (overloaded), the whole crawl is paused
for as long as the site asks (Retry-After header) or, without one, 1 minute doubling up to
15 minutes. Then the same request is tried again. Pages are never dropped because of a
rate limit; the pause shows in the run log and on the Scraper page.
"""

from __future__ import annotations

import logging

from twisted.internet import reactor

log = logging.getLogger(__name__)

WAIT_CODES = (429, 503)
FIRST_WAIT_S = 60.0
MAX_WAIT_S = 15 * 60.0
MAX_WAITS_PER_REQUEST = 12  # about 2.5 hours of waiting for one page before giving up on it


def retry_after_seconds(value: bytes | str | None) -> float | None:
    if not value:
        return None
    text = value.decode() if isinstance(value, bytes) else value
    try:
        return max(1.0, float(text.strip()))
    except ValueError:
        return None  # HTTP-date form: fall back to our own backoff


class RateLimitWaitMiddleware:
    def __init__(self, crawler) -> None:
        self.crawler = crawler
        self.wait_s = FIRST_WAIT_S
        self.paused = False

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_response(self, request, response, spider):
        if response.status not in WAIT_CODES:
            self.wait_s = FIRST_WAIT_S  # the site is happy again
            return response
        waits = request.meta.get("rate_limit_waits", 0)
        if waits >= MAX_WAITS_PER_REQUEST:
            log.warning("Still rate limited after %d waits, giving up on %s", waits, request.url)
            return response
        delay = retry_after_seconds(response.headers.get("Retry-After")) or self.wait_s
        delay = min(delay, MAX_WAIT_S)
        self.wait_s = min(self.wait_s * 2, MAX_WAIT_S)
        self._pause(delay, response.status)
        self.crawler.stats.inc_value("rate_limit_waits")
        retry = request.replace(dont_filter=True)
        retry.meta["rate_limit_waits"] = waits + 1
        return retry

    def _pause(self, delay: float, status: int) -> None:
        if self.paused:
            return
        self.paused = True
        log.warning("Rate limited (HTTP %s): pausing the crawl for %.0f s, then continuing", status, delay)
        self.crawler.engine.pause()

        def resume() -> None:
            self.paused = False
            self.crawler.engine.unpause()
            log.info("Resuming after the rate-limit pause")

        reactor.callLater(delay, resume)
