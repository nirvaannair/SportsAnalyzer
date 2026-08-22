from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.api_football_team import (
    APIFootballTeam,
)

from backend.database.models.team import (
    Team,
)

from backend.database.models.team_mapping import (
    TeamMapping,
)


class TeamSyncService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def _normalize(
        self,
        name: str,
    ) -> str:
        return (
            name
            .strip()
            .lower()
        )

    def sync_api_football(
        self,
        sport_id: int,
    ) -> int:

        inserted = 0

        api_teams = (
            self.db.query(
                APIFootballTeam
            )
            .all()
        )

        for api_team in api_teams:

            normalized_name = (
                self._normalize(
                    api_team.name
                )
            )

            team = (
                self.db.query(
                    Team
                )
                .filter(
                    Team.normalized_name
                    == normalized_name
                )
                .first()
            )

            if not team:

                team = Team(
                    sport_id=sport_id,
                    name=api_team.name,
                    normalized_name=normalized_name,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )

                self.db.add(
                    team
                )

                self.db.flush()

                inserted += 1

            mapping = (
                self.db.query(
                    TeamMapping
                )
                .filter(
                    TeamMapping.provider
                    == "api_football",
                    TeamMapping.provider_team_id
                    == str(
                        api_team.api_football_team_id
                    ),
                )
                .first()
            )

            if mapping:
                continue

            self.db.add(
                TeamMapping(
                    team_id=team.id,
                    provider="api_football",
                    provider_team_id=str(
                        api_team.api_football_team_id
                    ),
                    provider_name=api_team.name,
                    created_at=datetime.utcnow(),
                )
            )

        self.db.commit()

        return inserted