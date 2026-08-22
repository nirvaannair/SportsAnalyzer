from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Float

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    fixture_id: Mapped[int] = mapped_column(
        ForeignKey(
            "fixtures.id",
            ondelete="CASCADE",
        )
    )

    market_id: Mapped[int] = mapped_column(
        ForeignKey(
            "markets.id",
            ondelete="CASCADE",
        )
    )

    outcome_id: Mapped[int] = mapped_column(
        ForeignKey(
            "outcomes.id",
            ondelete="CASCADE",
        )
    )

    odds: Mapped[float] = mapped_column(
        Float,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(
            timezone=True,
        ),
        nullable=False,
    )

    fixture = relationship(
        "Fixture",
    )

    market = relationship(
        "Market",
    )

    outcome = relationship(
        "Outcome",
    )