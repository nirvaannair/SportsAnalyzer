from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class BetHistory(Base):
    __tablename__ = "bet_history"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    stake_bet_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(100),
    )

    amount: Mapped[float] = mapped_column(
        Float,
    )

    payout: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    payout_multiplier: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    outcomes_json: Mapped[
        str
    ] = mapped_column(
        Text,
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