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


async def main() -> None:

    client = APIFootballClient()

    response = await client.get(
        "/teams",
        {
            "league": 39,
            "season": 2024,
        },
    )

    print(
        "\nFULL RESPONSE:\n"
    )

    print(
        response
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )