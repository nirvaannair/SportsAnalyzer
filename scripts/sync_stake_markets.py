from __future__ import annotations

import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)

import backend.database.models.__all_models

from backend.database.session import (
    SessionLocal,
)

from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)

from backend.integrations.stake.fixture_market_service import (
    StakeFixtureMarketService,
)

from backend.services.stake_market_sync_service import (
    StakeMarketSyncService,
)


async def main() -> None:
    db = SessionLocal()

    try:
        graphql_client = (
            StakeGraphQLClient()
        )

        market_service = (
            StakeFixtureMarketService(
                graphql_client
            )
        )

        sync_service = (
            StakeMarketSyncService(
                db=db,
                market_service=market_service,
            )
        )

        result = (
            await sync_service
            .sync_main_markets()
        )

        print(
            "\nMain Market Sync Complete"
        )

        print(
            f"Fixtures: {result['fixtures']}"
        )

        print(
            f"Groups: {result['groups']}"
        )

        print(
            f"Templates: {result['templates']}"
        )

        print(
            f"Markets: {result['markets']}"
        )

        print(
            f"Outcomes: {result['outcomes']}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(
        main()
    )