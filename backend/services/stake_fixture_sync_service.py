from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.sport import Sport
from backend.database.models.tournament import Tournament
from backend.database.models.fixture import Fixture
from backend.database.models.market_group import MarketGroup
from backend.database.models.market_template import MarketTemplate
from backend.database.models.market import Market
from backend.database.models.outcome import Outcome

from backend.integrations.stake.fixture_service import (
    StakeFixtureService,
)


class StakeFixtureSyncService:
    def __init__(
        self,
        db: Session,
        fixture_service: StakeFixtureService,
    ) -> None:
        self.db = db
        self.fixture_service = fixture_service

    async def sync_upcoming_soccer_totals(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        fixtures = (
            await self.fixture_service.get_upcoming_soccer_totals(
                limit=limit,
                offset=offset,
            )
        )

        counts = {
            "sports": 0,
            "tournaments": 0,
            "fixtures": 0,
            "groups": 0,
            "templates": 0,
            "markets": 0,
            "outcomes": 0,
        }

        for fixture_data in fixtures:
            sport = self._upsert_sport(
                fixture_data,
            )

            tournament = self._upsert_tournament(
                fixture_data,
                sport.id,
            )

            fixture = self._upsert_fixture(
                fixture_data,
                tournament.id,
            )

            counts["fixtures"] += 1

            for group_data in fixture_data.get(
                "groups",
                [],
            ):
                group = self._upsert_market_group(
                    fixture.id,
                    group_data,
                )

                counts["groups"] += 1

                for template_data in group_data.get(
                    "templates",
                    [],
                ):
                    template = (
                        self._upsert_market_template(
                            group.id,
                            template_data,
                        )
                    )

                    counts["templates"] += 1

                    for market_data in template_data.get(
                        "markets",
                        [],
                    ):
                        market = self._upsert_market(
                            fixture.id,
                            template.id,
                            market_data,
                        )

                        counts["markets"] += 1

                        for outcome_data in market_data.get(
                            "outcomes",
                            [],
                        ):
                            self._upsert_outcome(
                                market.id,
                                outcome_data,
                            )

                            counts["outcomes"] += 1

        self.db.commit()

        return counts

    def _upsert_sport(
        self,
        fixture_data: dict,
    ) -> Sport:
        sport_data = (
            fixture_data["tournament"]
            ["category"]
            ["sport"]
        )

        existing = self.db.scalar(
            select(
                Sport
            ).where(
                Sport.stake_sport_id
                == sport_data["id"]
            )
        )

        if existing:
            if existing:
                existing.name = sport_data["name"]
                existing.slug = sport_data["slug"]

                return existing

        sport = Sport(
            stake_sport_id=sport_data["id"],
            name=sport_data["name"],
            slug=sport_data["slug"],
        )

        self.db.add(
            sport
        )

        self.db.flush()

        return sport

    def _upsert_tournament(
        self,
        fixture_data: dict,
        sport_id: int,
    ) -> Tournament:
        tournament_data = (
            fixture_data["tournament"]
        )

        existing = self.db.scalar(
            select(
                Tournament
            ).where(
                Tournament.stake_tournament_id
                == tournament_data[
                    "stake_tournament_id"
                ]
            )
        )

        if existing:
            return existing

        tournament = Tournament(
            stake_tournament_id=tournament_data[
                "stake_tournament_id"
            ],
            sport_id=sport_id,
            name=tournament_data["name"],
            slug=tournament_data["slug"],
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
    ) -> Fixture:
        existing = self.db.scalar(
            select(
                Fixture
            ).where(
                Fixture.stake_fixture_id
                == fixture_data[
                    "stake_fixture_id"
                ]
            )
        )

        if existing:
            return existing

        fixture = Fixture(
            stake_fixture_id=fixture_data[
                "stake_fixture_id"
            ],
            tournament_id=tournament_id,
            fixture_slug=fixture_data[
                "fixture_slug"
            ],
            name=fixture_data[
                "fixture_name"
            ],
            home_team=fixture_data[
                "home_team"
            ],
            away_team=fixture_data[
                "away_team"
            ],
            provider=fixture_data[
                "provider"
            ],
            status=fixture_data[
                "status"
            ],
            market_count=fixture_data[
                "market_count"
            ],
            start_time=fixture_data[
                "start_time"
            ],
        )

        self.db.add(
            fixture
        )

        self.db.flush()

        return fixture

    def _upsert_market_group(
        self,
        fixture_id: int,
        group_data: dict,
    ) -> MarketGroup:
        existing = self.db.scalar(
            select(
                MarketGroup
            ).where(
                MarketGroup.fixture_id
                == fixture_id,
                MarketGroup.name
                == group_data["name"],
            )
        )

        if existing:
            return existing

        group = MarketGroup(
            fixture_id=fixture_id,
            name=group_data["name"],
            translation=group_data.get(
                "translation"
            ),
            rank=group_data.get(
                "rank"
            ),
        )

        self.db.add(
            group
        )

        self.db.flush()

        return group

    def _upsert_market_template(
        self,
        group_id: int,
        template_data: dict,
    ) -> MarketTemplate:
        existing = self.db.scalar(
            select(
                MarketTemplate
            ).where(
                MarketTemplate.stake_template_ext_id
                == template_data[
                    "extId"
                ],
                MarketTemplate.group_id
                == group_id,
            )
        )

        if existing:
            return existing

        template = MarketTemplate(
            group_id=group_id,
            stake_template_ext_id=template_data[
                "extId"
            ],
            name=template_data[
                "name"
            ],
            rank=template_data.get(
                "rank"
            ),
        )

        self.db.add(
            template
        )

        self.db.flush()

        return template

    def _upsert_market(
        self,
        fixture_id: int,
        template_id: int,
        market_data: dict,
    ) -> Market:
        existing = self.db.scalar(
            select(
                Market
            ).where(
                Market.stake_market_id
                == market_data["id"]
            )
        )

        if existing:
            return existing

        market = Market(
            fixture_id=fixture_id,
            template_id=template_id,
            stake_market_id=market_data[
                "id"
            ],
            market_name=market_data[
                "name"
            ],
            provider=market_data.get(
                "provider"
            ),
            status=market_data[
                "status"
            ],
        )

        self.db.add(
            market
        )

        self.db.flush()

        return market

    def _upsert_outcome(
        self,
        market_id: int,
        outcome_data: dict,
    ) -> Outcome:
        existing = self.db.scalar(
            select(
                Outcome
            ).where(
                Outcome.stake_outcome_id
                == outcome_data["id"]
            )
        )

        if existing:
            existing.odds = outcome_data[
                "odds"
            ]
            existing.active = outcome_data[
                "active"
            ]
            existing.name = outcome_data[
                "name"
            ]

            return existing

        outcome = Outcome(
            market_id=market_id,
            stake_outcome_id=outcome_data[
                "id"
            ],
            name=outcome_data[
                "name"
            ],
            odds=outcome_data[
                "odds"
            ],
            active=outcome_data[
                "active"
            ],
        )

        self.db.add(
            outcome
        )

        self.db.flush()

        return outcome