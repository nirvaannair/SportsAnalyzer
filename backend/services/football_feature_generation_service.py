from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.api_football_fixture import (
    APIFootballFixture,
)

from backend.database.models.api_football_team_statistic import (
    APIFootballTeamStatistic,
)

from backend.database.models.football_fixture_feature import (
    FootballFixtureFeature,
)


class FootballFeatureGenerationService:

    def __init__(
        self,
        db: Session,
    ) -> None:

        self.db = db

    def generate_for_fixture(
        self,
        fixture_id: int,
    ) -> bool:

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
            return False

        existing = (
            self.db.query(
                FootballFixtureFeature
            )
            .filter(
                FootballFixtureFeature.fixture_id
                == fixture.id
            )
            .first()
        )

        if existing:
            return False

        home_stats = (
            self.db.query(
                APIFootballTeamStatistic
            )
            .filter(
                APIFootballTeamStatistic.team_id
                == fixture.home_team_id,
                APIFootballTeamStatistic.league_id
                == fixture.league_id,
                APIFootballTeamStatistic.season
                == fixture.season,
            )
            .first()
        )

        away_stats = (
            self.db.query(
                APIFootballTeamStatistic
            )
            .filter(
                APIFootballTeamStatistic.team_id
                == fixture.away_team_id,
                APIFootballTeamStatistic.league_id
                == fixture.league_id,
                APIFootballTeamStatistic.season
                == fixture.season,
            )
            .first()
        )

        self.db.add(
            FootballFixtureFeature(
                fixture_id=fixture.id,
                home_team_id=fixture.home_team_id,
                away_team_id=fixture.away_team_id,
                league_id=fixture.league_id,
                season=fixture.season,

                home_played=(
                    home_stats.played
                    if home_stats
                    else None
                ),
                away_played=(
                    away_stats.played
                    if away_stats
                    else None
                ),

                home_wins=(
                    home_stats.wins
                    if home_stats
                    else None
                ),
                away_wins=(
                    away_stats.wins
                    if away_stats
                    else None
                ),

                home_draws=(
                    home_stats.draws
                    if home_stats
                    else None
                ),
                away_draws=(
                    away_stats.draws
                    if away_stats
                    else None
                ),

                home_losses=(
                    home_stats.losses
                    if home_stats
                    else None
                ),
                away_losses=(
                    away_stats.losses
                    if away_stats
                    else None
                ),

                home_goals_for=(
                    home_stats.goals_for
                    if home_stats
                    else None
                ),
                away_goals_for=(
                    away_stats.goals_for
                    if away_stats
                    else None
                ),

                home_goals_against=(
                    home_stats.goals_against
                    if home_stats
                    else None
                ),
                away_goals_against=(
                    away_stats.goals_against
                    if away_stats
                    else None
                ),

                home_goal_difference=(
                    home_stats.goal_difference
                    if home_stats
                    else None
                ),
                away_goal_difference=(
                    away_stats.goal_difference
                    if away_stats
                    else None
                ),

                home_clean_sheets=(
                    home_stats.clean_sheets
                    if home_stats
                    else None
                ),
                away_clean_sheets=(
                    away_stats.clean_sheets
                    if away_stats
                    else None
                ),

                home_failed_to_score=(
                    home_stats.failed_to_score
                    if home_stats
                    else None
                ),
                away_failed_to_score=(
                    away_stats.failed_to_score
                    if away_stats
                    else None
                ),

                home_form=(
                    home_stats.form
                    if home_stats
                    else None
                ),
                away_form=(
                    away_stats.form
                    if away_stats
                    else None
                ),

                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        self.db.commit()

        return True