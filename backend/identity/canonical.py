from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from .provider_entities import IdentityEntityType


class CanonicalEntityStatus(StrEnum):
    """Lifecycle status of a canonical entity."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MERGED = "merged"
    DEPRECATED = "deprecated"


@dataclass(frozen=True, slots=True)
class CanonicalEntity:
    """
    Stable internal identity for a real-world entity.

    The UUID is generated internally by SportsAnalyzer and is completely
    independent of every external provider identifier.

    Provider IDs must never replace this canonical identity.
    """

    id: UUID
    entity_type: IdentityEntityType

    canonical_name: str

    status: CanonicalEntityStatus = CanonicalEntityStatus.ACTIVE

    sport: str | None = None
    country: str | None = None
    region: str | None = None

    aliases: tuple[str, ...] = ()

    created_at: datetime | None = None
    updated_at: datetime | None = None

    attributes: Mapping[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.canonical_name.strip():
            raise ValueError(
                "canonical_name must not be empty."
            )

        normalized_aliases = tuple(
            alias.strip()
            for alias in self.aliases
            if alias and alias.strip()
        )

        object.__setattr__(
            self,
            "canonical_name",
            self.canonical_name.strip(),
        )

        object.__setattr__(
            self,
            "aliases",
            normalized_aliases,
        )

    @classmethod
    def create(
        cls,
        *,
        entity_type: IdentityEntityType,
        canonical_name: str,
        sport: str | None = None,
        country: str | None = None,
        region: str | None = None,
        aliases: tuple[str, ...] = (),
        attributes: Mapping[str, Any] | None = None,
        entity_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> CanonicalEntity:
        """
        Create a new canonical entity.

        The generated UUID is an internal identity and contains no provider
        information.
        """
        now = datetime.utcnow()

        return cls(
            id=entity_id or uuid4(),
            entity_type=entity_type,
            canonical_name=canonical_name,
            status=CanonicalEntityStatus.ACTIVE,
            sport=sport,
            country=country,
            region=region,
            aliases=aliases,
            created_at=created_at or now,
            updated_at=updated_at or now,
            attributes=attributes or {},
        )

    def with_updates(
        self,
        *,
        canonical_name: str | None = None,
        status: CanonicalEntityStatus | None = None,
        sport: str | None = None,
        country: str | None = None,
        region: str | None = None,
        aliases: tuple[str, ...] | None = None,
        attributes: Mapping[str, Any] | None = None,
        updated_at: datetime | None = None,
    ) -> CanonicalEntity:
        """
        Create an updated immutable version of the canonical entity.
        """
        return CanonicalEntity(
            id=self.id,
            entity_type=self.entity_type,
            canonical_name=(
                canonical_name
                if canonical_name is not None
                else self.canonical_name
            ),
            status=(
                status
                if status is not None
                else self.status
            ),
            sport=(
                sport
                if sport is not None
                else self.sport
            ),
            country=(
                country
                if country is not None
                else self.country
            ),
            region=(
                region
                if region is not None
                else self.region
            ),
            aliases=(
                aliases
                if aliases is not None
                else self.aliases
            ),
            created_at=self.created_at,
            updated_at=updated_at or datetime.utcnow(),
            attributes=(
                attributes
                if attributes is not None
                else self.attributes
            ),
        )


@dataclass(frozen=True, slots=True)
class CanonicalTeam:
    """
    Canonical representation of a team.

    This is intentionally separate from provider-specific team records.
    """

    id: UUID

    canonical_name: str

    sport: str | None = None
    country: str | None = None
    region: str | None = None

    team_type: str | None = None

    aliases: tuple[str, ...] = ()

    status: CanonicalEntityStatus = CanonicalEntityStatus.ACTIVE

    creation_date: date | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    attributes: Mapping[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        *,
        canonical_name: str,
        sport: str | None = None,
        country: str | None = None,
        region: str | None = None,
        team_type: str | None = None,
        aliases: tuple[str, ...] = (),
        creation_date: date | None = None,
        attributes: Mapping[str, Any] | None = None,
        team_id: UUID | None = None,
    ) -> CanonicalTeam:
        """
        Create a canonical team with an internally generated UUID.
        """
        now = datetime.utcnow()

        if not canonical_name.strip():
            raise ValueError(
                "canonical_name must not be empty."
            )

        return cls(
            id=team_id or uuid4(),
            canonical_name=canonical_name.strip(),
            sport=sport,
            country=country,
            region=region,
            team_type=team_type,
            aliases=aliases,
            creation_date=creation_date,
            created_at=now,
            updated_at=now,
            attributes=attributes or {},
        )


@dataclass(frozen=True, slots=True)
class CanonicalPlayer:
    """
    Canonical representation of a player.

    A player's canonical identity persists across team transfers.
    """

    id: UUID

    canonical_name: str

    date_of_birth: date | None = None
    nationality: str | None = None
    sport: str | None = None
    position: str | None = None

    aliases: tuple[str, ...] = ()

    status: CanonicalEntityStatus = CanonicalEntityStatus.ACTIVE

    created_at: datetime | None = None
    updated_at: datetime | None = None

    attributes: Mapping[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        *,
        canonical_name: str,
        date_of_birth: date | None = None,
        nationality: str | None = None,
        sport: str | None = None,
        position: str | None = None,
        aliases: tuple[str, ...] = (),
        attributes: Mapping[str, Any] | None = None,
        player_id: UUID | None = None,
    ) -> CanonicalPlayer:
        """
        Create a canonical player with an internally generated UUID.
        """
        now = datetime.utcnow()

        if not canonical_name.strip():
            raise ValueError(
                "canonical_name must not be empty."
            )

        return cls(
            id=player_id or uuid4(),
            canonical_name=canonical_name.strip(),
            date_of_birth=date_of_birth,
            nationality=nationality,
            sport=sport,
            position=position,
            aliases=aliases,
            created_at=now,
            updated_at=now,
            attributes=attributes or {},
        )


@dataclass(frozen=True, slots=True)
class CanonicalCompetition:
    """
    Canonical representation of a competition or league.
    """

    id: UUID

    canonical_name: str

    sport: str | None = None
    country: str | None = None
    region: str | None = None

    competition_type: str | None = None

    aliases: tuple[str, ...] = ()

    status: CanonicalEntityStatus = CanonicalEntityStatus.ACTIVE

    created_at: datetime | None = None
    updated_at: datetime | None = None

    attributes: Mapping[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        *,
        canonical_name: str,
        sport: str | None = None,
        country: str | None = None,
        region: str | None = None,
        competition_type: str | None = None,
        aliases: tuple[str, ...] = (),
        attributes: Mapping[str, Any] | None = None,
        competition_id: UUID | None = None,
    ) -> CanonicalCompetition:
        """
        Create a canonical competition with an internal UUID.
        """
        now = datetime.utcnow()

        if not canonical_name.strip():
            raise ValueError(
                "canonical_name must not be empty."
            )

        return cls(
            id=competition_id or uuid4(),
            canonical_name=canonical_name.strip(),
            sport=sport,
            country=country,
            region=region,
            competition_type=competition_type,
            aliases=aliases,
            created_at=now,
            updated_at=now,
            attributes=attributes or {},
        )


@dataclass(frozen=True, slots=True)
class CanonicalSeason:
    """
    Canonical representation of a competition season.
    """

    id: UUID

    canonical_name: str

    competition_id: UUID

    start_date: date | None = None
    end_date: date | None = None

    status: CanonicalEntityStatus = CanonicalEntityStatus.ACTIVE

    created_at: datetime | None = None
    updated_at: datetime | None = None

    attributes: Mapping[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        *,
        canonical_name: str,
        competition_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        attributes: Mapping[str, Any] | None = None,
        season_id: UUID | None = None,
    ) -> CanonicalSeason:
        """
        Create a canonical season linked to a canonical competition.
        """
        now = datetime.utcnow()

        if not canonical_name.strip():
            raise ValueError(
                "canonical_name must not be empty."
            )

        return cls(
            id=season_id or uuid4(),
            canonical_name=canonical_name.strip(),
            competition_id=competition_id,
            start_date=start_date,
            end_date=end_date,
            created_at=now,
            updated_at=now,
            attributes=attributes or {},
        )