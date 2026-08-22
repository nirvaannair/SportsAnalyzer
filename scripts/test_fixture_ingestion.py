from __future__ import annotations

import asyncio
import json
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
from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)
from backend.integrations.stake.fixture_service import (
    StakeFixtureService,
)


async def main() -> None:
    client = StakeGraphQLClient()

    service = StakeFixtureService(
        client=client,
    )

    fixtures = (
        await service.get_upcoming_soccer_totals(
            limit=10,
            offset=0,
        )
    )

    print(
        json.dumps(
            fixtures,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())