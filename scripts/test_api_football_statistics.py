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

from backend.integrations.api_football.client import (
    APIFootballClient,
)

from backend.integrations.api_football.team_service import (
    APIFootballTeamService,
)


async def main() -> None:

    client = APIFootballClient()

    service = (
        APIFootballTeamService(
            client
        )
    )

    response = (
        await service.get_team_statistics(
            league_id=39,
            season=2024,
            team_id=33,
        )
    )

    print(
        "\nFULL RESPONSE\n"
    )

    print(
        response
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )