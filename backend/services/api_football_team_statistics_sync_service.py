from __future__ import annotations

import json
import asyncio
import httpx

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models.api_football_team_statistic import (
    APIFootballTeamStatistic,
)

from backend.database.models.team_mapping import (
    TeamMapping,
)

from backend.integrations.api_football.client import (
    APIFootballClient,
)


class APIFootballTeamStatisticsSyncService:
    def __init__(
        self,
        db: Session,
        client: APIFootballClient,
    ) -> None:
        self.db = db
        self.client = client

    async def sync_team_statistics(
        self,
        league_id: int,
        season: int,
        api_football_team_id: int,
    ) -> bool:

        existing = (
            self.db.query(
                APIFootballTeamStatistic
            )
            .filter(
                APIFootballTeamStatistic.api_football_team_id
                == api_football_team_id,
                APIFootballTeamStatistic.league_id
                == league_id,
                APIFootballTeamStatistic.season
                == season,
            )
            .first()
        )

        if existing:

            print(
                f"[SKIP] League={league_id} "
                f"Season={season} "
                f"Team={api_football_team_id} "
                f"(already exists)"
            )

            return False

        mapping = (
            self.db.query(
                TeamMapping
            )
            .filter(
                TeamMapping.provider
                == "api_football",
                TeamMapping.provider_team_id
                == str(
                    api_football_team_id
                ),
            )
            .first()
        )

        if not mapping:

            print(
                f"[NO MAPPING] "
                f"League={league_id} "
                f"Season={season} "
                f"Team={api_football_team_id}"
            )

            return False

        for attempt in range(3):

            try:

                print(
                    f"[FETCH] League={league_id} "
                    f"Season={season} "
                    f"Team={api_football_team_id}"
                )

                response = await self.client.get(
                    "/teams/statistics",
                    {
                        "league": league_id,
                        "season": season,
                        "team": api_football_team_id,
                    },
                )

                break
            
            except httpx.HTTPStatusError as exc:

                if exc.response.status_code == 429:

                    try:
                        body = exc.response.json()
                    except Exception:
                        body = {}

                    print(f"429 response: {body}")

                    errors = body.get("errors", {})

                    if "rateLimit" in errors:

                        print(
                            "Per-minute rate limit reached. "
                            "Waiting 60 seconds before retrying..."
                        )

                        await asyncio.sleep(60)

                        continue

                    raise RuntimeError(
                        "API_FOOTBALL_DAILY_LIMIT_REACHED"
                    )

                raise

        else:

            return False

        response_data = response.get(
            "response",
            []
        )

        if not response_data:

            print(
                f"[EMPTY RESPONSE] "
                f"League={league_id} "
                f"Season={season} "
                f"Team={api_football_team_id}"
            )

            return False

        data = response_data

        print(
            f"Team {api_football_team_id}: {type(data)}"
        )

        fixtures = data.get(
            "fixtures",
            {}
        )

        goals = data.get(
            "goals",
            {}
        )

        goals_for = (
            goals.get(
                "for",
                {}
            )
            .get(
                "total",
                {}
            )
        )

        goals_against = (
            goals.get(
                "against",
                {}
            )
            .get(
                "total",
                {}
            )
        )

        played = (
            fixtures.get(
                "played",
                {}
            )
        )

        wins = (
            fixtures.get(
                "wins",
                {}
            )
        )

        draws = (
            fixtures.get(
                "draws",
                {}
            )
        )

        losses = (
            fixtures.get(
                "loses",
                {}
            )
        )

        clean_sheet = (
            data.get(
                "clean_sheet",
                {}
            )
        )

        failed_to_score = (
            data.get(
                "failed_to_score",
                {}
            )
        )

        total_goals_for = (
            goals_for.get(
                "total"
            )
        )

        total_goals_against = (
            goals_against.get(
                "total"
            )
        )

        goal_difference = None

        if (
            total_goals_for
            is not None
            and total_goals_against
            is not None
        ):
            goal_difference = (
                total_goals_for
                - total_goals_against
            )

        self.db.add(
            APIFootballTeamStatistic(
                team_id=mapping.team_id,
                api_football_team_id=api_football_team_id,
                league_id=league_id,
                season=season,
                played=played.get(
                    "total"
                ),
                wins=wins.get(
                    "total"
                ),
                draws=draws.get(
                    "total"
                ),
                losses=losses.get(
                    "total"
                ),
                goals_for=total_goals_for,
                goals_against=total_goals_against,
                home_played=played.get(
                    "home"
                ),
                home_wins=wins.get(
                    "home"
                ),
                home_draws=draws.get(
                    "home"
                ),
                home_losses=losses.get(
                    "home"
                ),
                away_played=played.get(
                    "away"
                ),
                away_wins=wins.get(
                    "away"
                ),
                away_draws=draws.get(
                    "away"
                ),
                away_losses=losses.get(
                    "away"
                ),
                form=data.get(
                    "form"
                ),
                goal_difference=goal_difference,
                clean_sheets=clean_sheet.get(
                    "total"
                ),
                failed_to_score=(
                    failed_to_score.get(
                        "total"
                    )
                ),
                home_goals_for=(
                    goals_for.get(
                        "home"
                    )
                ),
                home_goals_against=(
                    goals_against.get(
                        "home"
                    )
                ),
                away_goals_for=(
                    goals_for.get(
                        "away"
                    )
                ),
                away_goals_against=(
                    goals_against.get(
                        "away"
                    )
                ),
                raw_json=json.dumps(
                    data
                ),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        self.db.commit()

        print(
            f"[INSERT] League={league_id} "
            f"Season={season} "
            f"Team={api_football_team_id}"
        )

        return True