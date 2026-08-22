from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class StakeBalance(BaseModel):
    available: dict[str, float] = Field(
        default_factory=dict
    )

    vault: dict[str, float] = Field(
        default_factory=dict
    )


class StakeCompetitor(BaseModel):
    name: str

    abbreviation: str | None = None

    ext_id: str | None = None


class StakeSport(BaseModel):
    id: str

    name: str

    slug: str


class StakeCategory(BaseModel):
    id: str

    name: str

    slug: str

    sport: StakeSport


class StakeTournament(BaseModel):
    id: str

    name: str

    slug: str

    category: StakeCategory


class StakeOutcome(BaseModel):
    id: str

    name: str

    odds: float

    active: bool


class StakeMarket(BaseModel):
    id: str

    name: str

    status: str

    ext_id: str | None = None

    specifiers: str | None = None

    provider: str | None = None

    outcomes: list[StakeOutcome] = Field(
        default_factory=list
    )


class StakeTemplate(BaseModel):
    ext_id: str

    rank: int | None = None

    name: str

    markets: list[StakeMarket] = Field(
        default_factory=list
    )


class StakeGroup(BaseModel):
    name: str

    translation: str | None = None

    rank: int | None = None

    templates: list[StakeTemplate] = Field(
        default_factory=list
    )


class StakeFixture(BaseModel):
    id: str

    slug: str

    name: str

    status: str

    provider: str | None = None

    ext_id: str | None = None

    market_count: int = 0

    start_time: datetime | None = None

    competitors: list[
        StakeCompetitor
    ] = Field(
        default_factory=list
    )

    tournament: StakeTournament

    groups: list[
        StakeGroup
    ] = Field(
        default_factory=list
    )


class StakeBetOutcome(BaseModel):
    outcome_id: str

    outcome_name: str

    odds: float

    market_name: str

    fixture_id: str

    fixture_name: str

    fixture_slug: str


class StakeBet(BaseModel):
    id: str

    amount: float

    payout: float | None = None

    status: str

    created_at: datetime

    updated_at: datetime

    payout_multiplier: float | None = None

    outcomes: list[
        StakeBetOutcome
    ] = Field(
        default_factory=list
    )