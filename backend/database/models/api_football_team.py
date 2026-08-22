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


class APIFootballTeam(Base):
    __tablename__ = "api_football_teams"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    api_football_team_id: Mapped[int] = mapped_column(
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    code: Mapped[
        str | None
    ] = mapped_column(
        String(50),
        nullable=True,
    )

    country: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    founded: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    national: Mapped[
        bool | None
    ] = mapped_column(
        Boolean,
        nullable=True,
    )

    logo_url: Mapped[
        str | None
    ] = mapped_column(
        String(1024),
        nullable=True,
    )

    venue_id: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    venue_name: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    venue_city: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    venue_capacity: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    venue_surface: Mapped[
        str | None
    ] = mapped_column(
        String(100),
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