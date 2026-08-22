from __future__ import annotations

from pathlib import Path
import sys

from rapidfuzz import fuzz


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

from backend.database.models.team import Team

from backend.database.models.team_mapping import (
    TeamMapping,
)

from backend.database.models.api_football_team import (
    APIFootballTeam,
)
from backend.database.models.__all_models import *

def main() -> None:

    db = SessionLocal()

    try:

        teams = (
            db.query(
                Team
            )
            .all()
        )

        mapped_provider_ids = {
            row.provider_team_id
            for row in (
                db.query(
                    TeamMapping
                )
                .filter(
                    TeamMapping.provider
                    == "api_football"
                )
                .all()
            )
        }

        api_teams = (
            db.query(
                APIFootballTeam
            )
            .all()
        )

        for api_team in api_teams:

            if (
                str(
                    api_team.api_football_team_id
                )
                in mapped_provider_ids
            ):
                continue

            best_score = 0
            best_match = None

            for team in teams:

                score = fuzz.token_sort_ratio(
                    api_team.name.lower(),
                    team.normalized_name,
                )

                if score > best_score:

                    best_score = score
                    best_match = team

            print(
                f"{api_team.name}"
                f" -> "
                f"{best_match.name}"
                f" ({best_score:.2f})"
            )

    finally:

        db.close()


if __name__ == "__main__":
    main()
    