from __future__ import annotations

from rapidfuzz import fuzz

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.team import Team

from backend.database.models.team_mapping import (
    TeamMapping,
)

from backend.database.models.api_football_team import (
    APIFootballTeam,
)


class APIFootballTeamMatchingService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def match(
        self,
        min_score: int = 85,
    ) -> int:

        inserted = 0

        teams = [
            team
            for team in (
                self.db.query(
                    Team
                )
                .all()
            )
            if self._is_primary_team(
                team
            )
        ]

        api_teams = (
            self.db.query(
                APIFootballTeam
            )
            .all()
        )

        existing_team_ids = {
            row.team_id
            for row in (
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

        for api_team in api_teams:

            best_team = None
            best_score = 0

            api_name = (
                api_team.name
                .lower()
                .strip()
            )

            for team in teams:

                if team.id in existing_team_ids:
                    continue

                score = max(
                    fuzz.ratio(
                        api_name,
                        team.normalized_name,
                    ),
                    fuzz.partial_ratio(
                        api_name,
                        team.normalized_name,
                    ),
                    fuzz.token_sort_ratio(
                        api_name,
                        team.normalized_name,
                    ),
                )

                if score > best_score:
                    best_score = score
                    best_team = team

            if (
                best_team
                and best_score >= min_score
            ):

                self.db.add(
                    TeamMapping(
                        team_id=best_team.id,
                        provider="api_football",
                        provider_team_id=str(
                            api_team.api_football_team_id
                        ),
                        provider_name=api_team.name,
                        created_at=datetime.utcnow(),
                    )
                )

                inserted += 1

        self.db.commit()
        
        return inserted
        
        
    def _is_primary_team(
        self,
        team: Team,
    ) -> bool:

        name = (
            team.normalized_name
            .lower()
            .strip()
        )

        blocked_terms = [
            " srl",
            " jong ",
            " women",
            " u19",
            " u20",
            " u21",
            " u23",
            " ii",
            " b team",
        ]

        return not any(
            term in name
            for term in blocked_terms
        )

        return inserted