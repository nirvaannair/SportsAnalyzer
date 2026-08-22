from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from backend.database.base import Base


class APIFootballLeague(Base):
    __tablename__ = "api_football_leagues"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    api_football_league_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    country: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    league_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    current: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    raw_json: Mapped[str] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )