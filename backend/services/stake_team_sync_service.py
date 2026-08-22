from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.fixture import (
    Fixture,
)

from backend.database.models.team import (
    Team,
)

from backend.database.models.sport import (
    Sport,
)


class StakeTeamSyncService:
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

    def sync(
        self,
    ) -> int:

        inserted = 0

        soccer = (
            self.db.query(
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

        fixtures = (
            self.db.query(
                Fixture
            )
            .all()
        )

        known_teams = {
            team.normalized_name
            for team in (
                self.db.query(
                    Team
                )
                .all()
            )
        }

        for fixture in fixtures:

            for team_name in (
                fixture.home_team,
                fixture.away_team,
            ):

                if not team_name:
                    continue

                normalized_name = (
                    self._normalize(
                        team_name
                    )
                )

                if (
                    normalized_name
                    in known_teams
                ):
                    continue

                self.db.add(
                    Team(
                        sport_id=soccer.id,
                        name=team_name,
                        normalized_name=normalized_name,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
                
                known_teams.add(
                    normalized_name
                )

                inserted += 1

        self.db.commit()

        return inserted