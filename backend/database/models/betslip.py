from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class BetSlip(Base):
    __tablename__ = "bet_slips"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    stake_bet_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(100),
    )

    total_odds: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    stake_amount: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    potential_return: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    selections_json: Mapped[
        str
    ] = mapped_column(
        Text,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
    )