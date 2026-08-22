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

from sqlalchemy import select

from backend.database.session import (
    SessionLocal,
)

from backend.database.models.fixture import (
    Fixture,
)

from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)

from backend.integrations.stake.main_market_service import (
    StakeMainMarketService,
)

from backend.services.stake_main_market_sync_service import (
    StakeMainMarketSyncService,
)


async def main() -> None:
    db = SessionLocal()

    try:
        graphql_client = (
            StakeGraphQLClient()
        )

        main_market_service = (
            StakeMainMarketService(
                graphql_client
            )
        )

        sync_service = (
            StakeMainMarketSyncService(
                db=db,
                main_market_service=(
                    main_market_service
                ),
            )
        )

        fixtures = db.scalars(
            select(
                Fixture
            )
        ).all()

        total_groups = 0
        total_templates = 0
        total_markets = 0
        total_outcomes = 0

        print(
            f"\nFound {len(fixtures)} fixtures\n"
        )

        for fixture in fixtures:
            print(
                f"Syncing: "
                f"{fixture.fixture_slug}"
            )

            result = (
                await sync_service
                .sync_fixture(
                    fixture.fixture_slug
                )
            )

            total_groups += (
                result["groups"]
            )

            total_templates += (
                result["templates"]
            )

            total_markets += (
                result["markets"]
            )

            total_outcomes += (
                result["outcomes"]
            )

        print(
            "\nWinner Market Sync Complete\n"
        )

        print(
            f"Groups: "
            f"{total_groups}"
        )

        print(
            f"Templates: "
            f"{total_templates}"
        )

        print(
            f"Markets: "
            f"{total_markets}"
        )

        print(
            f"Outcomes: "
            f"{total_outcomes}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(
        main()
    )