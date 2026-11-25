from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
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

# ---------------------------------------------------------------------------
# Canonical football model
#
# One row per real-world thing, whichever providers mention it. Provider IDs
# live only in ProviderEntityMapping.
# ---------------------------------------------------------------------------


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False
    )
    start_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (UniqueConstraint("competition_id", "start_year"),)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_teams_country_name", "country", "name"),)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # scheduled | finished
    home_goals: Mapped[int | None] = mapped_column(SmallInteger)
    away_goals: Mapped[int | None] = mapped_column(SmallInteger)
    ht_home_goals: Mapped[int | None] = mapped_column(SmallInteger)
    ht_away_goals: Mapped[int | None] = mapped_column(SmallInteger)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("home_team_id", "away_team_id", "match_date", name="uq_matches_teams_date"),
        Index("ix_matches_season_date", "season_id", "match_date"),
        Index("ix_matches_date", "match_date"),
    )


class OddsQuote(Base):
    """One price for one selection. Historical and closing odds share this table."""

    __tablename__ = "odds_quotes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # who reported it
    bookmaker: Mapped[str] = mapped_column(String(32), nullable=False)  # pinnacle, bet365, avg, max
    market: Mapped[str] = mapped_column(String(16), nullable=False)  # 1x2, ou25
    selection: Mapped[str] = mapped_column(String(16), nullable=False)  # home, draw, away, over, under
    price: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    is_closing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "match_id", "source", "bookmaker", "market", "selection", "is_closing",
            name="uq_odds_quotes_identity",
        ),
    )


class ProviderEntityMapping(Base):
    """How one provider's ID for a team (or match, player...) maps to our canonical row.

    status: active (resolved), unresolved (needs review), rejected (not one of ours).
    """

    __tablename__ = "provider_entity_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_label: Mapped[str] = mapped_column(String(200), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    canonical_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str | None] = mapped_column(String(48))
    confidence: Mapped[float | None] = mapped_column(Float)
    candidates: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("provider_name", "entity_type", "provider_entity_id",
                         name="uq_provider_entity_mappings_key"),
        Index("ix_provider_entity_mappings_status", "entity_type", "status"),
        Index("ix_provider_entity_mappings_canonical", "entity_type", "canonical_id"),
    )


# ---------------------------------------------------------------------------
# Models and predictions
# ---------------------------------------------------------------------------


class ModelRun(Base):
    """One training/backtest run of one model. Metrics are computed on real results."""

    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(48), nullable=False)  # elo, dixon_coles, blend
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # backtest | live
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    trained_until: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_model_runs_model_kind", "model", "kind", "created_at"),)


class Prediction(Base):
    """A model's pre-match probabilities for one match. Never derived from odds."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    p_home: Mapped[float] = mapped_column(Float, nullable=False)
    p_draw: Mapped[float] = mapped_column(Float, nullable=False)
    p_away: Mapped[float] = mapped_column(Float, nullable=False)
    p_over25: Mapped[float | None] = mapped_column(Float)
    p_btts: Mapped[float | None] = mapped_column(Float)
    exp_home_goals: Mapped[float | None] = mapped_column(Float)
    exp_away_goals: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("run_id", "match_id", name="uq_predictions_run_match"),
        Index("ix_predictions_match", "match_id"),
    )


# ---------------------------------------------------------------------------
# Scraper (Scrapy) runs and what they collected
# ---------------------------------------------------------------------------


class ScrapeRun(Base):
    """One Scrapy crawl started from the dashboard or CLI."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spider: Mapped[str] = mapped_column(String(64), nullable=False)
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # queued running finished failed stopped
    pid: Mapped[int | None] = mapped_column(Integer)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScrapedItem(Base):
    """Everything a spider yields, as scraped (odds and betting data are stripped before storing)."""

    __tablename__ = "scraped_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id", ondelete="SET NULL"))
    spider: Mapped[str] = mapped_column(String(64), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g. ESPN event id
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("spider", "item_type", "key", name="uq_scraped_items_key"),
        Index("ix_scraped_items_run", "run_id", "id"),
    )


# ---------------------------------------------------------------------------
# Players and who was on the pitch
# ---------------------------------------------------------------------------


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MatchPlayer(Base):
    """One player's participation in one match: on-pitch minutes and basic stats."""

    __tablename__ = "match_players"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    started: Mapped[bool] = mapped_column(Boolean, nullable=False)
    minute_on: Mapped[int | None] = mapped_column(SmallInteger)  # None = unused substitute
    minute_off: Mapped[int | None] = mapped_column(SmallInteger)
    position: Mapped[str | None] = mapped_column(String(16))
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="uq_match_players_match_player"),
        Index("ix_match_players_player", "player_id"),
        Index("ix_match_players_team", "team_id", "match_id"),
    )


class MatchEvent(Base):
    """Goals, substitutions and cards with their minute."""

    __tablename__ = "match_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    minute: Mapped[int | None] = mapped_column(SmallInteger)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # goal, own_goal, penalty_goal, sub, yellow, red
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    other_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))  # assist / player off

    __table_args__ = (Index("ix_match_events_match", "match_id"),)


class TeamMatchStats(Base):
    """Team-level match stats (possession, passes, shots, crosses...) used for style maps."""

    __tablename__ = "team_match_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (UniqueConstraint("match_id", "team_id", name="uq_team_match_stats"),)


# ---------------------------------------------------------------------------
# Stake execution (browser helper)
# ---------------------------------------------------------------------------


class AppSetting(Base):
    """Small key/value store for switches the user flips on the dashboard."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StakeOperation(Base):
    """A GraphQL request shape learned from the user's own Stake tab (no headers, no token)."""

    __tablename__ = "stake_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # query | mutation
    query: Mapped[str] = mapped_column(Text, nullable=False)
    sample_variables: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StakeOutcome(Base):
    """A selectable outcome seen on a Stake page, with its price at that moment.

    Prices here are bet payouts only. Prediction models never read this table (README §5.0).
    """

    __tablename__ = "stake_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outcome_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    fixture_name: Mapped[str | None] = mapped_column(String(200))
    market_name: Mapped[str | None] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool | None] = mapped_column(Boolean)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StakeOrder(Base):
    """A bet the system wants to place. Moves: pending_approval -> approved -> sent -> placed|failed.

    Can also be rejected (by the user) or blocked (by a guardrail).
    """

    __tablename__ = "stake_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # manual_test | strategy:<name>
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    outcome_id: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    min_price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    status_detail: Mapped[str | None] = mapped_column(Text)
    request_preview: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    stake_bet_id: Mapped[str | None] = mapped_column(String(128))
    placed_price: Mapped[float | None] = mapped_column(Float)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_stake_orders_status", "status", "created_at"),)
