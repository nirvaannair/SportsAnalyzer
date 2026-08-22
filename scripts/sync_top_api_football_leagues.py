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

from backend.integrations.api_football.team_service import (
    APIFootballTeamService,
)
from backend.services.api_football_team_sync_service import (
    APIFootballTeamSyncService,
)


LEAGUES = [
    39,     # Premier League
    140,    # La Liga
    78,     # Bundesliga
    135,    # Serie A
    61,     # Ligue 1
    40,     # Championship
    88,     # Eredivisie
    94,     # Primeira Liga
    98,     # J League
    99,     # J League 2
]


async def main() -> None:

    db = SessionLocal()

    try:

        client = APIFootballClient()

        team_service = (
            APIFootballTeamService(
                client,
            )
        )

        service = (
            APIFootballTeamSyncService(
                db,
                team_service,
            )
        )

        total_inserted = 0

        for league_id in LEAGUES:

            inserted = (
                await service.sync_league(
                    league_id=league_id,
                    season=2024,
                )
            )

            print(
                f"League {league_id}: {inserted}"
            )

            total_inserted += inserted

        print(
            f"\nTOTAL INSERTED: {total_inserted}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(
        main()
    )