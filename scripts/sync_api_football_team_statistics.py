from __future__ import annotations

import asyncio

from pathlib import Path

import sys

from sqlalchemy import or_

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

from backend.database.models.api_football_fixture import (
    APIFootballFixture,
)

from backend.database.models.api_football_league import (
    APIFootballLeague,
)

from backend.database.models.team_mapping import (
    TeamMapping,
)

from backend.integrations.api_football.client import (
    APIFootballClient,
)

from backend.services.api_football_team_statistics_sync_service import (
    APIFootballTeamStatisticsSyncService,
)

from backend.database.models.api_football_team_statistic import (
    APIFootballTeamStatistic,
)

async def main() -> None:

    db = SessionLocal()

    try:

        client = (
            APIFootballClient()
        )

        service = (
            APIFootballTeamStatisticsSyncService(
                db,
                client,
            )
        )

        leagues = (
            db.query(
                APIFootballLeague
            )
            .filter(
                APIFootballLeague.api_football_league_id.in_(
                    [
                        39,
                        40,
                        78,
                        98,
                        99,
                        135,
                        140,
                    ]
                )
            )
            .all()
        )

        total_inserted = 0

        for league in leagues:

            league_id = (
                league.api_football_league_id
            )

            print(
                f"\nLEAGUE {league_id}"
            )

            seasons = (
                db.query(
                    APIFootballFixture.season
                )
                .filter(
                    APIFootballFixture.league_id
                    == league_id
                )
                .distinct()
                .all()
            )

            seasons = [
                row[0]
                for row in seasons
            ]

            for season in seasons:

                print(
                    f"  Season {season}"
                )

                team_ids = (
                    db.query(
                        TeamMapping.provider_team_id
                    )
                    .join(
                        APIFootballFixture,
                        or_(
                            APIFootballFixture.home_team_id
                            == TeamMapping.team_id,
                            APIFootballFixture.away_team_id
                            == TeamMapping.team_id,
                        ),
                    )
                    .filter(
                        TeamMapping.provider
                        == "api_football",
                        APIFootballFixture.league_id
                        == league_id,
                        APIFootballFixture.season
                        == season,
                    )
                    .distinct()
                    .all()
                )
                
                team_ids = [
                    int(row[0])
                    for row in team_ids
                ]
                
                season_inserted = 0
                
                for api_football_team_id in team_ids:

                    try:

                        was_inserted  = await service.sync_team_statistics(
                            league_id=league_id,
                            season=season,
                            api_football_team_id=api_football_team_id,
                        )

                    except RuntimeError as exc:

                        if (
                            str(exc)
                            == "API_FOOTBALL_DAILY_LIMIT_REACHED"
                        ):
                            print(
                                "\nStopping because "
                                "daily API quota is exhausted."
                            )
                            return

                        raise

                    if was_inserted:
                        season_inserted += 1

                    await asyncio.sleep(
                        8
                    )
                print(
                    f"    Inserted: {season_inserted}"
                )

                total_inserted += (
                    season_inserted
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