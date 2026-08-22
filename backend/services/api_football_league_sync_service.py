from __future__ import annotations

import json

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.api_football_league import (
    APIFootballLeague,
)

from backend.integrations.api_football.client import (
    APIFootballClient,
)


class APIFootballLeagueSyncService:
    def __init__(
        self,
        db: Session,
        client: APIFootballClient,
    ) -> None:
        self.db = db
        self.client = client

    async def sync(self) -> int:

        inserted = 0

        response = await self.client.get(
            "/leagues",
        )

        leagues = response.get(
            "response",
            [],
        )

        for item in leagues:

            league = item.get(
                "league",
                {},
            )

            country = item.get(
                "country",
                {},
            )

            seasons = item.get(
                "seasons",
                [],
            )

            current = None

            for season in seasons:

                if season.get(
                    "current"
                ):
                    current = True
                    break

            league_id = league.get(
                "id"
            )

            existing = (
                self.db.query(
                    APIFootballLeague
                )
                .filter(
                    APIFootballLeague.api_football_league_id
                    == league_id
                )
                .first()
            )

            if existing:
                continue

            self.db.add(
                APIFootballLeague(
                    api_football_league_id=league_id,
                    name=league.get(
                        "name"
                    ),
                    country=country.get(
                        "name"
                    ),
                    league_type=league.get(
                        "type"
                    ),
                    current=current,
                    logo_url=league.get(
                        "logo"
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