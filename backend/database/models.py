from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SportsAnalyzer database models."""


class RawProviderObservation(Base):
    """
    Immutable observation of a response received from an external provider.

    Provider-specific payloads remain untouched. This table is intentionally
    independent of the canonical sports domain model so that new providers
    can be added without changing the raw ingestion contract.
    """

    __tablename__ = "raw_provider_observations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    provider_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    endpoint: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
    )

    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    provider_entity_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    provider_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    request_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    response_headers: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    payload_format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    payload: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = (
        mapped_column(
            JSONB,
            nullable=False,
        )
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_raw_provider_observations_provider_endpoint",
            "provider_name",
            "endpoint",
        ),
        Index(
            "ix_raw_provider_observations_provider_entity",
            "provider_name",
            "entity_type",
            "provider_entity_id",
        ),
        Index(
            "ix_raw_provider_observations_payload_hash",
            "provider_name",
            "payload_hash",
        ),
        Index(
            "ix_raw_provider_observations_received_at",
            "received_at",
        ),
    )