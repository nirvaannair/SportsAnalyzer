from __future__ import annotations

from sqlalchemy import Boolean
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    market_id: Mapped[int] = mapped_column(
        ForeignKey(
            "markets.id",
            ondelete="CASCADE",
        )
    )

    stake_outcome_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    odds: Mapped[float] = mapped_column(
        Float,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    market = relationship(
        "Market",
        back_populates="outcomes",
    )