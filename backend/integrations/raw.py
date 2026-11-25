from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from backend.integrations.base import (
    ProviderEntityType,
    ProviderRequestContext,
    ProviderResponse,
)


class RawPayloadFormat(StrEnum):
    """Formats supported by the raw payload storage contract."""

    JSON = "json"
    TEXT = "text"
    BINARY = "binary"


class RawIngestionStatus(StrEnum):
    """Lifecycle states for a raw provider observation."""

    RECEIVED = "received"
    STORED = "stored"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RawPayload:
    """
    Immutable representation of one provider payload.

    RawPayload intentionally does not contain canonical team, player,
    competition, match, or other internal entity IDs.

    It represents exactly what was received from a provider plus the
    metadata required to reproduce and audit the ingestion event.
    """

    provider_name: str
    payload_format: RawPayloadFormat
    payload: Any

    retrieved_at: datetime

    endpoint: str
    provider_entity_type: ProviderEntityType | None = None
    provider_entity_id: str | None = None

    request_id: str | None = None
    provider_timestamp: datetime | None = None

    request_parameters: Mapping[str, Any] = field(
        default_factory=dict
    )

    response_headers: Mapping[str, str] = field(
        default_factory=dict
    )

    payload_hash: str | None = None

    status: RawIngestionStatus = RawIngestionStatus.RECEIVED

    error_message: str | None = None

    @classmethod
    def from_provider_response(
        cls,
        response: ProviderResponse,
    ) -> RawPayload:
        """
        Construct a raw payload from a provider response.

        The provider payload is preserved without canonical normalization.
        """
        payload_format = cls._detect_payload_format(response.payload)

        payload_hash = response.payload_hash

        if payload_hash is None:
            payload_hash = calculate_payload_hash(
                response.payload,
                payload_format,
            )

        return cls(
            provider_name=response.context.provider_name,
            payload_format=payload_format,
            payload=response.payload,
            retrieved_at=response.received_at,
            endpoint=response.context.endpoint,
            provider_entity_type=response.context.entity_type,
            provider_entity_id=response.context.provider_entity_id,
            request_id=response.context.request_id,
            provider_timestamp=response.provider_timestamp,
            request_parameters=response.context.parameters,
            response_headers=response.response_headers,
            payload_hash=payload_hash,
            status=(
                RawIngestionStatus.STORED
                if response.succeeded
                else RawIngestionStatus.FAILED
            ),
            error_message=response.error_message,
        )

    @classmethod
    def from_request_context(
        cls,
        context: ProviderRequestContext,
        payload: Any,
        *,
        received_at: datetime | None = None,
        provider_timestamp: datetime | None = None,
        response_headers: Mapping[str, str] | None = None,
    ) -> RawPayload:
        """
        Construct a raw payload directly from a provider request context.

        This is useful for adapters that need to preserve a response before
        constructing a higher-level ProviderResponse object.
        """
        actual_received_at = received_at or datetime.now(UTC)

        payload_format = cls._detect_payload_format(payload)

        return cls(
            provider_name=context.provider_name,
            payload_format=payload_format,
            payload=payload,
            retrieved_at=actual_received_at,
            endpoint=context.endpoint,
            provider_entity_type=context.entity_type,
            provider_entity_id=context.provider_entity_id,
            request_id=context.request_id,
            provider_timestamp=provider_timestamp,
            request_parameters=context.parameters,
            response_headers=response_headers or {},
            payload_hash=calculate_payload_hash(
                payload,
                payload_format,
            ),
        )

    def canonical_payload_bytes(self) -> bytes:
        """
        Convert the raw payload into deterministic bytes for hashing.

        This does not modify the stored payload itself.
        """
        return serialize_payload(
            self.payload,
            self.payload_format,
        )

    def calculated_hash(self) -> str:
        """Calculate the SHA-256 hash of the payload."""
        return hashlib.sha256(
            self.canonical_payload_bytes()
        ).hexdigest()

    def verify_hash(self) -> bool:
        """
        Verify the stored payload hash.

        Returns True when no hash exists because verification is impossible
        rather than falsely claiming that an unverified payload is valid.
        """
        if self.payload_hash is None:
            return False

        return self.payload_hash == self.calculated_hash()

    @staticmethod
    def _detect_payload_format(
        payload: Any,
    ) -> RawPayloadFormat:
        """Determine the raw payload representation."""
        if isinstance(payload, bytes):
            return RawPayloadFormat.BINARY

        if isinstance(payload, str):
            return RawPayloadFormat.TEXT

        return RawPayloadFormat.JSON


@dataclass(frozen=True, slots=True)
class RawPayloadKey:
    """
    Logical identity for a raw provider observation.

    This is NOT a canonical entity identity.

    A provider entity can have many raw observations over time.
    """

    provider_name: str
    endpoint: str
    payload_hash: str

    provider_entity_type: ProviderEntityType | None = None
    provider_entity_id: str | None = None


def serialize_payload(
    payload: Any,
    payload_format: RawPayloadFormat,
) -> bytes:
    """
    Serialize a payload deterministically for hashing/storage.

    JSON payloads use stable key ordering and UTF-8 encoding.

    Text payloads are encoded as UTF-8.

    Binary payloads are preserved byte-for-byte.
    """
    if payload_format == RawPayloadFormat.BINARY:
        if not isinstance(payload, bytes):
            raise TypeError(
                "Binary raw payloads must be represented as bytes."
            )

        return payload

    if payload_format == RawPayloadFormat.TEXT:
        if not isinstance(payload, str):
            raise TypeError(
                "Text raw payloads must be represented as strings."
            )

        return payload.encode("utf-8")

    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "Payload cannot be serialized as deterministic JSON."
        ) from exc


def calculate_payload_hash(
    payload: Any,
    payload_format: RawPayloadFormat | None = None,
) -> str:
    """
    Calculate a SHA-256 checksum for a provider payload.

    The checksum is used for deduplication and auditability.

    It must never be treated as the identity of a team, player, match, or
    any other real-world entity.
    """
    actual_format = (
        payload_format
        if payload_format is not None
        else RawPayload._detect_payload_format(payload)
    )

    serialized = serialize_payload(
        payload,
        actual_format,
    )

    return hashlib.sha256(serialized).hexdigest()


def build_raw_payload_key(
    raw_payload: RawPayload,
) -> RawPayloadKey:
    """
    Build the provider-scoped logical key for a raw observation.
    """
    if not raw_payload.payload_hash:
        raise ValueError(
            "A payload hash is required before creating a RawPayloadKey."
        )

    return RawPayloadKey(
        provider_name=raw_payload.provider_name,
        endpoint=raw_payload.endpoint,
        payload_hash=raw_payload.payload_hash,
        provider_entity_type=raw_payload.provider_entity_type,
        provider_entity_id=raw_payload.provider_entity_id,
    )