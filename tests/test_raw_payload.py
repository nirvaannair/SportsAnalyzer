from datetime import UTC, datetime

from backend.integrations.base import (
    ProviderRequestContext,
    ProviderRequestStatus,
    ProviderResponse,
)
from backend.integrations.raw import (
    RawIngestionStatus,
    RawPayload,
    RawPayloadFormat,
    build_raw_payload_key,
    calculate_payload_hash,
)


def _context() -> ProviderRequestContext:
    return ProviderRequestContext(
        provider_name="api_football",
        endpoint="/fixtures",
        requested_at=datetime.now(UTC),
        request_id="req-1",
        parameters={"league": 39, "season": 2024},
    )


def test_json_hash_ignores_key_order() -> None:
    assert calculate_payload_hash({"a": 1, "b": [1, 2]}) == calculate_payload_hash(
        {"b": [1, 2], "a": 1}
    )
    assert calculate_payload_hash({"a": 1}) != calculate_payload_hash({"a": 2})


def test_format_detection() -> None:
    assert RawPayload._detect_payload_format(b"x") is RawPayloadFormat.BINARY
    assert RawPayload._detect_payload_format("<html>") is RawPayloadFormat.TEXT
    assert RawPayload._detect_payload_format({"x": 1}) is RawPayloadFormat.JSON


def test_from_provider_response_sets_hash_and_status() -> None:
    response = ProviderResponse(
        context=_context(),
        status=ProviderRequestStatus.SUCCESS,
        payload={"response": []},
        received_at=datetime.now(UTC),
    )
    raw = RawPayload.from_provider_response(response)
    assert raw.status is RawIngestionStatus.STORED
    assert raw.verify_hash()
    key = build_raw_payload_key(raw)
    assert key.provider_name == "api_football"
    assert key.payload_hash == raw.payload_hash


def test_failed_response_is_marked_failed() -> None:
    response = ProviderResponse(
        context=_context(),
        status=ProviderRequestStatus.RATE_LIMITED,
        payload={"errors": {"rateLimit": "too many"}},
        received_at=datetime.now(UTC),
        error_message="rate limited",
    )
    assert RawPayload.from_provider_response(response).status is RawIngestionStatus.FAILED
