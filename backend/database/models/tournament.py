from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    stake_tournament_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )

    sport_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sports.id",
            ondelete="CASCADE",
        )
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    sport = relationship(
        "Sport",
        back_populates="tournaments",
    )

    fixtures = relationship(
        "Fixture",
        back_populates="tournament",
    )