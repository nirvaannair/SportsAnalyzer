from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class TrainingExample(Base):
    __tablename__ = "training_examples"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    bet_leg_id: Mapped[int] = mapped_column(
        ForeignKey(
            "bet_legs.id",
            ondelete="CASCADE",
        ),
        unique=True,
        index=True,
    )

    fixture_id: Mapped[int] = mapped_column(
        ForeignKey(
            "fixtures.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    sport_name: Mapped[str] = mapped_column(
        String(255),
    )

    tournament_name: Mapped[str] = mapped_column(
        String(255),
    )

    fixture_name: Mapped[str] = mapped_column(
        String(512),
    )

    home_team: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    away_team: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    market_name: Mapped[str] = mapped_column(
        String(255),
    )

    market_type: Mapped[str] = mapped_column(
        String(100),
    )

    selected_team: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    selected_side: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    outcome_name: Mapped[str] = mapped_column(
        String(255),
    )

    odds: Mapped[float] = mapped_column(
        Float,
    )

    implied_probability: Mapped[float] = mapped_column(
        Float,
    )

    is_home_selection: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    is_away_selection: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    target: Mapped[int] = mapped_column(
        Integer,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )