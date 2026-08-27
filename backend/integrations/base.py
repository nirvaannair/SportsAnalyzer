from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence


class ProviderEntityType(StrEnum):
    """Entity categories that an external provider may expose."""

    SPORT = "sport"
    TEAM = "team"
    PLAYER = "player"
    COMPETITION = "competition"
    SEASON = "season"
    MATCH = "match"
    VENUE = "venue"
    MANAGER = "manager"
    MARKET = "market"
    OUTCOME = "outcome"
    NEWS_ARTICLE = "news_article"


class ProviderCapability(StrEnum):
    """Capabilities that a provider integration may expose."""

    SPORTS = "sports"
    TEAMS = "teams"
    PLAYERS = "players"
    COMPETITIONS = "competitions"
    SEASONS = "seasons"
    MATCHES = "matches"
    LINEUPS = "lineups"
    PLAYER_STATISTICS = "player_statistics"
    TEAM_STATISTICS = "team_statistics"
    PLAYER_TRANSFERS = "player_transfers"
    PLAYER_INJURIES = "player_injuries"
    NEWS = "news"
    ODDS = "odds"
    BETTING_MARKETS = "betting_markets"
    BET_PLACEMENT = "bet_placement"
    BET_HISTORY = "bet_history"
    ACCOUNT_BALANCE = "account_balance"


class ProviderRequestStatus(StrEnum):
    """Outcome of an external provider request."""

    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTHENTICATION_FAILED = "authentication_failed"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(frozen=True, slots=True)
class ProviderRequestContext:
    """
    Metadata describing one provider request.

    This object intentionally contains no canonical sports entities.
    Provider-specific identifiers remain provider-scoped.
    """

    provider_name: str
    endpoint: str
    requested_at: datetime
    request_id: str | None = None
    entity_type: ProviderEntityType | None = None
    provider_entity_id: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """
    Raw provider response returned by an adapter.

    The payload is intentionally represented as an opaque value. The
    provider adapter is responsible for understanding its own response
    format, while the ingestion layer is responsible for preserving it.
    """

    context: ProviderRequestContext
    status: ProviderRequestStatus
    payload: Any
    received_at: datetime
    http_status: int | None = None
    response_headers: Mapping[str, str] = field(default_factory=dict)
    provider_timestamp: datetime | None = None
    payload_hash: str | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether the provider request completed successfully."""
        return self.status == ProviderRequestStatus.SUCCESS


@dataclass(frozen=True, slots=True)
class ProviderEntity:
    """
    Provider-level entity.

    This is NOT a canonical SportsAnalyzer entity.

    The combination of provider_name, entity_type, and provider_entity_id
    identifies the provider's representation of an entity.
    """

    provider_name: str
    entity_type: ProviderEntityType
    provider_entity_id: str
    name: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    source_timestamp: datetime | None = None
    observed_at: datetime | None = None
    raw_payload_reference: str | None = None

    @property
    def provider_key(self) -> tuple[str, ProviderEntityType, str]:
        """Return the provider-scoped identity tuple."""
        return (
            self.provider_name,
            self.entity_type,
            self.provider_entity_id,
        )


@dataclass(frozen=True, slots=True)
class ProviderQuotaSnapshot:
    """
    Snapshot of provider quota/rate-limit information.

    Providers expose different quota mechanisms, so values may be unknown.
    Unknown values must remain None rather than being fabricated.
    """

    provider_name: str
    observed_at: datetime
    requests_remaining: int | None = None
    requests_limit: int | None = None
    window_seconds: int | None = None
    retry_after_seconds: float | None = None
    quota_reset_at: datetime | None = None
    rate_limit_remaining: int | None = None
    rate_limit_limit: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Current operational health information for a provider."""

    provider_name: str
    checked_at: datetime
    available: bool
    status: ProviderRequestStatus | None = None
    message: str | None = None


class ProviderAdapter(ABC):
    """
    Base contract for every external provider integration.

    Provider adapters communicate with external systems and return
    provider-level data. They must not create or mutate canonical
    SportsAnalyzer entities.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable internal name of this provider."""
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[ProviderCapability]:
        """Return the capabilities supported by this provider."""
        raise NotImplementedError

    async def initialize(self) -> None:
        """
        Initialize provider resources.

        Providers that require no initialization may use the default
        implementation.
        """

    async def close(self) -> None:
        """
        Release provider resources.

        Providers that do not maintain persistent resources may use the
        default implementation.
        """

    def supports(self, capability: ProviderCapability) -> bool:
        """Return whether this provider supports a capability."""
        return capability in self.capabilities

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check provider availability without modifying canonical data."""
        raise NotImplementedError

    @abstractmethod
    async def get_quota_snapshot(self) -> ProviderQuotaSnapshot:
        """
        Return the latest known quota/rate-limit information.

        If the provider does not expose quota information, unknown values
        must remain None.
        """
        raise NotImplementedError

    @abstractmethod
    async def fetch(
        self,
        context: ProviderRequestContext,
    ) -> ProviderResponse:
        """
        Execute one provider request.

        The adapter must return the provider response without transforming
        it into a canonical SportsAnalyzer entity.
        """
        raise NotImplementedError

    async def fetch_entities(
        self,
        entity_type: ProviderEntityType,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> Sequence[ProviderEntity]:
        """
        Fetch provider entities of a supported type.

        Provider-specific adapters should override this method when they
        support entity discovery for the requested entity type.
        """
        raise NotImplementedError(
            f"Provider '{self.name}' does not implement entity discovery "
            f"for '{entity_type.value}'."
        )