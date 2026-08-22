from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class BetLeg(Base):
    __tablename__ = "bet_legs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    stake_bet_id: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    stake_bet_slip_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    bet_history_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey(
            "bet_history.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    fixture_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    fixture_name: Mapped[
        str | None
    ] = mapped_column(
        String(512),
        nullable=True,
    )

    fixture_slug: Mapped[
        str | None
    ] = mapped_column(
        String(512),
        nullable=True,
    )

    market_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    market_name: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    outcome_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    outcome_name: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    odds: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    total_odds: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    market_status: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    fixture_status: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    bet_status: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )
    
    leg_status: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
    )