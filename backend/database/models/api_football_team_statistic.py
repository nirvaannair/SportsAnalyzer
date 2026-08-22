from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class APIFootballTeamStatistic(Base):
    __tablename__ = "api_football_team_statistics"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        )
    )

    api_football_team_id: Mapped[int] = mapped_column()

    league_id: Mapped[int] = mapped_column()

    season: Mapped[int] = mapped_column()

    played: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    wins: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    draws: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    losses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    goals_for: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    goals_against: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_played: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_wins: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_draws: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_losses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_played: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_wins: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_draws: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_losses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    
    form: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    goal_difference: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    clean_sheets: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    failed_to_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_goals_for: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    home_goals_against: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_goals_for: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_goals_against: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    raw_json: Mapped[str] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )