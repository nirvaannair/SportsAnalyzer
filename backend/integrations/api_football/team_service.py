from __future__ import annotations

from backend.integrations.api_football.client import (
    APIFootballClient,
)


class APIFootballTeamService:
    def __init__(
        self,
        client: APIFootballClient,
    ) -> None:
        self.client = client

    async def get_team_statistics(
        self,
        league_id: int,
        season: int,
        team_id: int,
    ) -> dict:

        response = (
            await self.client.get(
                "/teams/statistics",
                {
                    "league":
                    league_id,

                    "season":
                    season,

                    "team":
                    team_id,
                },
            )
        )

        return response

    async def get_teams(
        self,
        league_id: int,
        season: int,
    ) -> list[dict]:

        response = (
            await self.client.get(
                "/teams",
                {
                    "league":
                    league_id,

                    "season":
                    season,
                },
            )
        )

        return (
            response.get(
                "response",
                [],
            )
        )