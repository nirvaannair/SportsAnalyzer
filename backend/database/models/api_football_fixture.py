from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class APIFootballFixture(Base):
    __tablename__ = "api_football_fixtures"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    api_football_fixture_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        index=True,
    )

    league_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )

    season: Mapped[int] = mapped_column(
        Integer,
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

    home_goals: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    away_goals: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    winner_team_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    fixture_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
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