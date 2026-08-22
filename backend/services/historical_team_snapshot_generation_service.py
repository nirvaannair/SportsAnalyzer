from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.api_football_fixture import (
    APIFootballFixture,
)

from backend.database.models.historical_team_snapshot import (
    HistoricalTeamSnapshot,
)


class HistoricalTeamSnapshotGenerationService:

    def __init__(
        self,
        db: Session,
    ) -> None:

        self.db = db

    def generate_for_fixture(
        self,
        fixture_id: int,
    ) -> None:

        fixture = (
            self.db.query(
                APIFootballFixture
            )
            .filter(
                APIFootballFixture.id
                == fixture_id
            )
            .first()
        )

        if not fixture:
            return
        
        if (
            fixture.home_team_id
            == fixture.away_team_id
        ):
            return

        existing = (
            self.db.query(
                HistoricalTeamSnapshot
            )
            .filter(
                HistoricalTeamSnapshot.fixture_id
                == fixture.id
            )
            .first()
        )

        if existing:
            return

        self._create_snapshot(
            fixture=fixture,
            team_id=fixture.home_team_id,
        )

        self._create_snapshot(
            fixture=fixture,
            team_id=fixture.away_team_id,
        )

        self.db.commit()

    def _create_snapshot(
        self,
        fixture: APIFootballFixture,
        team_id: int,
    ) -> None:

        previous_matches = (
            self.db.query(
                APIFootballFixture
            )
            .filter(
                APIFootballFixture.fixture_date
                < fixture.fixture_date,
            )
            .filter(
                (
                    APIFootballFixture.home_team_id
                    == team_id
                )
                |
                (
                    APIFootballFixture.away_team_id
                    == team_id
                )
            )
            .order_by(
                APIFootballFixture.fixture_date.asc()
            )
            .all()
        )

        played = 0
        wins = 0
        draws = 0
        losses = 0

        goals_for = 0
        goals_against = 0

        recent_results: list[str] = []

        for match in previous_matches:

            played += 1

            is_home = (
                match.home_team_id
                == team_id
            )

            team_goals = (
                match.home_goals
                if is_home
                else match.away_goals
            )

            opponent_goals = (
                match.away_goals
                if is_home
                else match.home_goals
            )

            goals_for += team_goals
            goals_against += opponent_goals

            if team_goals > opponent_goals:

                wins += 1
                recent_results.append(
                    "W"
                )

            elif team_goals < opponent_goals:

                losses += 1
                recent_results.append(
                    "L"
                )

            else:

                draws += 1
                recent_results.append(
                    "D"
                )

        form = "".join(
            recent_results[-10:]
        )

        self.db.add(
            HistoricalTeamSnapshot(
                fixture_id=fixture.id,
                team_id=team_id,
                snapshot_date=fixture.fixture_date,

                played=played,
                wins=wins,
                draws=draws,
                losses=losses,

                goals_for=goals_for,
                goals_against=goals_against,

                goal_difference=(
                    goals_for
                    - goals_against
                ),

                form=form,

                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )