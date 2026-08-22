from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class MarketGroup(Base):
    __tablename__ = "market_groups"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    fixture_id: Mapped[int] = mapped_column(
        ForeignKey(
            "fixtures.id",
            ondelete="CASCADE",
        )
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    translation: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    rank: Mapped[
        int | None
    ] = mapped_column(
        nullable=True,
    )

    templates = relationship(
        "MarketTemplate",
        back_populates="group",
    )