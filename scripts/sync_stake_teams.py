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

from backend.services.stake_team_sync_service import (
    StakeTeamSyncService,
)


def main() -> None:

    db = SessionLocal()

    try:

        service = (
            StakeTeamSyncService(
                db
            )
        )

        inserted = (
            service.sync()
        )

        print(
            "\nSTAKE TEAM SYNC\n"
        )

        print(
            f"Inserted Teams: {inserted}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()