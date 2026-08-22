from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from backend.database.models.bet_leg import (
    BetLeg,
)

from backend.database.models.fixture import (
    Fixture,
)

from backend.database.models.tournament import (
    Tournament,
)

from backend.database.models.sport import (
    Sport,
)

from backend.database.models.training_example import (
    TrainingExample,
)


class TrainingDatasetGeneratorService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db


    def _normalize_name(
        self,
        value: str,
    ) -> str:
        return (
            value.lower()
            .replace(",", " ")
            .replace("-", " ")
            .replace(".", " ")
            .replace("fc", "")
            .replace("cf", "")
            .replace("club", "")
            .strip()
        )


    def _market_type(
        self,
        market_name: str | None,
    ) -> str:
        name = (
            market_name or ""
        ).lower()

        if (
            "winner" in name
            or name == "1x2"
        ):
            return "winner"

        if (
            "total" in name
            or "over" in name
            or "under" in name
        ):
            return "total"

        if (
            "both teams"
            in name
        ):
            return "both_teams_score"

        if (
            "handicap"
            in name
            or "spread"
            in name
        ):
            return "handicap"

        if (
            "draw no bet"
            in name
        ):
            return "draw_no_bet"

        if (
            "double chance"
            in name
        ):
            return "double_chance"

        return "other"

    def generate(
        self,
    ) -> int:
        inserted = 0

        bet_legs = (
            self.db.query(
                BetLeg,
                Fixture,
                Tournament,
                Sport,
            )
            .join(
                Fixture,
                BetLeg.fixture_id
                == Fixture.stake_fixture_id,
            )
            .join(
                Tournament,
                Fixture.tournament_id
                == Tournament.id,
            )
            .join(
                Sport,
                Tournament.sport_id
                == Sport.id,
            )
            .all()
        )

        for (
            leg,
            fixture,
            tournament,
            sport,
        ) in bet_legs:

            if leg.leg_status not in (
                "won",
                "lost",
            ):
                continue

            existing = (
                self.db.query(
                    TrainingExample
                )
                .filter(
                    TrainingExample.bet_leg_id
                    == leg.id
                )
                .first()
            )

            if existing:
                continue

            odds = (
                float(leg.odds)
                if leg.odds
                else None
            )

            if not odds:
                continue

            implied_probability = (
                1 / odds
            )

            target = (
                1
                if leg.leg_status
                == "won"
                else 0
            )

            outcome_name = (
                leg.outcome_name or ""
            )

            home_team = (
                fixture.home_team or ""
            )

            away_team = (
                fixture.away_team or ""
            )

            outcome_lower = (
                self._normalize_name(
                    outcome_name
                )
            )

            home_lower = (
                self._normalize_name(
                    home_team
                )
            )

            away_lower = (
                self._normalize_name(
                    away_team
                )
            )

            is_home_selection = (
                1
                if home_lower
                and home_lower in outcome_lower
                else 0
            )

            is_away_selection = (
                1
                if away_lower
                and away_lower in outcome_lower
                else 0
            )
            
            selected_team = None
            selected_side = None

            if is_home_selection:
                selected_team = home_team
                selected_side = "home"

            elif is_away_selection:
                selected_team = away_team
                selected_side = "away"

            market_type = (
                self._market_type(
                    leg.market_name
                )
            )

            self.db.add(
                TrainingExample(
                    bet_leg_id=leg.id,
                    fixture_id=fixture.id,
                    sport_name=sport.name,
                    tournament_name=tournament.name,
                    fixture_name=fixture.name,
                    home_team=home_team,
                    away_team=away_team,
                    market_name=leg.market_name,
                    market_type=market_type,
                    outcome_name=outcome_name,
                    odds=odds,
                    implied_probability=implied_probability,
                    is_home_selection=is_home_selection,
                    is_away_selection=is_away_selection,
                    selected_team=selected_team,
                    selected_side=selected_side,
                    target=target,
                    created_at=datetime.utcnow(),
                )
            )

            inserted += 1

        self.db.commit()

        return inserted