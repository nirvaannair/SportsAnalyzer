from __future__ import annotations

import json

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.api_football_fixture import (
    APIFootballFixture,
)

from backend.database.models.team_mapping import (
    TeamMapping,
)

from backend.integrations.api_football.client import (
    APIFootballClient,
)


class APIFootballFixtureSyncService:
    def __init__(
        self,
        db: Session,
        client: APIFootballClient,
    ) -> None:
        self.db = db
        self.client = client

    async def sync_league(
        self,
        league_id: int,
        season: int,
    ) -> int:

        inserted = 0

        response = await self.client.get(
            "/fixtures",
            {
                "league": league_id,
                "season": season,
            },
        )

        fixtures = response.get(
            "response",
            [],
        )
        
        mapping_lookup = {
            mapping.provider_team_id: mapping.team_id
            for mapping in (
                self.db.query(
                    TeamMapping
                )
                .filter(
                    TeamMapping.provider
                    == "api_football"
                )
                .all()
            )
        }        
        

        for fixture_data in fixtures:

            fixture_info = (
                fixture_data.get(
                    "fixture",
                    {}
                )
            )

            fixture_id = (
                fixture_info.get(
                    "id"
                )
            )

            existing = (
                self.db.query(
                    APIFootballFixture
                )
                .filter(
                    APIFootballFixture.api_football_fixture_id
                    == fixture_id
                )
                .first()
            )

            if existing:
                continue

            home_api_id = (
                fixture_data
                .get(
                    "teams",
                    {}
                )
                .get(
                    "home",
                    {}
                )
                .get(
                    "id"
                )
            )

            away_api_id = (
                fixture_data
                .get(
                    "teams",
                    {}
                )
                .get(
                    "away",
                    {}
                )
                .get(
                    "id"
                )
            )

            home_team_id = (
                mapping_lookup.get(
                    str(home_api_id)
                )
            )

            away_team_id = (
                mapping_lookup.get(
                    str(away_api_id)
                )
            )

            if (
                not home_team_id
                or not away_team_id
            ):
                continue

            goals = (
                fixture_data.get(
                    "goals",
                    {}
                )
            )

            home_goals = (
                goals.get(
                    "home"
                )
            )

            away_goals = (
                goals.get(
                    "away"
                )
            )

            winner_team_id = None

            if (
                home_goals
                is not None
                and away_goals
                is not None
            ):

                if (
                    home_goals
                    > away_goals
                ):
                    winner_team_id = (
                        home_team_id
                    )

                elif (
                    away_goals
                    > home_goals
                ):
                    winner_team_id = (
                        away_team_id
                    )

            self.db.add(
                APIFootballFixture(
                    api_football_fixture_id=fixture_id,
                    league_id=league_id,
                    season=season,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    winner_team_id=winner_team_id,
                    status=(
                        fixture_info
                        .get(
                            "status",
                            {}
                        )
                        .get(
                            "short"
                        )
                    ),
                    fixture_date=datetime.fromisoformat(
                        fixture_info[
                            "date"
                        ].replace(
                            "Z",
                            "+00:00",
                        )
                    ),
                    raw_json=json.dumps(
                        fixture_data
                    ),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

            inserted += 1

        self.db.commit()

        return inserted
    
    