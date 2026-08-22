from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class HistoricalTeamSnapshot(Base):
    __tablename__ = "historical_team_snapshots"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    fixture_id: Mapped[int] = mapped_column(
        ForeignKey(
            "api_football_fixtures.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    played: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    wins: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    draws: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    losses: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    goals_for: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    goals_against: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    goal_difference: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    form: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )