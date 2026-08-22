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

from backend.services.api_football_team_matching_service import (
    APIFootballTeamMatchingService,
)


def main() -> None:

    db = SessionLocal()

    try:

        service = (
            APIFootballTeamMatchingService(
                db
            )
        )

        inserted = (
            service.match()
        )

        print(
            "\nAPI FOOTBALL MATCHING\n"
        )

        print(
            f"Inserted: {inserted}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()