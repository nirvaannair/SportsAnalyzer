from __future__ import annotations

from datetime import datetime
from datetime import timezone

from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.database.models.market import Market
from backend.database.models.outcome import Outcome
from backend.database.models.odds_snapshot import (
    OddsSnapshot,
)
from backend.database.models.fixture import (
    Fixture,
)

class OddsSnapshotService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def capture_all_current_odds(
        self,
    ) -> int:
        outcomes = self.db.scalars(
            select(
                Outcome
            )
        ).all()

        snapshot_count = 0

        for outcome in outcomes:
            market = self.db.scalar(
                select(
                    Market
                ).where(
                    Market.id
                    == outcome.market_id
                )
            )

            if market is None:
                continue

            fixture = self.db.scalar(
                select(
                    Fixture
                ).where(
                    Fixture.id
                    == market.fixture_id
                )
            )

            if fixture is None:
                continue

            if fixture.status.lower() not in [
                "not_started",
                "upcoming",
            ]:
                continue

            snapshot = OddsSnapshot(
                fixture_id=market.fixture_id,
                market_id=market.id,
                outcome_id=outcome.id,
                odds=outcome.odds,
                captured_at=datetime.now(
                    timezone.utc
                ),
            )

            self.db.add(
                snapshot
            )

            snapshot_count += 1

        self.db.commit()

        return snapshot_count