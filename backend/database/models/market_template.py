from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class MarketTemplate(Base):
    __tablename__ = "market_templates"

    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "stake_template_ext_id",
            name="uq_market_template_group_extid",
        ),
    )


    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey(
            "market_groups.id",
            ondelete="CASCADE",
        )
    )

    stake_template_ext_id: Mapped[
        str
    ] = mapped_column(
        String(255),
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    rank: Mapped[
        int | None
    ] = mapped_column(
        nullable=True,
    )

    group = relationship(
        "MarketGroup",
        back_populates="templates",
    )

    markets = relationship(
        "Market",
        back_populates="template",
    )