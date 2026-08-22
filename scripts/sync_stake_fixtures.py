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

from backend.database.session import SessionLocal
from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)
from backend.integrations.stake.fixture_service import (
    StakeFixtureService,
)
from backend.services.stake_fixture_sync_service import (
    StakeFixtureSyncService,
)


async def main() -> None:
    db = SessionLocal()

    try:
        graphql_client = (
            StakeGraphQLClient()
        )

        fixture_service = (
            StakeFixtureService(
                graphql_client
            )
        )

        sync_service = (
            StakeFixtureSyncService(
                db=db,
                fixture_service=fixture_service,
            )
        )

        result = (
            await sync_service
            .sync_upcoming_soccer_totals(
                limit=10,
                offset=0,
            )
        )

        print(
            "\nSync Complete"
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