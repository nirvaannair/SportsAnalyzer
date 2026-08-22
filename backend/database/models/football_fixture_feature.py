from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class FootballFixtureFeature(Base):
    __tablename__ = "football_fixture_features"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    fixture_id: Mapped[int] = mapped_column(
        ForeignKey(
            "api_football_fixtures.id",
            ondelete="CASCADE",
        ),
        unique=True,
        index=True,
    )

    home_team_id: Mapped[int] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    away_team_id: Mapped[int] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    league_id: Mapped[int] = mapped_column(
        index=True,
    )

    season: Mapped[int] = mapped_column(
        index=True,
    )

    home_played: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_played: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_wins: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_wins: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_draws: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_draws: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_losses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_losses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_goals_for: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_goals_for: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_goals_against: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_goals_against: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_goal_difference: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_goal_difference: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_clean_sheets: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_clean_sheets: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_failed_to_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_failed_to_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_form: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    away_form: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    home_xg: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    away_xg: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    home_xga: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    away_xga: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )