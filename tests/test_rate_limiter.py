import pytest

from backend.integrations.rate_limiter import ProviderRateLimiter


def test_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        ProviderRateLimiter(provider_name=" ")
    with pytest.raises(ValueError):
        ProviderRateLimiter(provider_name="x", requests_per_minute=0)


async def test_counts_requests_within_limit() -> None:
    limiter = ProviderRateLimiter(provider_name="API_Football", requests_per_minute=5)
    for _ in range(3):
        await limiter.acquire()
    snapshot = await limiter.snapshot()
    assert snapshot.provider_name == "api_football"
    assert snapshot.requests_in_current_minute == 3


async def test_blocks_when_window_is_full() -> None:
    limiter = ProviderRateLimiter(provider_name="x", requests_per_minute=2)
    await limiter.acquire()
    await limiter.acquire()
    async with limiter._lock:
        from datetime import UTC, datetime

        wait = limiter._required_wait(datetime.now(UTC))
    assert 55 < wait <= 60


async def test_records_quota_headers_case_insensitively() -> None:
    limiter = ProviderRateLimiter(provider_name="x")
    await limiter.record_response(
        response_headers={
            "X-RateLimit-Requests-Remaining": "97",
            "x-ratelimit-requests-limit": "100",
            "Retry-After": "not-a-number",
        }
    )
    snapshot = await limiter.snapshot()
    assert snapshot.observed_requests_remaining == 97
    assert snapshot.observed_requests_limit == 100
    assert snapshot.retry_after_seconds is None
