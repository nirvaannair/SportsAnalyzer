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

from backend.integrations.api_football.client import (
    APIFootballClient,
)

from backend.integrations.api_football.team_service import (
    APIFootballTeamService,
)


async def main() -> None:

    client = APIFootballClient()

    service = APIFootballTeamService(
        client,
    )

    response = (
        await service.get_team_statistics(
            league_id=39,
            season=2024,
            team_id=50,
        )
    )

    print(
        "\nRAW RESPONSE KEYS\n"
    )

    print(
        list(
            response.keys()
        )
    )

    data = response.get(
        "response",
        {}
    )

    print(
        "\nRESPONSE KEYS\n"
    )

    print(
        list(
            data.keys()
        )
    )

    print(
        "\nFULL RESPONSE SAMPLE\n"
    )

    print(
        json.dumps(
            data,
            indent=2,
        )[:5000]
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )