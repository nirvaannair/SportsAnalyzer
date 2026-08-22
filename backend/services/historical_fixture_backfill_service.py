from __future__ import annotations

import json
from email.utils import parsedate_to_datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.bet_history import (
    BetHistory,
)

from backend.database.models.fixture import (
    Fixture,
)

from backend.database.models.sport import (
    Sport,
)

from backend.database.models.tournament import (
    Tournament,
)


class HistoricalFixtureBackfillService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def backfill(self) -> dict:
        counts = {
            "sports": 0,
            "tournaments": 0,
            "fixtures": 0,
        }

        histories = (
            self.db.query(
                BetHistory
            )
            .all()
        )

        for history in histories:
            outcomes = json.loads(
                history.outcomes_json
            )

            for outcome in outcomes:
                fixture = outcome.get(
                    "fixture",
                    {}
                )

                tournament = (
                    fixture.get(
                        "tournament",
                        {}
                    )
                )

                category = (
                    tournament.get(
                        "category",
                        {}
                    )
                )

                sport_data = (
                    category.get(
                        "sport",
                        {}
                    )
                )

                if (
                    not fixture
                    or not tournament
                    or not sport_data
                ):
                    continue

                sport = (
                    self._upsert_sport(
                        sport_data
                    )
                )

                if sport:
                    counts[
                        "sports"
                    ] += 1

                tournament_obj = (
                    self._upsert_tournament(
                        tournament,
                        sport.id,
                    )
                )

                if tournament_obj:
                    counts[
                        "tournaments"
                    ] += 1

                created = (
                    self._upsert_fixture(
                        fixture,
                        tournament_obj.id,
                    )
                )

                if created:
                    counts[
                        "fixtures"
                    ] += 1

        self.db.commit()

        return counts

    def _upsert_sport(
        self,
        sport_data: dict,
    ) -> Sport:
        existing = (
            self.db.scalar(
                select(
                    Sport
                ).where(
                    Sport.stake_sport_id
                    == sport_data["id"]
                )
            )
        )

        if existing:
            return existing

        sport = Sport(
            stake_sport_id=sport_data[
                "id"
            ],
            name=sport_data[
                "name"
            ],
            slug=sport_data[
                "slug"
            ],
        )

        self.db.add(
            sport
        )

        self.db.flush()

        return sport

    def _upsert_tournament(
        self,
        tournament_data: dict,
        sport_id: int,
    ) -> Tournament:
        existing = (
            self.db.scalar(
                select(
                    Tournament
                ).where(
                    Tournament.stake_tournament_id
                    == tournament_data[
                        "id"
                    ]
                )
            )
        )

        if existing:
            return existing

        tournament = Tournament(
            stake_tournament_id=
            tournament_data["id"],
            sport_id=sport_id,
            name=tournament_data[
                "name"
            ],
            slug=tournament_data[
                "slug"
            ],
        )

        self.db.add(
            tournament
        )

        self.db.flush()

        return tournament

    def _upsert_fixture(
        self,
        fixture_data: dict,
        tournament_id: int,
    ) -> bool:
        existing = (
            self.db.scalar(
                select(
                    Fixture
                ).where(
                    Fixture.stake_fixture_id
                    == fixture_data[
                        "id"
                    ]
                )
            )
        )

        if existing:
            return False

        data = fixture_data.get(
            "data",
            {},
        )

        teams = data.get(
            "teams",
            [],
        )

        home_team = ""
        away_team = ""

        for team in teams:
            if (
                team.get(
                    "qualifier"
                )
                == "home"
            ):
                home_team = team.get(
                    "name",
                    "",
                )

            if (
                team.get(
                    "qualifier"
                )
                == "away"
            ):
                away_team = team.get(
                    "name",
                    "",
                )

        start_time_raw = data.get(
            "startTime"
        )

        if not start_time_raw:
            return False

        start_time = (
            parsedate_to_datetime(
                start_time_raw
            )
        )

        self.db.add(
            Fixture(
                stake_fixture_id=
                fixture_data["id"],
                tournament_id=
                tournament_id,
                fixture_slug=
                fixture_data["slug"],
                name=
                fixture_data["name"],
                home_team=
                home_team,
                away_team=
                away_team,
                provider=None,
                status=
                fixture_data.get(
                    "status",
                    "unknown",
                ),
                market_count=0,
                start_time=
                start_time,
            )
        )

        self.db.flush()

        return True