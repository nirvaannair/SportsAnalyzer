from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Prediction(Base):
    __tablename__ = "predictions"

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

    predicted_probability: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    implied_probability: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    expected_value: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    confidence_score: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    model_version: Mapped[
        str
    ] = mapped_column(
        String(100),
    )

    analysis_json: Mapped[
        str
    ] = mapped_column(
        Text,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
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