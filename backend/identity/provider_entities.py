from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class IdentityEntityType(StrEnum):
    """Real-world entity categories supported by identity resolution."""

    SPORT = "sport"
    TEAM = "team"
    PLAYER = "player"
    COMPETITION = "competition"
    SEASON = "season"
    MATCH = "match"
    VENUE = "venue"
    MANAGER = "manager"


@dataclass(frozen=True, slots=True)
class ProviderEntityKey:
    """
    Provider-scoped identity.

    This is the complete identity of a provider record only.

    It must never be used as the canonical SportsAnalyzer entity ID.
    """

    provider_name: str
    entity_type: IdentityEntityType
    provider_entity_id: str

    def __post_init__(self) -> None:
        provider_name = self.provider_name.strip().lower()
        provider_entity_id = self.provider_entity_id.strip()

        if not provider_name:
            raise ValueError("Provider name must not be empty.")

        if not provider_entity_id:
            raise ValueError(
                "Provider entity ID must not be empty."
            )

        object.__setattr__(
            self,
            "provider_name",
            provider_name,
        )

        object.__setattr__(
            self,
            "provider_entity_id",
            provider_entity_id,
        )


@dataclass(frozen=True, slots=True)
class ProviderEntity:
    """
    A provider's representation of a real-world entity.

    ProviderEntity intentionally remains provider-specific.

    For example, two ProviderEntity objects can represent the same real-world
    football team while having completely different provider names and IDs.
    Identity resolution is responsible for determining whether they refer to
    the same canonical entity.
    """

    key: ProviderEntityKey

    name: str | None = None

    aliases: tuple[str, ...] = ()

    country: str | None = None
    region: str | None = None

    sport: str | None = None
    competition_name: str | None = None
    season_name: str | None = None

    date_of_birth: date | None = None
    nationality: str | None = None
    position: str | None = None

    external_identifiers: Mapping[str, str] = field(
        default_factory=dict
    )

    attributes: Mapping[str, Any] = field(
        default_factory=dict
    )

    source_timestamp: datetime | None = None
    observed_at: datetime | None = None

    raw_payload_reference: str | None = None

    def __post_init__(self) -> None:
        if self.name is not None and not self.name.strip():
            object.__setattr__(
                self,
                "name",
                None,
            )

        normalized_aliases = tuple(
            alias.strip()
            for alias in self.aliases
            if alias and alias.strip()
        )

        object.__setattr__(
            self,
            "aliases",
            normalized_aliases,
        )

    @property
    def provider_name(self) -> str:
        """Return the provider that owns this entity representation."""
        return self.key.provider_name

    @property
    def provider_entity_id(self) -> str:
        """Return the provider-specific entity ID."""
        return self.key.provider_entity_id

    @property
    def entity_type(self) -> IdentityEntityType:
        """Return the entity category."""
        return self.key.entity_type

    @property
    def identity_attributes(self) -> Mapping[str, Any]:
        """
        Return attributes that can participate in entity resolution.

        These values are provider observations only. They do not establish
        that the entity has been resolved to a canonical entity.
        """
        return {
            "name": self.name,
            "aliases": self.aliases,
            "country": self.country,
            "region": self.region,
            "sport": self.sport,
            "competition_name": self.competition_name,
            "season_name": self.season_name,
            "date_of_birth": self.date_of_birth,
            "nationality": self.nationality,
            "position": self.position,
            "external_identifiers": self.external_identifiers,
        }


@dataclass(frozen=True, slots=True)
class ProviderEntityObservation:
    """
    Historical observation of a provider entity.

    A provider entity can change over time, so the application must not
    assume that the latest representation is the only representation that
    ever existed.
    """

    key: ProviderEntityKey

    observed_at: datetime

    name: str | None = None
    aliases: tuple[str, ...] = ()

    country: str | None = None
    region: str | None = None

    sport: str | None = None
    competition_name: str | None = None
    season_name: str | None = None

    date_of_birth: date | None = None
    nationality: str | None = None
    position: str | None = None

    external_identifiers: Mapping[str, str] = field(
        default_factory=dict
    )

    attributes: Mapping[str, Any] = field(
        default_factory=dict
    )

    raw_payload_reference: str | None = None

    @classmethod
    def from_entity(
        cls,
        entity: ProviderEntity,
        *,
        observed_at: datetime | None = None,
    ) -> ProviderEntityObservation:
        """
        Create a historical observation from a provider entity.
        """
        timestamp = (
            observed_at
            or entity.observed_at
            or entity.source_timestamp
        )

        if timestamp is None:
            raise ValueError(
                "An observation timestamp is required."
            )

        return cls(
            key=entity.key,
            observed_at=timestamp,
            name=entity.name,
            aliases=entity.aliases,
            country=entity.country,
            region=entity.region,
            sport=entity.sport,
            competition_name=entity.competition_name,
            season_name=entity.season_name,
            date_of_birth=entity.date_of_birth,
            nationality=entity.nationality,
            position=entity.position,
            external_identifiers=entity.external_identifiers,
            attributes=entity.attributes,
            raw_payload_reference=entity.raw_payload_reference,
        )

    def to_provider_entity(self) -> ProviderEntity:
        """Convert the observation back into a provider entity."""
        return ProviderEntity(
            key=self.key,
            name=self.name,
            aliases=self.aliases,
            country=self.country,
            region=self.region,
            sport=self.sport,
            competition_name=self.competition_name,
            season_name=self.season_name,
            date_of_birth=self.date_of_birth,
            nationality=self.nationality,
            position=self.position,
            external_identifiers=self.external_identifiers,
            attributes=self.attributes,
            source_timestamp=self.observed_at,
            observed_at=self.observed_at,
            raw_payload_reference=self.raw_payload_reference,
        )


def build_provider_entity_key(
    provider_name: str,
    entity_type: IdentityEntityType,
    provider_entity_id: str,
) -> ProviderEntityKey:
    """
    Construct a validated provider-scoped identity key.
    """
    return ProviderEntityKey(
        provider_name=provider_name,
        entity_type=entity_type,
        provider_entity_id=provider_entity_id,
    )