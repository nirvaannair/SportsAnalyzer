from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.team import (
    Team,
)

from backend.database.models.team_mapping import (
    TeamMapping,
)


class StakeTeamMappingSyncService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def sync(
        self,
    ) -> int:

        inserted = 0

        existing_mappings = {
            (
                mapping.provider,
                mapping.provider_name,
            )
            for mapping in (
                self.db.query(
                    TeamMapping
                )
                .filter(
                    TeamMapping.provider
                    == "stake"
                )
                .all()
            )
        }

        teams = (
            self.db.query(
                Team
            )
            .all()
        )

        for team in teams:

            key = (
                "stake",
                team.name,
            )

            if key in existing_mappings:
                continue

            self.db.add(
                TeamMapping(
                    team_id=team.id,
                    provider="stake",
                    provider_team_id=None,
                    provider_name=team.name,
                    created_at=datetime.utcnow(),
                )
            )

            inserted += 1

        self.db.commit()

        return inserted