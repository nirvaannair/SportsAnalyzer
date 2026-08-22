from __future__ import annotations

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

from backend.services.team_sync_service import (
    TeamSyncService,
)
from backend.database.models.sport import (
    Sport,
)

def main() -> None:

    db = SessionLocal()

    try:

        service = (
            TeamSyncService(
                db
            )
        )

        soccer = (
            db.query(
                Sport
            )
            .filter(
                Sport.slug
                == "soccer"
            )
            .first()
        )

        if not soccer:
            raise RuntimeError(
                "Soccer sport not found"
            )

        inserted = (
            service.sync_api_football(
                sport_id=soccer.id,
            )
        )

        print(
            "\nCANONICAL TEAM SYNC\n"
        )

        print(
            f"Inserted Teams: {inserted}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()