from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    fixture_id: Mapped[int] = mapped_column(
        ForeignKey(
            "fixtures.id",
            ondelete="CASCADE",
        )
    )

    stake_market_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )

    market_name: Mapped[str] = mapped_column(
        String(255),
    )

    template_id: Mapped[int] = mapped_column(
        ForeignKey(
            "market_templates.id",
            ondelete="CASCADE",
        )
    )

    template = relationship(
        "MarketTemplate",
        back_populates="markets",
    )

    line_value: Mapped[
        float | None
    ] = mapped_column(
        nullable=True,
    )

    line_type: Mapped[
        str | None
    ] = mapped_column(
        String(50),
        nullable=True,
    )

    provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(100),
    )

    fixture = relationship(
        "Fixture",
        back_populates="markets",
    )

    outcomes = relationship(
        "Outcome",
        back_populates="market",
    )