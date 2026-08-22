from __future__ import annotations

from typing import Any
import json

from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)

from backend.integrations.stake.queries import (
    FIXTURE_DETAILS_QUERY,
)


class StakeFixtureMarketService:
    def __init__(
        self,
        client: StakeGraphQLClient,
    ) -> None:
        self.client = client

    async def get_fixture_main_markets(
        self,
        fixture_slug: str,
    ) -> dict[str, Any]:
        response = await self.client.execute(
            query=FIXTURE_DETAILS_QUERY,
            variables={
                "fixture": fixture_slug,
                "groups": [
                    "main",
                ],
            },
        )

        print(
            json.dumps(
                response,
                indent=2,
            )
        )

        fixture = (
            response
            .get("data", {})
            .get("slugFixture")
        )

        if not fixture:
            return {}

        print(
            json.dumps(
                fixture,
                indent=2,
            )
        )

        return fixture