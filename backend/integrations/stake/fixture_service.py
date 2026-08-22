from __future__ import annotations

from typing import Any

from backend.integrations.stake.graphql_client import StakeGraphQLClient
from backend.integrations.stake.queries import (
    SOCCER_FIXTURE_LIST_QUERY,
)


class StakeFixtureService:
    def __init__(
        self,
        client: StakeGraphQLClient,
    ) -> None:
        self.client = client

    async def get_upcoming_soccer_totals(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        variables = {
            "type": "upcoming",
            "sport": "soccer",
            "groups": "Total",
            "limit": limit,
            "offset": offset,
        }

        print("GRAPHQL VARIABLES:", variables)

        response = await self.client.execute(
            query=SOCCER_FIXTURE_LIST_QUERY,
            variables=variables,
        )

        fixtures = (
            response
            .get("data", {})
            .get("slugSport", {})
            .get("fixtureList", [])
        )

        normalized: list[dict[str, Any]] = []

        for fixture in fixtures:
            normalized.append(
                self._normalize_fixture(
                    fixture
                )
            )

        return normalized

    def _normalize_fixture(
        self,
        fixture: dict[str, Any],
    ) -> dict[str, Any]:
        data = fixture.get(
            "data",
            {},
        )

        competitors = data.get(
            "competitors",
            [],
        )

        home_team = None
        away_team = None

        if len(competitors) >= 2:
            home_team = competitors[0].get(
                "name"
            )
            away_team = competitors[1].get(
                "name"
            )

        tournament = fixture.get(
            "tournament",
            {},
        )

        groups = fixture.get(
            "groups",
            [],
        )

        return {
            "stake_fixture_id": fixture.get(
                "id"
            ),
            "stake_fixture_ext_id": fixture.get(
                "extId"
            ),
            "fixture_slug": fixture.get(
                "slug"
            ),
            "fixture_name": fixture.get(
                "name"
            ),
            "provider": fixture.get(
                "provider"
            ),
            "status": fixture.get(
                "status"
            ),
            "market_count": fixture.get(
                "marketCount"
            ),
            "start_time": data.get(
                "startTime"
            ),
            "home_team": home_team,
            "away_team": away_team,
            "tournament": {
                "stake_tournament_id": tournament.get(
                    "id"
                ),
                "name": tournament.get(
                    "name"
                ),
                "slug": tournament.get(
                    "slug"
                ),
                "category": tournament.get(
                    "category"
                ),
            },
            "groups": groups,
        }