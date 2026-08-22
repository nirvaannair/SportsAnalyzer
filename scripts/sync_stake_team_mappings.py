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

from backend.services.stake_team_mapping_sync_service import (
    StakeTeamMappingSyncService,
)


def main() -> None:

    db = SessionLocal()

    try:

        service = (
            StakeTeamMappingSyncService(
                db
            )
        )

        inserted = (
            service.sync()
        )

        print(
            "\nSTAKE TEAM MAPPINGS\n"
        )

        print(
            f"Inserted Mappings: {inserted}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()