from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .canonical import CanonicalEntityStatus
from .provider_entities import (
    IdentityEntityType,
    ProviderEntityKey,
)


class MappingStatus(StrEnum):
    """
    Lifecycle state of a provider-to-canonical identity mapping.
    """

    ACTIVE = "active"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    UNRESOLVED = "unresolved"


class ResolutionMethod(StrEnum):
    """
    Method that produced an identity-resolution decision.

    The values describe the resolution mechanism, not the correctness
    of the resulting mapping.
    """

    EXACT_EXTERNAL_IDENTIFIER = "exact_external_identifier"
    EXACT_PROVIDER_CROSS_REFERENCE = "exact_provider_cross_reference"
    DETERMINISTIC_RULE = "deterministic_rule"
    NAME_AND_CONTEXT = "name_and_context"
    FUZZY_NAME = "fuzzy_name"
    COMPOSITE_SCORE = "composite_score"
    IMPORTED_MAPPING = "imported_mapping"
    MANUAL_OVERRIDE = "manual_override"


@dataclass(frozen=True, slots=True)
class IdentityResolutionEvidence:
    """
    Evidence used by the identity-resolution engine.

    Evidence is stored separately from the final mapping so the decision
    can be inspected and reproduced later.
    """

    signal: str
    score: float
    matched: bool
    details: str | None = None

    def __post_init__(self) -> None:
        if not self.signal.strip():
            raise ValueError(
                "Identity-resolution evidence signal must not be empty."
            )

        if not 0.0 <= self.score <= 1.0:
            raise ValueError(
                "Identity-resolution evidence score must be between "
                "0 and 1."
            )


@dataclass(frozen=True, slots=True)
class IdentityResolutionCandidate:
    """
    Candidate canonical entity considered for a provider entity.
    """

    provider_entity: ProviderEntityKey
    canonical_entity_id: UUID
    entity_type: IdentityEntityType

    confidence: float

    evidence: tuple[IdentityResolutionEvidence, ...] = ()

    method: ResolutionMethod | None = None

    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Candidate confidence must be between 0 and 1."
            )

        if self.provider_entity.entity_type != self.entity_type:
            raise ValueError(
                "Provider entity type and candidate entity type must match."
            )


@dataclass(frozen=True, slots=True)
class ProviderCanonicalMapping:
    """
    Persistent relationship between one provider entity and one canonical
    SportsAnalyzer entity.

    This is the table-level identity bridge that allows different providers
    to use completely different identifiers for the same real-world entity.
    """

    id: UUID

    provider_entity: ProviderEntityKey

    canonical_entity_id: UUID

    entity_type: IdentityEntityType

    status: MappingStatus

    confidence: float

    resolution_method: ResolutionMethod

    evidence: tuple[IdentityResolutionEvidence, ...] = ()

    created_at: datetime | None = None
    updated_at: datetime | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    resolver_version: str | None = None

    source_candidate_id: UUID | None = None

    attributes: dict[str, str] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        *,
        provider_entity: ProviderEntityKey,
        canonical_entity_id: UUID,
        confidence: float,
        resolution_method: ResolutionMethod,
        evidence: tuple[IdentityResolutionEvidence, ...] = (),
        status: MappingStatus = MappingStatus.ACTIVE,
        mapping_id: UUID | None = None,
        created_at: datetime | None = None,
        valid_from: datetime | None = None,
        resolver_version: str | None = None,
        source_candidate_id: UUID | None = None,
        attributes: dict[str, str] | None = None,
    ) -> "ProviderCanonicalMapping":
        """
        Create a provider-to-canonical mapping.

        The mapping does not modify either the provider entity or the
        canonical entity.
        """
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "Mapping confidence must be between 0 and 1."
            )

        if (
            status == MappingStatus.ACTIVE
            and confidence <= 0.0
        ):
            raise ValueError(
                "An active mapping must have a positive confidence."
            )

        now = created_at or datetime.utcnow()

        return cls(
            id=mapping_id or UUID(int=0),
            provider_entity=provider_entity,
            canonical_entity_id=canonical_entity_id,
            entity_type=provider_entity.entity_type,
            status=status,
            confidence=confidence,
            resolution_method=resolution_method,
            evidence=evidence,
            created_at=now,
            updated_at=now,
            valid_from=valid_from or now,
            resolver_version=resolver_version,
            source_candidate_id=source_candidate_id,
            attributes=attributes or {},
        )

    def activate(
        self,
        *,
        updated_at: datetime | None = None,
    ) -> "ProviderCanonicalMapping":
        """
        Return an active version of this mapping.
        """
        return self._with_status(
            MappingStatus.ACTIVE,
            updated_at=updated_at,
        )

    def reject(
        self,
        *,
        updated_at: datetime | None = None,
    ) -> "ProviderCanonicalMapping":
        """
        Return a rejected version of this mapping.
        """
        return self._with_status(
            MappingStatus.REJECTED,
            updated_at=updated_at,
        )

    def supersede(
        self,
        *,
        updated_at: datetime | None = None,
    ) -> "ProviderCanonicalMapping":
        """
        Return a superseded version of this mapping.
        """
        return self._with_status(
            MappingStatus.SUPERSEDED,
            updated_at=updated_at,
        )

    def _with_status(
        self,
        status: MappingStatus,
        *,
        updated_at: datetime | None,
    ) -> "ProviderCanonicalMapping":
        """
        Create an immutable copy with a new mapping status.
        """
        return ProviderCanonicalMapping(
            id=self.id,
            provider_entity=self.provider_entity,
            canonical_entity_id=self.canonical_entity_id,
            entity_type=self.entity_type,
            status=status,
            confidence=self.confidence,
            resolution_method=self.resolution_method,
            evidence=self.evidence,
            created_at=self.created_at,
            updated_at=updated_at or datetime.utcnow(),
            valid_from=self.valid_from,
            valid_to=self.valid_to,
            resolver_version=self.resolver_version,
            source_candidate_id=self.source_candidate_id,
            attributes=dict(self.attributes),
        )

    @property
    def is_active(self) -> bool:
        """Return whether this mapping is currently active."""
        return self.status == MappingStatus.ACTIVE

    @property
    def provider_name(self) -> str:
        """Return the provider owning the mapped entity."""
        return self.provider_entity.provider_name

    @property
    def provider_entity_id(self) -> str:
        """Return the provider-specific identifier."""
        return self.provider_entity.provider_entity_id


@dataclass(frozen=True, slots=True)
class MappingConflict:
    """
    Represents a conflict discovered during identity resolution.

    A conflict is data-quality information. It must not silently result in
    a merge.
    """

    provider_entity: ProviderEntityKey

    existing_canonical_entity_id: UUID | None

    proposed_canonical_entity_id: UUID | None

    reason: str

    detected_at: datetime

    evidence: tuple[IdentityResolutionEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError(
                "Mapping conflict reason must not be empty."
            )


@dataclass(frozen=True, slots=True)
class IdentityResolutionResult:
    """
    Complete result produced by an identity-resolution run.

    The result may contain an accepted mapping, unresolved candidates, or a
    conflict. Nothing here directly mutates persistent state.
    """

    provider_entity: ProviderEntityKey

    selected_candidate: IdentityResolutionCandidate | None

    candidates: tuple[IdentityResolutionCandidate, ...]

    status: MappingStatus

    resolver_version: str

    resolved_at: datetime

    conflict: MappingConflict | None = None

    def __post_init__(self) -> None:
        if not self.resolver_version.strip():
            raise ValueError(
                "Resolver version must not be empty."
            )

        if (
            self.status == MappingStatus.ACTIVE
            and self.selected_candidate is None
        ):
            raise ValueError(
                "An active resolution result requires a selected candidate."
            )

        if (
            self.selected_candidate is not None
            and self.selected_candidate.provider_entity
            != self.provider_entity
        ):
            raise ValueError(
                "Selected candidate does not belong to the resolved "
                "provider entity."
            )

    @property
    def confidence(self) -> float | None:
        """
        Return the selected candidate confidence, if one exists.
        """
        if self.selected_candidate is None:
            return None

        return self.selected_candidate.confidence