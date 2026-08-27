from __future__ import annotations

import os
from typing import Mapping

from .config import (
    ProviderCacheConfig,
    ProviderConfig,
    ProviderQuotaConfig,
    ProviderRateLimitConfig,
    ProviderRetryConfig,
    ProviderSyncConfig,
)


PROVIDER_NAME = "api_football"


def _get_required_environment_variable(
    name: str,
) -> str:
    """
    Return a required environment variable.

    Secrets and provider-specific connection details must come from the
    environment rather than being embedded in source code.
    """
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f"Required environment variable '{name}' is not configured."
        )

    return value.strip()


def _get_optional_string(
    name: str,
    default: str | None = None,
) -> str | None:
    """
    Return an optional string environment variable.
    """
    value = os.getenv(name)

    if value is None:
        return default

    stripped = value.strip()

    return stripped if stripped else default


def _get_optional_bool(
    name: str,
    default: bool,
) -> bool:
    """
    Parse an optional boolean environment variable.
    """
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().casefold()

    if normalized in {"true", "1", "yes", "on"}:
        return True

    if normalized in {"false", "0", "no", "off"}:
        return False

    raise ValueError(
        f"Environment variable '{name}' must be a boolean value."
    )


def _get_optional_int(
    name: str,
    default: int | None = None,
) -> int | None:
    """
    Parse an optional integer environment variable.

    None means that no local value has been configured.
    """
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable '{name}' must be an integer."
        ) from exc

    if parsed <= 0:
        raise ValueError(
            f"Environment variable '{name}' must be greater than zero."
        )

    return parsed


def _get_optional_float(
    name: str,
    default: float | None = None,
) -> float | None:
    """
    Parse an optional floating-point environment variable.
    """
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable '{name}' must be numeric."
        ) from exc

    if parsed <= 0:
        raise ValueError(
            f"Environment variable '{name}' must be greater than zero."
        )

    return parsed


def _get_metadata() -> Mapping[str, str]:
    """
    Build provider metadata from optional environment configuration.

    Metadata is descriptive configuration only. It contains no provider
    entities or real-world sports data.
    """
    metadata: dict[str, str] = {}

    environment = _get_optional_string(
        "API_FOOTBALL_ENVIRONMENT"
    )

    if environment is not None:
        metadata["environment"] = environment

    account_name = _get_optional_string(
        "API_FOOTBALL_ACCOUNT_NAME"
    )

    if account_name is not None:
        metadata["account_name"] = account_name

    return metadata


def build_api_football_config() -> ProviderConfig:
    """
    Build the runtime ProviderConfig for API-Football.

    All provider-specific operational values come from environment
    configuration.

    No API-Football IDs, teams, players, leagues, fixtures, odds, or other
    real-world data are embedded here.
    """
    api_key = _get_required_environment_variable(
        "API_FOOTBALL_API_KEY"
    )

    base_url = _get_required_environment_variable(
        "API_FOOTBALL_BASE_URL"
    )

    enabled = _get_optional_bool(
        "API_FOOTBALL_ENABLED",
        True,
    )

    request_timeout_seconds = _get_optional_float(
        "API_FOOTBALL_REQUEST_TIMEOUT_SECONDS",
        30.0,
    )

    requests_per_second = _get_optional_float(
        "API_FOOTBALL_REQUESTS_PER_SECOND"
    )

    requests_per_minute = _get_optional_int(
        "API_FOOTBALL_REQUESTS_PER_MINUTE"
    )

    requests_per_hour = _get_optional_int(
        "API_FOOTBALL_REQUESTS_PER_HOUR"
    )

    requests_per_day = _get_optional_int(
        "API_FOOTBALL_REQUESTS_PER_DAY"
    )

    quota_requests_per_minute = _get_optional_int(
        "API_FOOTBALL_QUOTA_REQUESTS_PER_MINUTE"
    )

    quota_requests_per_hour = _get_optional_int(
        "API_FOOTBALL_QUOTA_REQUESTS_PER_HOUR"
    )

    quota_requests_per_day = _get_optional_int(
        "API_FOOTBALL_QUOTA_REQUESTS_PER_DAY"
    )

    quota_requests_per_month = _get_optional_int(
        "API_FOOTBALL_QUOTA_REQUESTS_PER_MONTH"
    )

    retry_max_attempts = _get_optional_int(
        "API_FOOTBALL_RETRY_MAX_ATTEMPTS",
        3,
    )

    retry_initial_backoff_seconds = _get_optional_float(
        "API_FOOTBALL_RETRY_INITIAL_BACKOFF_SECONDS",
        1.0,
    )

    retry_max_backoff_seconds = _get_optional_float(
        "API_FOOTBALL_RETRY_MAX_BACKOFF_SECONDS",
        30.0,
    )

    retry_exponential_base = _get_optional_float(
        "API_FOOTBALL_RETRY_EXPONENTIAL_BASE",
        2.0,
    )

    cache_enabled = _get_optional_bool(
        "API_FOOTBALL_CACHE_ENABLED",
        True,
    )

    cache_ttl_seconds = _get_optional_int(
        "API_FOOTBALL_CACHE_TTL_SECONDS"
    )

    sync_enabled = _get_optional_bool(
        "API_FOOTBALL_SYNC_ENABLED",
        True,
    )

    upcoming_fixtures_interval_seconds = _get_optional_int(
        "API_FOOTBALL_UPCOMING_FIXTURES_INTERVAL_SECONDS"
    )

    historical_data_interval_seconds = _get_optional_int(
        "API_FOOTBALL_HISTORICAL_DATA_INTERVAL_SECONDS"
    )

    live_data_interval_seconds = _get_optional_int(
        "API_FOOTBALL_LIVE_DATA_INTERVAL_SECONDS"
    )

    news_interval_seconds = _get_optional_int(
        "API_FOOTBALL_NEWS_INTERVAL_SECONDS"
    )

    odds_interval_seconds = _get_optional_int(
        "API_FOOTBALL_ODDS_INTERVAL_SECONDS"
    )

    return ProviderConfig(
        name=PROVIDER_NAME,
        enabled=enabled,
        base_url=base_url,
        api_key=api_key,
        request_timeout_seconds=(
            request_timeout_seconds
            if request_timeout_seconds is not None
            else 30.0
        ),
        rate_limit=ProviderRateLimitConfig(
            requests_per_second=requests_per_second,
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            requests_per_day=requests_per_day,
        ),
        quota=ProviderQuotaConfig(
            requests_per_minute=quota_requests_per_minute,
            requests_per_hour=quota_requests_per_hour,
            requests_per_day=quota_requests_per_day,
            requests_per_month=quota_requests_per_month,
        ),
        retry=ProviderRetryConfig(
            max_attempts=(
                retry_max_attempts
                if retry_max_attempts is not None
                else 3
            ),
            initial_backoff_seconds=(
                retry_initial_backoff_seconds
                if retry_initial_backoff_seconds is not None
                else 1.0
            ),
            max_backoff_seconds=(
                retry_max_backoff_seconds
                if retry_max_backoff_seconds is not None
                else 30.0
            ),
            exponential_base=(
                retry_exponential_base
                if retry_exponential_base is not None
                else 2.0
            ),
        ),
        cache=ProviderCacheConfig(
            enabled=cache_enabled,
            default_ttl_seconds=cache_ttl_seconds,
        ),
        sync=ProviderSyncConfig(
            enabled=sync_enabled,
            upcoming_fixtures_interval_seconds=(
                upcoming_fixtures_interval_seconds
            ),
            historical_data_interval_seconds=(
                historical_data_interval_seconds
            ),
            live_data_interval_seconds=(
                live_data_interval_seconds
            ),
            news_interval_seconds=(
                news_interval_seconds
            ),
            odds_interval_seconds=(
                odds_interval_seconds
            ),
        ),
        metadata=_get_metadata(),
    )