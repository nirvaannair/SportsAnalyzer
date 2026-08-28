from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import RawProviderObservation
from backend.integrations.base import ProviderEntityType
from backend.integrations.raw import (
    RawIngestionStatus,
    RawPayload,
    RawPayloadFormat,
    RawPayloadKey,
)
from backend.integrations.repository import RawPayloadRepository


class PostgresRawPayloadRepository(RawPayloadRepository):
    """
    PostgreSQL implementation of the raw provider payload repository.

    This repository is responsible only for durable persistence and retrieval
    of provider observations.

    It does not:
    - normalize provider data
    - resolve canonical entities
    - interpret provider-specific payloads
    - create canonical sports entities
    - commit or rollback the caller's transaction
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def store(
        self,
        payload: RawPayload,
    ) -> RawPayloadKey:
        """
        Persist one raw provider observation.

        The caller owns the transaction. This method flushes the pending
        INSERT so database-generated values and constraint errors are
        surfaced immediately, but it does not commit the transaction.
        """
        if not payload.request_id:
            raise ValueError(
                "Raw payload must have a request_id before persistence."
            )

        if not payload.payload_hash:
            raise ValueError(
                "Raw payload must have a payload_hash before persistence."
            )

        if payload.payload_format == RawPayloadFormat.BINARY:
            raise ValueError(
                "Binary raw payloads cannot be persisted because the current "
                "database payload column uses PostgreSQL JSONB."
            )

        observation = RawProviderObservation(
            provider_name=payload.provider_name,
            endpoint=payload.endpoint,
            request_id=payload.request_id,
            entity_type=(
                payload.provider_entity_type.value
                if payload.provider_entity_type is not None
                else None
            ),
            provider_entity_id=payload.provider_entity_id,
            requested_at=payload.retrieved_at,
            received_at=payload.retrieved_at,
            provider_timestamp=payload.provider_timestamp,
            request_parameters=dict(payload.request_parameters),
            response_headers=dict(payload.response_headers),
            payload_format=payload.payload_format.value,
            payload_hash=payload.payload_hash,
            payload=payload.payload,
            status=payload.status.value,
            error_message=payload.error_message,
        )

        self._session.add(observation)

        await self._session.flush()

        return RawPayloadKey(
            provider_name=payload.provider_name,
            endpoint=payload.endpoint,
            payload_hash=payload.payload_hash,
            provider_entity_type=payload.provider_entity_type,
            provider_entity_id=payload.provider_entity_id,
        )

    async def exists(
        self,
        key: RawPayloadKey,
    ) -> bool:
        """
        Check whether a raw observation with the supplied provider-scoped
        logical key already exists.
        """
        statement = (
            select(RawProviderObservation.id)
            .where(
                RawProviderObservation.provider_name
                == key.provider_name,
                RawProviderObservation.endpoint
                == key.endpoint,
                RawProviderObservation.payload_hash
                == key.payload_hash,
            )
        )

        if key.provider_entity_type is not None:
            statement = statement.where(
                RawProviderObservation.entity_type
                == key.provider_entity_type.value,
            )

        if key.provider_entity_id is not None:
            statement = statement.where(
                RawProviderObservation.provider_entity_id
                == key.provider_entity_id,
            )

        statement = statement.limit(1)

        result = await self._session.execute(statement)

        return result.scalar_one_or_none() is not None

    async def get(
        self,
        key: RawPayloadKey,
    ) -> RawPayload | None:
        """
        Retrieve one raw observation by its provider-scoped logical key.
        """
        statement = (
            select(RawProviderObservation)
            .where(
                RawProviderObservation.provider_name
                == key.provider_name,
                RawProviderObservation.endpoint
                == key.endpoint,
                RawProviderObservation.payload_hash
                == key.payload_hash,
            )
        )

        if key.provider_entity_type is not None:
            statement = statement.where(
                RawProviderObservation.entity_type
                == key.provider_entity_type.value,
            )

        if key.provider_entity_id is not None:
            statement = statement.where(
                RawProviderObservation.provider_entity_id
                == key.provider_entity_id,
            )

        statement = (
            statement
            .order_by(
                RawProviderObservation.received_at.desc(),
                RawProviderObservation.id.desc(),
            )
            .limit(1)
        )

        result = await self._session.execute(statement)

        observation = result.scalar_one_or_none()

        if observation is None:
            return None

        return self._to_raw_payload(observation)

    async def list_by_provider(
        self,
        provider_name: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[RawPayload, ...]:
        """
        Retrieve raw observations belonging to one provider.
        """
        statement = select(RawProviderObservation).where(
            RawProviderObservation.provider_name == provider_name,
        )

        if start_time is not None:
            statement = statement.where(
                RawProviderObservation.received_at >= start_time,
            )

        if end_time is not None:
            statement = statement.where(
                RawProviderObservation.received_at <= end_time,
            )

        statement = statement.order_by(
            RawProviderObservation.received_at.desc(),
            RawProviderObservation.id.desc(),
        )

        if limit is not None:
            if limit < 1:
                raise ValueError(
                    "limit must be greater than zero."
                )

            statement = statement.limit(limit)

        result = await self._session.execute(statement)

        observations = result.scalars().all()

        return tuple(
            self._to_raw_payload(observation)
            for observation in observations
        )

    async def list_by_entity(
        self,
        provider_name: str,
        provider_entity_id: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[RawPayload, ...]:
        """
        Retrieve historical observations for one provider entity.

        Entity type is intentionally not required by the repository contract.
        Therefore all observations for the provider-scoped entity ID are
        returned regardless of entity type.
        """
        statement = select(RawProviderObservation).where(
            RawProviderObservation.provider_name == provider_name,
            RawProviderObservation.provider_entity_id
            == provider_entity_id,
        )

        if start_time is not None:
            statement = statement.where(
                RawProviderObservation.received_at >= start_time,
            )

        if end_time is not None:
            statement = statement.where(
                RawProviderObservation.received_at <= end_time,
            )

        statement = statement.order_by(
            RawProviderObservation.received_at.desc(),
            RawProviderObservation.id.desc(),
        )

        if limit is not None:
            if limit < 1:
                raise ValueError(
                    "limit must be greater than zero."
                )

            statement = statement.limit(limit)

        result = await self._session.execute(statement)

        observations = result.scalars().all()

        return tuple(
            self._to_raw_payload(observation)
            for observation in observations
        )

    async def count_by_provider(
        self,
        provider_name: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """
        Count raw observations belonging to one provider.
        """
        statement = select(
            func.count(RawProviderObservation.id)
        ).where(
            RawProviderObservation.provider_name == provider_name,
        )

        if start_time is not None:
            statement = statement.where(
                RawProviderObservation.received_at >= start_time,
            )

        if end_time is not None:
            statement = statement.where(
                RawProviderObservation.received_at <= end_time,
            )

        result = await self._session.execute(statement)

        return int(result.scalar_one())

    @staticmethod
    def _to_raw_payload(
        observation: RawProviderObservation,
    ) -> RawPayload:
        """
        Reconstruct the domain RawPayload from a database observation.
        """
        try:
            payload_format = RawPayloadFormat(
                observation.payload_format
            )
        except ValueError as exc:
            raise ValueError(
                "Stored observation contains an unsupported payload "
                f"format: {observation.payload_format!r}."
            ) from exc

        try:
            status = RawIngestionStatus(
                observation.status
            )
        except ValueError as exc:
            raise ValueError(
                "Stored observation contains an unsupported ingestion "
                f"status: {observation.status!r}."
            ) from exc

        provider_entity_type = None

        if observation.entity_type is not None:
            try:
                provider_entity_type = ProviderEntityType(
                    observation.entity_type
                )
            except ValueError as exc:
                raise ValueError(
                    "Stored observation contains an unsupported provider "
                    f"entity type: {observation.entity_type!r}."
                ) from exc

        return RawPayload(
            provider_name=observation.provider_name,
            payload_format=payload_format,
            payload=observation.payload,
            retrieved_at=observation.received_at,
            endpoint=observation.endpoint,
            provider_entity_type=provider_entity_type,
            provider_entity_id=observation.provider_entity_id,
            request_id=observation.request_id,
            provider_timestamp=observation.provider_timestamp,
            request_parameters=observation.request_parameters,
            response_headers=observation.response_headers,
            payload_hash=observation.payload_hash,
            status=status,
            error_message=observation.error_message,
        )