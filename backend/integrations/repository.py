from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from .raw import RawPayload, RawPayloadKey


class RawPayloadRepository(ABC):
    """
    Persistence contract for raw provider observations.

    Implementations are responsible for durable storage. The ingestion layer
    depends only on this contract and therefore remains independent of the
    eventual database or object-storage implementation.
    """

    @abstractmethod
    async def store(
        self,
        payload: RawPayload,
    ) -> RawPayloadKey:
        """
        Persist one raw provider observation.

        Implementations must preserve the payload and its ingestion metadata.
        They must not normalize provider data into canonical entities.
        """
        raise NotImplementedError

    @abstractmethod
    async def exists(
        self,
        key: RawPayloadKey,
    ) -> bool:
        """
        Check whether an equivalent raw observation already exists.
        """
        raise NotImplementedError

    @abstractmethod
    async def get(
        self,
        key: RawPayloadKey,
    ) -> RawPayload | None:
        """
        Retrieve one raw observation by its provider-scoped key.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_by_provider(
        self,
        provider_name: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[RawPayload]:
        """
        Retrieve raw observations belonging to one provider.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_by_entity(
        self,
        provider_name: str,
        provider_entity_id: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[RawPayload]:
        """
        Retrieve historical observations for one provider entity.

        The provider entity ID is intentionally scoped to the provider.
        It must never be interpreted as a canonical SportsAnalyzer ID.
        """
        raise NotImplementedError

    @abstractmethod
    async def count_by_provider(
        self,
        provider_name: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """
        Count raw observations for a provider.
        """
        raise NotImplementedError

    async def store_if_new(
        self,
        payload: RawPayload,
    ) -> tuple[RawPayloadKey, bool]:
        """
        Store a payload only when an equivalent observation is not present.

        Returns:
            A tuple containing:

            - the logical raw payload key
            - True when a new observation was stored
            - False when an equivalent observation already existed

        This helper provides idempotent ingestion behavior at the repository
        boundary without requiring callers to implement duplicate checks.
        """
        key = _require_payload_key(payload)

        if await self.exists(key):
            return key, False

        stored_key = await self.store(payload)

        return stored_key, True


def _require_payload_key(
    payload: RawPayload,
) -> RawPayloadKey:
    """
    Build and validate the logical key required by repository operations.
    """
    if not payload.payload_hash:
        raise ValueError(
            "Raw payload must have a payload hash before persistence."
        )

    return RawPayloadKey(
        provider_name=payload.provider_name,
        endpoint=payload.endpoint,
        payload_hash=payload.payload_hash,
        provider_entity_type=payload.provider_entity_type,
        provider_entity_id=payload.provider_entity_id,
    )