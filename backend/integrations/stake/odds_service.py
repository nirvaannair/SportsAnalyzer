from __future__ import annotations

from backend.integrations.stake.fixture_service import (
    StakeFixtureService,
)

from backend.integrations.stake.models import (
    StakeFixture,
)


class StakeOddsService:
    def __init__(
        self,
        fixture_service: StakeFixtureService,
    ) -> None:
        self.fixture_service = (
            fixture_service
        )

    async def get_total_markets(
        self,
        limit: int = 100,
    ) -> list[StakeFixture]:
        return await (
            self.fixture_service
            .get_upcoming_soccer_fixtures(
                limit=limit,
                group="Total",
            )
        )

    async def get_winner_markets(
        self,
        limit: int = 100,
    ) -> list[StakeFixture]:
        return await (
            self.fixture_service
            .get_upcoming_soccer_fixtures(
                limit=limit,
                group="Main",
            )
        )