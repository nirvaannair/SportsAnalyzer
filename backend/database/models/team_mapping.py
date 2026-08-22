from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class TeamMapping(Base):
    __tablename__ = "team_mappings"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        )
    )

    provider: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    provider_team_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    provider_name: Mapped[str] = mapped_column(
        String(255),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    team = relationship(
        "Team",
        back_populates="mappings",
    )