from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(
        primary_key=True,
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

    normalized_name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    sport = relationship(
        "Sport",
    )

    mappings = relationship(
        "TeamMapping",
        back_populates="team",
    )   