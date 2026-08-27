from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import aiohttp
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "provider_inspection"
    / "api_football"
)


def load_api_key() -> str:
    """Load the API-Football key from the project environment."""
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv(
        "SPORTSANALYZER_API_FOOTBALL_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "SPORTSANALYZER_API_FOOTBALL_API_KEY is not configured "
            "in the project .env file."
        )

    return api_key


def parse_arguments() -> argparse.Namespace:
    """Parse inspection parameters supplied by the user."""
    parser = argparse.ArgumentParser(
        description=(
            "Make one controlled API-Football request and save "
            "the complete response for inspection."
        )
    )

    parser.add_argument(
        "endpoint",
        help=(
            "API-Football endpoint without the leading slash. "
            "Example: leagues"
        ),
    )

    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Query parameter. May be supplied multiple times. "
            "Example: --param current=true"
        ),
    )

    return parser.parse_args()


def parse_parameters(
    raw_parameters: list[str],
) -> dict[str, str]:
    """Convert KEY=VALUE arguments into query parameters."""
    parameters: dict[str, str] = {}

    for raw_parameter in raw_parameters:
        if "=" not in raw_parameter:
            raise ValueError(
                "Invalid parameter format "
                f"'{raw_parameter}'. Expected KEY=VALUE."
            )

        key, value = raw_parameter.split(
            "=",
            maxsplit=1,
        )

        key = key.strip()

        if not key:
            raise ValueError(
                f"Invalid parameter '{raw_parameter}': "
                "parameter name cannot be empty."
            )

        parameters[key] = value

    return parameters


def extract_quota_headers(
    headers: aiohttp.typedefs.LooseHeaders,
) -> dict[str, str]:
    """
    Extract known quota/rate-limit headers.

    The function does not assume that every response contains every
    possible header.
    """
    interesting_headers = {
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-requests-limit",
        "x-ratelimit-requests-remaining",
        "x-ratelimit-reset",
        "retry-after",
    }

    result: dict[str, str] = {}

    for key, value in headers.items():
        normalized_key = key.lower()

        if normalized_key in interesting_headers:
            result[normalized_key] = value

    return result


async def request_endpoint(
    session: aiohttp.ClientSession,
    api_key: str,
    endpoint: str,
    parameters: dict[str, str],
) -> tuple[
    dict[str, Any],
    dict[str, str],
    dict[str, str],
    int,
]:
    """
    Execute exactly one API-Football request.

    No retry is performed here.

    This is intentional because this tool exists specifically for controlled
    API inspection and every request consumes a limited provider resource.
    """
    normalized_endpoint = endpoint.strip().strip("/")

    if not normalized_endpoint:
        raise ValueError(
            "Endpoint must not be empty."
        )

    url = (
        "https://v3.football.api-sports.io/"
        f"{normalized_endpoint}"
    )

    headers = {
        "x-apisports-key": api_key,
    }

    async with session.get(
        url,
        headers=headers,
        params=parameters,
    ) as response:
        response_headers = {
            key: value
            for key, value in response.headers.items()
        }

        quota_headers = extract_quota_headers(
            response.headers
        )

        try:
            payload = await response.json(
                content_type=None
            )
        except (aiohttp.ContentTypeError, json.JSONDecodeError):
            response_text = await response.text()

            payload = {
                "raw_text_response": response_text,
            }

        return (
            payload,
            response_headers,
            quota_headers,
            response.status,
        )


def write_inspection_result(
    *,
    endpoint: str,
    parameters: dict[str, str],
    payload: dict[str, Any],
    response_headers: dict[str, str],
    quota_headers: dict[str, str],
    status_code: int,
) -> Path:
    """Persist one complete provider inspection."""
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_endpoint = (
        endpoint.strip()
        .strip("/")
        .replace("/", "_")
    )

    parameter_suffix = ""

    if parameters:
        parameter_suffix = "_with_parameters"

    output_path = (
        OUTPUT_DIRECTORY
        / (
            f"{safe_endpoint}"
            f"{parameter_suffix}"
            "_latest.json"
        )
    )

    inspection_document = {
        "request": {
            "endpoint": endpoint,
            "parameters": parameters,
        },
        "response_metadata": {
            "http_status": status_code,
            "quota_headers": quota_headers,
            "headers": response_headers,
        },
        "response": payload,
    }

    output_path.write_text(
        json.dumps(
            inspection_document,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return output_path


async def main() -> int:
    """Execute one controlled provider inspection."""
    arguments = parse_arguments()

    try:
        parameters = parse_parameters(
            arguments.param
        )
    except ValueError as exc:
        print(f"Parameter error: {exc}")
        return 1

    try:
        api_key = load_api_key()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}")
        return 1

    timeout = aiohttp.ClientTimeout(
        total=30
    )

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:
        try:
            (
                payload,
                response_headers,
                quota_headers,
                status_code,
            ) = await request_endpoint(
                session=session,
                api_key=api_key,
                endpoint=arguments.endpoint,
                parameters=parameters,
            )
        except (aiohttp.ClientError, ValueError) as exc:
            print(
                "API-Football request failed: "
                f"{exc}"
            )
            return 1

    output_path = write_inspection_result(
        endpoint=arguments.endpoint,
        parameters=parameters,
        payload=payload,
        response_headers=response_headers,
        quota_headers=quota_headers,
        status_code=status_code,
    )

    print(f"HTTP status: {status_code}")

    print("\nDetected quota/rate-limit headers:")

    if quota_headers:
        for key, value in sorted(
            quota_headers.items()
        ):
            print(
                f"  {key}: {value}"
            )
    else:
        print("  None detected")

    print(
        f"\nResponse saved to: {output_path}"
    )

    print("\nResponse:")

    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        asyncio.run(main())
    )