from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.fixture import Fixture
from backend.database.models.market_group import MarketGroup
from backend.database.models.market_template import MarketTemplate
from backend.database.models.market import Market
from backend.database.models.outcome import Outcome

from backend.integrations.stake.main_market_service import (
    StakeMainMarketService,
)


class StakeMainMarketSyncService:
    def __init__(
        self,
        db: Session,
        main_market_service: StakeMainMarketService,
    ) -> None:
        self.db = db
        self.main_market_service = (
            main_market_service
        )

    async def sync_fixture(
        self,
        fixture_slug: str,
    ) -> dict:
        fixture_data = (
            await self.main_market_service
            .get_fixture_main_markets(
                fixture_slug
            )
        )

        if not fixture_data:
            return {
                "groups": 0,
                "templates": 0,
                "markets": 0,
                "outcomes": 0,
            }

        fixture = self.db.scalar(
            select(
                Fixture
            ).where(
                Fixture.fixture_slug
                == fixture_slug
            )
        )

        if fixture is None:
            raise ValueError(
                f"Fixture not found: "
                f"{fixture_slug}"
            )

        counts = {
            "groups": 0,
            "templates": 0,
            "markets": 0,
            "outcomes": 0,
        }

        groups = (
            fixture_data.get(
                "group",
                []
            )
        )

        for group_data in groups:
            group = (
                self._upsert_market_group(
                    fixture.id,
                    group_data,
                )
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
                    market = (
                        self._upsert_market(
                            fixture.id,
                            template.id,
                            market_data,
                        )
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
            existing.translation = group_data.get(
                "translation"
            )

            existing.rank = group_data.get(
                "rank"
            )

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
                MarketTemplate.group_id
                == group_id,
                MarketTemplate.stake_template_ext_id
                == template_data["extId"],
            )
        )

        if existing:
            existing.name = template_data[
                "name"
            ]

            existing.rank = template_data.get(
                "rank"
            )

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
            existing.market_name = market_data[
                "name"
            ]

            existing.provider = market_data.get(
                "provider"
            )

            existing.status = market_data[
                "status"
            ]

            existing.template_id = template_id

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
            existing.name = outcome_data[
                "name"
            ]
            existing.odds = outcome_data[
                "odds"
            ]
            existing.active = outcome_data[
                "active"
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