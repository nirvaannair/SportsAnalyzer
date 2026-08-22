from __future__ import annotations

import json

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.api_football_team import (
    APIFootballTeam,
)

from backend.integrations.api_football.team_service import (
    APIFootballTeamService,
)


class APIFootballTeamSyncService:
    def __init__(
        self,
        db: Session,
        team_service: APIFootballTeamService,
    ) -> None:
        self.db = db
        self.team_service = team_service

    async def sync_league(
        self,
        league_id: int,
        season: int,
    ) -> int:

        inserted = 0

        teams = (
            await self.team_service.get_teams(
                league_id=league_id,
                season=season,
            )
        )

        for item in teams:

            team = item.get(
                "team",
                {},
            )

            venue = item.get(
                "venue",
                {},
            )

            existing = (
                self.db.query(
                    APIFootballTeam
                )
                .filter(
                    APIFootballTeam.api_football_team_id
                    == team["id"]
                )
                .first()
            )

            if existing:
                continue

            self.db.add(
                APIFootballTeam(
                    api_football_team_id=team["id"],
                    name=team.get(
                        "name"
                    ),
                    code=team.get(
                        "code"
                    ),
                    country=team.get(
                        "country"
                    ),
                    founded=team.get(
                        "founded"
                    ),
                    national=team.get(
                        "national"
                    ),
                    logo_url=team.get(
                        "logo"
                    ),
                    venue_id=venue.get(
                        "id"
                    ),
                    venue_name=venue.get(
                        "name"
                    ),
                    venue_city=venue.get(
                        "city"
                    ),
                    venue_capacity=venue.get(
                        "capacity"
                    ),
                    venue_surface=venue.get(
                        "surface"
                    ),
                    raw_json=json.dumps(
                        item
                    ),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

            inserted += 1

        self.db.commit()

        return inserted