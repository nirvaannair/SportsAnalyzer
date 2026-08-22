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

from backend.services.api_football_league_sync_service import (
    APIFootballLeagueSyncService,
)


async def main() -> None:

    db = SessionLocal()

    try:

        client = (
            APIFootballClient()
        )

        service = (
            APIFootballLeagueSyncService(
                db,
                client,
            )
        )

        inserted = (
            await service.sync()
        )

        print(
            "\nLEAGUE SYNC\n"
        )

        print(
            f"Inserted: {inserted}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(
        main()
    )