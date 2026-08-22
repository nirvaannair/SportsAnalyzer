from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    stake_fixture_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )

    tournament_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tournaments.id",
            ondelete="CASCADE",
        )
    )

    fixture_slug: Mapped[str] = mapped_column(
        String(512),
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(512),
    )

    home_team: Mapped[str] = mapped_column(
        String(255),
    )

    away_team: Mapped[str] = mapped_column(
        String(255),
    )

    provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(100),
    )

    market_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    tournament = relationship(
        "Tournament",
        back_populates="fixtures",
    )

    markets = relationship(
        "Market",
        back_populates="fixture",
    )