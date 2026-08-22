from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    stake_sport_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    tournaments = relationship(
        "Tournament",
        back_populates="sport",
    )