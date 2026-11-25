from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import aiohttp

from .base import (
    ProviderAdapter,
    ProviderCapability,
    ProviderEntityType,
    ProviderHealth,
    ProviderQuotaSnapshot,
    ProviderRequestContext,
    ProviderRequestStatus,
    ProviderResponse,
)
from .config import ProviderConfig
from .rate_limiter import ProviderRateLimiter


class ApiFootballAdapter(ProviderAdapter):
    """
    Provider adapter for API-Football.

    This class is responsible only for communicating with API-Football and
    returning provider-level responses.

    It deliberately does not:
    - create canonical entities
    - resolve provider IDs
    - normalize teams, players, competitions, or matches
    - calculate sports features
    - make prediction decisions
    - make betting decisions

    All provider-specific identifiers remain provider-scoped.

    Request execution is protected by a provider-specific rate limiter so
    configured provider limits are respected locally before requests are sent.
    """

    _PROVIDER_NAME = "api_football"

    _API_KEY_HEADER = "x-apisports-key"

    _QUOTA_REMAINING_HEADER = "x-ratelimit-requests-remaining"
    _QUOTA_LIMIT_HEADER = "x-ratelimit-requests-limit"

    _RATE_LIMIT_REMAINING_HEADER = "x-ratelimit-remaining"
    _RATE_LIMIT_LIMIT_HEADER = "x-ratelimit-limit"

    _RETRY_AFTER_HEADER = "retry-after"

    _RETRYABLE_HTTP_STATUSES = frozenset(
        {
            408,
            425,
            429,
            500,
            502,
            503,
            504,
        }
    )

    _STATUS_ENDPOINT = "status"

    def __init__(
        self,
        config: ProviderConfig,
    ) -> None:
        """
        Initialize the API-Football adapter.

        Args:
            config:
                Provider-specific runtime configuration.

        Raises:
            ValueError:
                If the configuration does not contain a usable base URL or
                API key.
        """
        if config.name != self._PROVIDER_NAME:
            raise ValueError(
                "ApiFootballAdapter requires a provider configuration "
                "named 'api_football'."
            )

        if not config.base_url or not config.base_url.strip():
            raise ValueError(
                "API-Football base URL must be configured."
            )

        if not config.api_key or not config.api_key.strip():
            raise ValueError(
                "API-Football API key must be configured."
            )

        self._config = config
        self._base_url = config.base_url.rstrip("/")
        self._api_key = config.api_key.strip()

        self._session: aiohttp.ClientSession | None = None

        self._latest_quota: ProviderQuotaSnapshot | None = None

        self._request_lock = asyncio.Lock()

        self._rate_limiter = ProviderRateLimiter(
            provider_name=self.name,
            requests_per_second=(
                config.rate_limit.requests_per_second
            ),
            requests_per_minute=(
                config.rate_limit.requests_per_minute
            ),
            requests_per_hour=(
                config.rate_limit.requests_per_hour
            ),
            requests_per_day=(
                config.rate_limit.requests_per_day
            ),
        )

    @property
    def name(self) -> str:
        """Return the stable internal provider name."""
        return self._PROVIDER_NAME

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        """
        Return capabilities exposed by API-Football.

        These are application capabilities, not hard-coded real-world data.
        Availability for a particular competition or season must still be
        determined from the provider's actual response.
        """
        return frozenset(
            {
                ProviderCapability.SPORTS,
                ProviderCapability.TEAMS,
                ProviderCapability.PLAYERS,
                ProviderCapability.COMPETITIONS,
                ProviderCapability.SEASONS,
                ProviderCapability.MATCHES,
                ProviderCapability.LINEUPS,
                ProviderCapability.PLAYER_STATISTICS,
                ProviderCapability.TEAM_STATISTICS,
                ProviderCapability.PLAYER_TRANSFERS,
                ProviderCapability.PLAYER_INJURIES,
                ProviderCapability.ODDS,
            }
        )

    async def initialize(self) -> None:
        """
        Initialize the reusable HTTP session.
        """
        if self._session is not None and not self._session.closed:
            return

        timeout = aiohttp.ClientTimeout(
            total=self._config.request_timeout_seconds
        )

        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                self._API_KEY_HEADER: self._api_key,
            },
        )

    async def close(self) -> None:
        """
        Close the reusable HTTP session.
        """
        if self._session is None:
            return

        if not self._session.closed:
            await self._session.close()

        self._session = None

    async def health_check(self) -> ProviderHealth:
        """
        Check API-Football availability.

        This performs an actual provider request and therefore consumes one
        API request.
        """
        checked_at = datetime.now(UTC)

        context = self._build_context(
            endpoint=self._STATUS_ENDPOINT,
            parameters={},
        )

        try:
            response = await self.fetch(context)
        except Exception as exc:
            return ProviderHealth(
                provider_name=self.name,
                checked_at=checked_at,
                available=False,
                status=ProviderRequestStatus.UNKNOWN_ERROR,
                message=str(exc),
            )

        return ProviderHealth(
            provider_name=self.name,
            checked_at=checked_at,
            available=response.succeeded,
            status=response.status,
            message=response.error_message,
        )

    async def get_quota_snapshot(self) -> ProviderQuotaSnapshot:
        """
        Return the latest provider quota and rate-limit information.

        This method does not consume an API request.
        """
        if self._latest_quota is not None:
            return self._latest_quota

        return ProviderQuotaSnapshot(
            provider_name=self.name,
            observed_at=datetime.now(UTC),
        )

    async def fetch(
        self,
        context: ProviderRequestContext,
    ) -> ProviderResponse:
        """
        Execute one GET request against API-Football.

        The endpoint and parameters come from the caller.

        No real-world endpoint parameters are embedded into this adapter.

        The complete decoded JSON response is returned unchanged.

        Requests pass through the local provider rate limiter before being
        sent.

        Retry behavior is limited to transient HTTP and network failures.
        Provider-level API errors are returned rather than being fabricated
        into successful responses.
        """
        if context.provider_name != self.name:
            raise ValueError(
                "Provider request context does not belong to API-Football."
            )

        if not context.endpoint.strip():
            raise ValueError(
                "Provider endpoint must not be empty."
            )

        await self.initialize()

        if self._session is None:
            raise RuntimeError(
                "API-Football HTTP session was not initialized."
            )

        request_id = context.request_id or str(uuid4())

        request_context = ProviderRequestContext(
            provider_name=self.name,
            endpoint=context.endpoint.strip().lstrip("/"),
            requested_at=context.requested_at,
            request_id=request_id,
            entity_type=context.entity_type,
            provider_entity_id=context.provider_entity_id,
            parameters=dict(context.parameters),
        )

        last_exception: Exception | None = None

        for attempt in range(
            1,
            self._config.retry.max_attempts + 1,
        ):
            try:
                return await self._execute_request(
                    request_context
                )

            except aiohttp.ClientResponseError as exc:
                last_exception = exc

                if (
                    exc.status not in self._RETRYABLE_HTTP_STATUSES
                    or attempt >= self._config.retry.max_attempts
                ):
                    return ProviderResponse(
                        context=request_context,
                        status=self._status_from_http_error(
                            exc.status
                        ),
                        payload=None,
                        received_at=datetime.now(
                            UTC
                        ),
                        http_status=exc.status,
                        error_message=str(exc),
                    )

            except (TimeoutError, aiohttp.ClientConnectionError, aiohttp.ClientConnectorError) as exc:
                last_exception = exc

                if attempt >= self._config.retry.max_attempts:
                    return ProviderResponse(
                        context=request_context,
                        status=ProviderRequestStatus.NETWORK_ERROR,
                        payload=None,
                        received_at=datetime.now(
                            UTC
                        ),
                        error_message=str(exc),
                    )

            if attempt < self._config.retry.max_attempts:
                delay = self._calculate_backoff(attempt)
                await asyncio.sleep(delay)

        return ProviderResponse(
            context=request_context,
            status=ProviderRequestStatus.UNKNOWN_ERROR,
            payload=None,
            received_at=datetime.now(UTC),
            error_message=(
                str(last_exception)
                if last_exception is not None
                else (
                    "Provider request failed without "
                    "an exception."
                )
            ),
        )

    async def _execute_request(
        self,
        context: ProviderRequestContext,
    ) -> ProviderResponse:
        """
        Execute one HTTP request attempt.

        The local rate limiter is acquired immediately before the request.

        The request lock prevents concurrent HTTP execution inside this
        adapter, while the rate limiter enforces configured provider limits.

        This method performs no canonical transformation.
        """
        if self._session is None:
            raise RuntimeError(
                "API-Football HTTP session is not initialized."
            )

        url = f"{self._base_url}/{context.endpoint}"

        async with self._request_lock:
            await self._rate_limiter.acquire()

            async with self._session.get(
                url,
                params=dict(context.parameters),
            ) as response:
                response_headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                }

                await self._rate_limiter.record_response(
                    response_headers=response_headers
                )

                await self._update_quota_snapshot(
                    response_headers
                )

                http_status = response.status

                try:
                    payload = await response.json(
                        content_type=None
                    )
                except (
                    aiohttp.ContentTypeError,
                    ValueError,
                ) as exc:
                    body = await response.text()

                    status = (
                        self._status_from_http_error(
                            http_status
                        )
                        if http_status >= 400
                        else ProviderRequestStatus.PARSE_ERROR
                    )

                    return ProviderResponse(
                        context=context,
                        status=status,
                        payload=body,
                        received_at=datetime.now(
                            UTC
                        ),
                        http_status=http_status,
                        response_headers=response_headers,
                        error_message=str(exc),
                    )

                if http_status in self._RETRYABLE_HTTP_STATUSES:
                    retry_after = self._parse_float(
                        response_headers.get(
                            self._RETRY_AFTER_HEADER
                        )
                    )

                    if retry_after is not None:
                        previous = self._latest_quota

                        self._latest_quota = (
                            ProviderQuotaSnapshot(
                                provider_name=self.name,
                                observed_at=datetime.now(
                                    UTC
                                ),
                                requests_remaining=(
                                    previous.requests_remaining
                                    if previous is not None
                                    else None
                                ),
                                requests_limit=(
                                    previous.requests_limit
                                    if previous is not None
                                    else None
                                ),
                                retry_after_seconds=(
                                    retry_after
                                ),
                                rate_limit_remaining=(
                                    previous.rate_limit_remaining
                                    if previous is not None
                                    else None
                                ),
                                rate_limit_limit=(
                                    previous.rate_limit_limit
                                    if previous is not None
                                    else None
                                ),
                                metadata=response_headers,
                            )
                        )

                    error = self._extract_provider_error(
                        payload
                    )

                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=http_status,
                        message=error,
                        headers=response.headers,
                    )

                status = (
                    self._status_from_success_or_provider_error(
                        http_status=http_status,
                        payload=payload,
                    )
                )

                error_message = (
                    self._extract_provider_error(
                        payload
                    )
                )

                return ProviderResponse(
                    context=context,
                    status=status,
                    payload=payload,
                    received_at=datetime.now(
                        UTC
                    ),
                    http_status=http_status,
                    response_headers=response_headers,
                    error_message=error_message,
                )

    async def _update_quota_snapshot(
        self,
        headers: Mapping[str, str],
    ) -> None:
        """
        Update the latest provider quota snapshot.

        Missing headers remain unknown. The adapter never invents values.
        """
        now = datetime.now(UTC)

        requests_remaining = self._parse_int(
            headers.get(
                self._QUOTA_REMAINING_HEADER
            )
        )

        requests_limit = self._parse_int(
            headers.get(
                self._QUOTA_LIMIT_HEADER
            )
        )

        rate_limit_remaining = self._parse_int(
            headers.get(
                self._RATE_LIMIT_REMAINING_HEADER
            )
        )

        rate_limit_limit = self._parse_int(
            headers.get(
                self._RATE_LIMIT_LIMIT_HEADER
            )
        )

        retry_after = self._parse_float(
            headers.get(
                self._RETRY_AFTER_HEADER
            )
        )

        previous = self._latest_quota

        self._latest_quota = ProviderQuotaSnapshot(
            provider_name=self.name,
            observed_at=now,
            requests_remaining=(
                requests_remaining
                if requests_remaining is not None
                else (
                    previous.requests_remaining
                    if previous is not None
                    else None
                )
            ),
            requests_limit=(
                requests_limit
                if requests_limit is not None
                else (
                    previous.requests_limit
                    if previous is not None
                    else None
                )
            ),
            retry_after_seconds=retry_after,
            rate_limit_remaining=(
                rate_limit_remaining
                if rate_limit_remaining is not None
                else (
                    previous.rate_limit_remaining
                    if previous is not None
                    else None
                )
            ),
            rate_limit_limit=(
                rate_limit_limit
                if rate_limit_limit is not None
                else (
                    previous.rate_limit_limit
                    if previous is not None
                    else None
                )
            ),
            metadata=dict(headers),
        )

    def _build_context(
        self,
        *,
        endpoint: str,
        parameters: Mapping[str, Any],
        entity_type: ProviderEntityType | None = None,
        provider_entity_id: str | None = None,
    ) -> ProviderRequestContext:
        """
        Build a provider-scoped request context.
        """
        return ProviderRequestContext(
            provider_name=self.name,
            endpoint=endpoint,
            requested_at=datetime.now(UTC),
            request_id=str(uuid4()),
            entity_type=entity_type,
            provider_entity_id=provider_entity_id,
            parameters=dict(parameters),
        )

    def _calculate_backoff(
        self,
        attempt: int,
    ) -> float:
        """
        Calculate exponential retry delay from provider configuration.
        """
        retry = self._config.retry

        delay = retry.initial_backoff_seconds * (
            retry.exponential_base ** (attempt - 1)
        )

        return min(
            delay,
            retry.max_backoff_seconds,
        )

    @staticmethod
    def _status_from_http_error(
        status_code: int,
    ) -> ProviderRequestStatus:
        """
        Convert an HTTP status code into the generic provider status.
        """
        if status_code == 401 or status_code == 403:
            return ProviderRequestStatus.AUTHENTICATION_FAILED

        if status_code == 404:
            return ProviderRequestStatus.NOT_FOUND

        if status_code == 408 or status_code == 429:
            return ProviderRequestStatus.RATE_LIMITED

        if 400 <= status_code < 500:
            return ProviderRequestStatus.VALIDATION_ERROR

        if status_code >= 500:
            return ProviderRequestStatus.SERVER_ERROR

        return ProviderRequestStatus.UNKNOWN_ERROR

    @classmethod
    def _status_from_success_or_provider_error(
        cls,
        *,
        http_status: int,
        payload: Any,
    ) -> ProviderRequestStatus:
        """
        Determine the generic request status.

        API-Football can return an HTTP 200 response containing an API-level
        error object. Those responses must not automatically be considered
        successful.
        """
        if http_status >= 400:
            return cls._status_from_http_error(
                http_status
            )

        if cls._extract_provider_errors(payload):
            return ProviderRequestStatus.VALIDATION_ERROR

        return ProviderRequestStatus.SUCCESS

    @staticmethod
    def _extract_provider_errors(
        payload: Any,
    ) -> Mapping[str, Any] | None:
        """
        Extract API-level provider errors when present.

        The provider payload itself is never modified.
        """
        if not isinstance(payload, Mapping):
            return None

        errors = payload.get("errors")

        if isinstance(errors, Mapping) and errors:
            return errors

        return None

    @classmethod
    def _extract_provider_error(
        cls,
        payload: Any,
    ) -> str | None:
        """
        Convert provider error information into a diagnostic message.
        """
        errors = cls._extract_provider_errors(payload)

        if errors is None:
            return None

        parts: list[str] = []

        for key, value in errors.items():
            parts.append(
                f"{key}: {value}"
            )

        return "; ".join(parts)

    @staticmethod
    def _parse_int(
        value: str | None,
    ) -> int | None:
        """
        Parse an integer header without fabricating a value.
        """
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_float(
        value: str | None,
    ) -> float | None:
        """
        Parse a numeric header without fabricating a value.
        """
        if value is None:
            return None

        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None

        if parsed < 0:
            return None

        return parsed