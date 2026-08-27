from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.integrations.api_football import ApiFootballAdapter
from backend.integrations.config import (
    ProviderCacheConfig,
    ProviderConfig,
    ProviderQuotaConfig,
    ProviderRateLimitConfig,
    ProviderRetryConfig,
    ProviderSyncConfig,
)


ENV_FILE = PROJECT_ROOT / ".env"

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "provider_inspection"
    / "api_football"
)

OUTPUT_FILE = OUTPUT_DIRECTORY / "adapter_test_latest.json"


def parse_bool(
    value: str | None,
    *,
    default: bool,
) -> bool:
    if value is None or not value.strip():
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"Invalid boolean configuration value: {value}"
    )


def parse_int(
    value: str | None,
) -> int | None:
    if value is None or not value.strip():
        return None

    return int(value)


def parse_float(
    value: str | None,
) -> float | None:
    if value is None or not value.strip():
        return None

    return float(value)


def load_provider_config() -> ProviderConfig:
    """
    Load API-Football configuration from the repository .env file.

    This deliberately avoids the global ApplicationSettings object because
    provider connectivity tests must not require unrelated infrastructure
    such as the database.
    """
    load_dotenv(
        dotenv_path=ENV_FILE,
        override=False,
    )

    enabled = parse_bool(
        os.getenv("API_FOOTBALL_ENABLED"),
        default=True,
    )

    if not enabled:
        raise ValueError(
            "API_FOOTBALL_ENABLED is set to false."
        )

    base_url = os.getenv(
        "API_FOOTBALL_BASE_URL"
    )

    api_key = os.getenv(
        "API_FOOTBALL_API_KEY"
    )

    if not base_url or not base_url.strip():
        raise ValueError(
            "API_FOOTBALL_BASE_URL is not configured in .env."
        )

    if not api_key or not api_key.strip():
        raise ValueError(
            "API_FOOTBALL_API_KEY is not configured in .env."
        )

    request_timeout_seconds = parse_float(
        os.getenv(
            "API_FOOTBALL_REQUEST_TIMEOUT_SECONDS"
        )
    )

    if request_timeout_seconds is None:
        request_timeout_seconds = 30.0

    rate_limit = ProviderRateLimitConfig(
        requests_per_minute=parse_int(
            os.getenv(
                "API_FOOTBALL_REQUESTS_PER_MINUTE"
            )
        ),
        requests_per_day=parse_int(
            os.getenv(
                "API_FOOTBALL_REQUESTS_PER_DAY"
            )
        ),
    )

    quota = ProviderQuotaConfig(
        requests_per_minute=parse_int(
            os.getenv(
                "API_FOOTBALL_QUOTA_REQUESTS_PER_MINUTE"
            )
        ),
        requests_per_day=parse_int(
            os.getenv(
                "API_FOOTBALL_QUOTA_REQUESTS_PER_DAY"
            )
        ),
    )

    retry = ProviderRetryConfig(
        max_attempts=(
            parse_int(
                os.getenv(
                    "API_FOOTBALL_RETRY_MAX_ATTEMPTS"
                )
            )
            or 3
        ),
        initial_backoff_seconds=(
            parse_float(
                os.getenv(
                    "API_FOOTBALL_RETRY_INITIAL_BACKOFF_SECONDS"
                )
            )
            if os.getenv(
                "API_FOOTBALL_RETRY_INITIAL_BACKOFF_SECONDS"
            )
            else 1.0
        ),
        max_backoff_seconds=(
            parse_float(
                os.getenv(
                    "API_FOOTBALL_RETRY_MAX_BACKOFF_SECONDS"
                )
            )
            if os.getenv(
                "API_FOOTBALL_RETRY_MAX_BACKOFF_SECONDS"
            )
            else 30.0
        ),
        exponential_base=(
            parse_float(
                os.getenv(
                    "API_FOOTBALL_RETRY_EXPONENTIAL_BASE"
                )
            )
            if os.getenv(
                "API_FOOTBALL_RETRY_EXPONENTIAL_BASE"
            )
            else 2.0
        ),
    )

    cache = ProviderCacheConfig(
        enabled=parse_bool(
            os.getenv(
                "API_FOOTBALL_CACHE_ENABLED"
            ),
            default=True,
        ),
    )

    sync = ProviderSyncConfig(
        enabled=parse_bool(
            os.getenv(
                "API_FOOTBALL_SYNC_ENABLED"
            ),
            default=True,
        ),
    )

    return ProviderConfig(
        name="api_football",
        enabled=True,
        base_url=base_url.strip(),
        api_key=api_key.strip(),
        request_timeout_seconds=request_timeout_seconds,
        rate_limit=rate_limit,
        quota=quota,
        retry=retry,
        cache=cache,
        sync=sync,
    )


def sanitize_headers(
    headers: dict[str, str],
) -> dict[str, str]:
    """
    Remove authentication secrets from diagnostic output.
    """
    sensitive_headers = {
        "authorization",
        "x-apisports-key",
        "x-rapidapi-key",
    }

    return {
        key: (
            "<redacted>"
            if key.lower() in sensitive_headers
            else value
        )
        for key, value in headers.items()
    }


async def main() -> None:
    config = load_provider_config()

    adapter = ApiFootballAdapter(config)

    try:
        await adapter.initialize()

        context = adapter._build_context(
            endpoint="status",
            parameters={},
        )

        response = await adapter.fetch(context)
        quota = await adapter.get_quota_snapshot()

        output: dict[str, Any] = {
            "provider": adapter.name,
            "request": {
                "endpoint": context.endpoint,
                "parameters": dict(context.parameters),
                "request_id": context.request_id,
            },
            "result": {
                "status": response.status.value,
                "succeeded": response.succeeded,
                "http_status": response.http_status,
                "error_message": response.error_message,
                "received_at": response.received_at.isoformat(),
                "response_headers": sanitize_headers(
                    dict(response.response_headers)
                ),
                "payload": response.payload,
            },
            "quota": {
                "observed_at": quota.observed_at.isoformat(),
                "requests_remaining": quota.requests_remaining,
                "requests_limit": quota.requests_limit,
                "rate_limit_remaining": quota.rate_limit_remaining,
                "rate_limit_limit": quota.rate_limit_limit,
                "retry_after_seconds": quota.retry_after_seconds,
                "metadata": sanitize_headers(
                    dict(quota.metadata)
                ),
            },
        }

        OUTPUT_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

        OUTPUT_FILE.write_text(
            json.dumps(
                output,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        print(f"Provider: {adapter.name}")
        print(
            f"Request status: {response.status.value}"
        )
        print(
            f"HTTP status: {response.http_status}"
        )
        print(
            f"Succeeded: {response.succeeded}"
        )

        if response.error_message:
            print(
                f"Provider error: {response.error_message}"
            )

        print()
        print("Quota snapshot:")
        print(
            "  Requests remaining: "
            f"{quota.requests_remaining}"
        )
        print(
            "  Requests limit: "
            f"{quota.requests_limit}"
        )
        print(
            "  Rate-limit remaining: "
            f"{quota.rate_limit_remaining}"
        )
        print(
            "  Rate-limit limit: "
            f"{quota.rate_limit_limit}"
        )

        print()
        print(
            f"Response saved to: {OUTPUT_FILE}"
        )

        print()
        print("Provider payload:")

        print(
            json.dumps(
                response.payload,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(main())