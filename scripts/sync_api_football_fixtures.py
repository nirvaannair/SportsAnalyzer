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

from backend.database.session import (
    SessionLocal,
)

from backend.database.models.__all_models import *

from backend.integrations.api_football.client import (
    APIFootballClient,
)

from backend.services.api_football_fixture_sync_service import (
    APIFootballFixtureSyncService,
)


async def main() -> None:

    db = SessionLocal()

    try:

        client = (
            APIFootballClient()
        )

        service = (
            APIFootballFixtureSyncService(
                db,
                client,
            )
        )

        total_inserted = 0

        for season in (
            2022,
            2023,
            2024,
        ):

            inserted = (
                await service.sync_league(
                    league_id=39,
                    season=season,
                )
            )

            print(
                f"Season {season}: {inserted}"
            )

            total_inserted += (
                inserted
            )

        print(
            "\nTOTAL FIXTURES:"
        )

        print(
            total_inserted
        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(
        main()
    )