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


async def main() -> None:

    db = SessionLocal()

    try:

        client = APIFootballClient()

        team_service = (
            APIFootballTeamService(
                client
            )
        )

        sync_service = (
            APIFootballTeamSyncService(
                db=db,
                team_service=team_service,
            )
        )

        inserted = (
            await sync_service.sync_league(
                league_id=39,
                season=2024,
            )
        )

        print(
            "\nSYNC RESULTS\n"
        )

        print(
            f"Inserted Teams: {inserted}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(
        main()
    )