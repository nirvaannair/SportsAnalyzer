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

from backend.integrations.stake.fixture_market_service import (
    StakeFixtureMarketService,
)


async def main() -> None:
    db = SessionLocal()

    try:
        fixture = db.scalar(
            select(
                Fixture
            ).limit(
                1
            )
        )

        if not fixture:
            print(
                "No fixtures found."
            )
            return

        print(
            f"Fixture: {fixture.name}"
        )

        print(
            f"Slug: {fixture.fixture_slug}"
        )

        client = (
            StakeGraphQLClient()
        )

        service = (
            StakeFixtureMarketService(
                client
            )
        )

        data = (
            await service.get_fixture_main_markets(
                fixture.fixture_slug
            )
        )

        groups = data.get(
            "group",
            [],
        )

        print(
            f"\nGroups Found: {len(groups)}"
        )

        for group in groups:
            print(
                f"\nGROUP: {group['name']}"
            )

            for template in group.get(
                "templates",
                [],
            ):
                print(
                    f"\n  TEMPLATE: {template['name']}"
                )

                for market in template.get(
                    "markets",
                    [],
                ):
                    print(
                        f"\n    MARKET: {market['name']}"
                    )

                    for outcome in market.get(
                        "outcomes",
                        [],
                    ):
                        print(
                            f"      {outcome['name']} -> {outcome['odds']}"
                        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(
        main()
    )