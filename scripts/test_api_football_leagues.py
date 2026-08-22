import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_FOOTBALL_API_KEY")

BASE_URL = "https://v3.football.api-sports.io"


async def api_get(endpoint: str, params: dict):
    headers = {
        "x-apisports-key": API_KEY,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{BASE_URL}{endpoint}",
            headers=headers,
            params=params,
        )

        response.raise_for_status()

        return response.json()


async def test_leagues():
    print("\n" + "=" * 80)
    print("TESTING LEAGUES")
    print("=" * 80)

    data = await api_get("/leagues", {})

    leagues = data.get("response", [])

    print(f"\nTOTAL LEAGUES: {len(leagues)}\n")

    for league in leagues[:50]:
        league_info = league.get("league", {})
        country_info = league.get("country", {})

        print(
            f"{league_info.get('id')} | "
            f"{league_info.get('name')} | "
            f"{country_info.get('name')}"
        )


async def test_fixtures():
    print("\n" + "=" * 80)
    print("TESTING PREMIER LEAGUE FIXTURES")
    print("=" * 80)

    data = await api_get(
        "/fixtures",
        {
            "league": 39,
            "season": 2024,
        },
    )

    fixtures = data.get("response", [])

    print(f"\nFIXTURES FOUND: {len(fixtures)}")

    if fixtures:
        fixture = fixtures[0]

        home_team = (
            fixture.get("teams", {})
            .get("home", {})
            .get("name")
        )

        away_team = (
            fixture.get("teams", {})
            .get("away", {})
            .get("name")
        )

        print(
            f"Sample Fixture: "
            f"{home_team} vs {away_team}"
        )


async def test_standings():
    print("\n" + "=" * 80)
    print("TESTING PREMIER LEAGUE STANDINGS")
    print("=" * 80)

    data = await api_get(
        "/standings",
        {
            "league": 39,
            "season": 2024,
        },
    )

    response = data.get("response", [])

    if not response:
        print("No standings returned")
        return

    standings = (
        response[0]
        .get("league", {})
        .get("standings", [[]])[0]
    )

    print(f"\nTEAMS IN TABLE: {len(standings)}\n")

    for team in standings[:10]:
        print(
            f"{team.get('rank')} | "
            f"{team.get('team', {}).get('name')} | "
            f"{team.get('points')} pts"
        )


async def test_team_statistics():
    print("\n" + "=" * 80)
    print("TESTING TEAM STATISTICS")
    print("=" * 80)

    data = await api_get(
        "/teams/statistics",
        {
            "league": 39,
            "season": 2024,
            "team": 50,
        },
    )

    response = data.get("response", {})

    team_name = response.get("team", {}).get("name")

    fixtures_played = (
        response.get("fixtures", {})
        .get("played", {})
        .get("total")
    )

    goals_for = (
        response.get("goals", {})
        .get("for", {})
        .get("total", {})
        .get("total")
    )

    goals_against = (
        response.get("goals", {})
        .get("against", {})
        .get("total", {})
        .get("total")
    )

    print(f"\nTeam: {team_name}")
    print(f"Matches Played: {fixtures_played}")
    print(f"Goals For: {goals_for}")
    print(f"Goals Against: {goals_against}")


async def test_historical_seasons():
    print("\n" + "=" * 80)
    print("TESTING HISTORICAL DATA AVAILABILITY")
    print("=" * 80)

    seasons = [
        2022,
        2023,
        2024,
        2024,
    ]

    for season in seasons:
        try:
            data = await api_get(
                "/fixtures",
                {
                    "league": 39,
                    "season": season,
                },
            )

            fixtures = data.get("response", [])

            print(
                f"Season {season}: "
                f"{len(fixtures)} fixtures"
            )

        except Exception as exc:
            print(
                f"Season {season}: FAILED -> {exc}"
            )


async def main():
    if not API_KEY:
        raise ValueError(
            "API_FOOTBALL_API_KEY not found in environment variables."
        )

    print("\nAPI-FOOTBALL CONNECTIVITY TEST\n")

    await test_leagues()
    await test_fixtures()
    await test_standings()
    await test_team_statistics()
    await test_historical_seasons()

    print("\n")
    print("=" * 80)
    print("ALL TESTS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())