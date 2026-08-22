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


LEAGUES = [
    # 39,     # Premier League
    # 40,     # Championship
    # 98,     # J League
    99,     # J League 2
    135,    # Serie A
    78,     # Bundesliga
    140,    # La Liga
]

SEASONS = [
    # 2022,
    2023,
    2024,
]


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

        for league_id in LEAGUES:

            print(
                f"\nLEAGUE {league_id}"
            )

            for season in SEASONS:

                inserted = (
                    await service.sync_league(
                        league_id=league_id,
                        season=season,
                    )
                )

                await asyncio.sleep(3)

                print(
                    f"Season {season}: {inserted}"
                )

                total_inserted += (
                    inserted
                )

        print(
            "\nTOTAL INSERTED"
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