from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class RateLimitSnapshot:
    """
    Immutable snapshot of locally enforced and provider-observed limits.

    None means that the corresponding limit is not known or configured.
    The limiter never invents provider limits.
    """

    provider_name: str
    observed_at: datetime

    configured_requests_per_second: float | None = None
    configured_requests_per_minute: int | None = None
    configured_requests_per_hour: int | None = None
    configured_requests_per_day: int | None = None

    observed_requests_remaining: int | None = None
    observed_requests_limit: int | None = None
    observed_rate_limit_remaining: int | None = None
    observed_rate_limit_limit: int | None = None
    retry_after_seconds: float | None = None

    requests_in_current_minute: int = 0
    requests_in_current_hour: int = 0
    requests_in_current_day: int = 0

    metadata: Mapping[str, str] = field(default_factory=dict)


class ProviderRateLimiter:
    """
    Async request governor for one external provider.

    The limiter is deliberately provider-agnostic. It knows only about
    request timing, configured limits, and provider-observed quota headers.

    It does not know about fixtures, teams, players, markets, predictions,
    or betting decisions.

    A request must call acquire() before execution and record_response() after
    the provider responds. This makes the limiter reusable by every provider
    adapter in SportsAnalyzer.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        requests_per_second: float | None = None,
        requests_per_minute: int | None = None,
        requests_per_hour: int | None = None,
        requests_per_day: int | None = None,
    ) -> None:
        normalized_name = provider_name.strip().lower()

        if not normalized_name:
            raise ValueError("Provider name must not be empty.")

        if requests_per_second is not None and requests_per_second <= 0:
            raise ValueError("requests_per_second must be greater than zero.")

        for field_name, value in (
            ("requests_per_minute", requests_per_minute),
            ("requests_per_hour", requests_per_hour),
            ("requests_per_day", requests_per_day),
        ):
            if value is not None and value <= 0:
                raise ValueError(
                    f"{field_name} must be greater than zero."
                )

        self._provider_name = normalized_name

        self._requests_per_second = requests_per_second
        self._requests_per_minute = requests_per_minute
        self._requests_per_hour = requests_per_hour
        self._requests_per_day = requests_per_day

        self._request_times: deque[datetime] = deque()
        self._lock = asyncio.Lock()

        self._observed_requests_remaining: int | None = None
        self._observed_requests_limit: int | None = None
        self._observed_rate_limit_remaining: int | None = None
        self._observed_rate_limit_limit: int | None = None
        self._retry_after_seconds: float | None = None
        self._metadata: dict[str, str] = {}
        self._last_observed_at: datetime | None = None

    @property
    def provider_name(self) -> str:
        """Return the normalized provider name."""
        return self._provider_name

    async def acquire(self) -> None:
        """
        Wait until one request is permitted by the configured limits.

        The request is recorded only after permission is granted. This means
        failed HTTP requests still count as requests once record_response()
        is called by the adapter.
        """
        while True:
            async with self._lock:
                now = datetime.now(UTC)
                self._prune(now)

                delay = self._required_wait(now)

                if delay <= 0:
                    self._request_times.append(now)
                    return

            await asyncio.sleep(delay)

    async def record_response(
        self,
        *,
        response_headers: Mapping[str, str],
    ) -> None:
        """
        Record provider-observed quota and rate-limit headers.

        Header names are matched case-insensitively. Unknown or malformed
        values are ignored rather than converted into fabricated numbers.
        """
        normalized_headers = {
            key.strip().lower(): value.strip()
            for key, value in response_headers.items()
        }

        async with self._lock:
            self._observed_requests_remaining = self._parse_int(
                normalized_headers.get("x-ratelimit-requests-remaining")
            )
            self._observed_requests_limit = self._parse_int(
                normalized_headers.get("x-ratelimit-requests-limit")
            )
            self._observed_rate_limit_remaining = self._parse_int(
                normalized_headers.get("x-ratelimit-remaining")
            )
            self._observed_rate_limit_limit = self._parse_int(
                normalized_headers.get("x-ratelimit-limit")
            )
            self._retry_after_seconds = self._parse_float(
                normalized_headers.get("retry-after")
            )
            self._metadata = dict(normalized_headers)
            self._last_observed_at = datetime.now(UTC)

    async def snapshot(self) -> RateLimitSnapshot:
        """Return the current limiter state without making a request."""
        async with self._lock:
            now = datetime.now(UTC)
            self._prune(now)

            return RateLimitSnapshot(
                provider_name=self._provider_name,
                observed_at=self._last_observed_at or now,
                configured_requests_per_second=self._requests_per_second,
                configured_requests_per_minute=self._requests_per_minute,
                configured_requests_per_hour=self._requests_per_hour,
                configured_requests_per_day=self._requests_per_day,
                observed_requests_remaining=self._observed_requests_remaining,
                observed_requests_limit=self._observed_requests_limit,
                observed_rate_limit_remaining=self._observed_rate_limit_remaining,
                observed_rate_limit_limit=self._observed_rate_limit_limit,
                retry_after_seconds=self._retry_after_seconds,
                requests_in_current_minute=self._count_since(
                    now,
                    timedelta(minutes=1),
                ),
                requests_in_current_hour=self._count_since(
                    now,
                    timedelta(hours=1),
                ),
                requests_in_current_day=self._count_since(
                    now,
                    timedelta(days=1),
                ),
                metadata=dict(self._metadata),
            )

    async def reset_observed_state(self) -> None:
        """
        Clear provider-observed header state.

        Local request history is intentionally preserved because clearing it
        could cause the application to violate its configured limits.
        """
        async with self._lock:
            self._observed_requests_remaining = None
            self._observed_requests_limit = None
            self._observed_rate_limit_remaining = None
            self._observed_rate_limit_limit = None
            self._retry_after_seconds = None
            self._metadata = {}
            self._last_observed_at = None

    def _required_wait(self, now: datetime) -> float:
        """
        Calculate the minimum delay before another request is allowed.
        """
        delays: list[float] = []

        if self._requests_per_second is not None:
            interval = 1.0 / self._requests_per_second

            if self._request_times:
                elapsed = (
                    now - self._request_times[-1]
                ).total_seconds()
                delays.append(max(0.0, interval - elapsed))

        for limit, window in (
            (
                self._requests_per_minute,
                timedelta(minutes=1),
            ),
            (
                self._requests_per_hour,
                timedelta(hours=1),
            ),
            (
                self._requests_per_day,
                timedelta(days=1),
            ),
        ):
            if limit is None:
                continue

            timestamps = self._timestamps_within_window(
                now,
                window,
            )

            if len(timestamps) < limit:
                continue

            oldest = timestamps[0]
            wait_until = oldest + window
            delays.append(
                max(
                    0.0,
                    (wait_until - now).total_seconds(),
                )
            )

        return max(delays, default=0.0)

    def _prune(self, now: datetime) -> None:
        """Remove request timestamps outside the largest configured window."""
        windows = [
            window
            for limit, window in (
                (
                    self._requests_per_minute,
                    timedelta(minutes=1),
                ),
                (
                    self._requests_per_hour,
                    timedelta(hours=1),
                ),
                (
                    self._requests_per_day,
                    timedelta(days=1),
                ),
            )
            if limit is not None
        ]

        if not windows:
            return

        cutoff = now - max(windows)

        while self._request_times and self._request_times[0] <= cutoff:
            self._request_times.popleft()

    def _timestamps_within_window(
        self,
        now: datetime,
        window: timedelta,
    ) -> list[datetime]:
        cutoff = now - window
        return [
            timestamp
            for timestamp in self._request_times
            if timestamp > cutoff
        ]

    def _count_since(
        self,
        now: datetime,
        window: timedelta,
    ) -> int:
        cutoff = now - window
        return sum(
            timestamp > cutoff
            for timestamp in self._request_times
        )

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_float(value: str | None) -> float | None:
        if value is None:
            return None

        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None

        if parsed < 0:
            return None

        return parsed