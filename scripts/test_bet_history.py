from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)

from backend.database.session import (
    SessionLocal,
)

from backend.database.models.__all_models import *

from backend.database.models.bet_leg import (
    BetLeg,
)

from backend.database.models.fixture import (
    Fixture,
)


def main() -> None:
    db = SessionLocal()

    try:
        total_legs = (
            db.query(BetLeg)
            .count()
        )

        linked_legs = (
            db.query(BetLeg)
            .join(
                Fixture,
                BetLeg.fixture_id
                == Fixture.stake_fixture_id,
            )
            .count()
        )

        unlinked_legs = (
            total_legs
            - linked_legs
        )

        coverage = (
            (
                linked_legs
                / total_legs
            )
            * 100
            if total_legs
            else 0
        )

        print(
            "\n========== LINKAGE AUDIT ==========\n"
        )

        print(
            f"Total Bet Legs      : {total_legs}"
        )

        print(
            f"Linked Bet Legs     : {linked_legs}"
        )

        print(
            f"Unlinked Bet Legs   : {unlinked_legs}"
        )

        print(
            f"Coverage            : {coverage:.2f}%"
        )

        print(
            "\n===== SAMPLE UNLINKED LEGS =====\n"
        )

        unlinked = (
            db.query(BetLeg)
            .outerjoin(
                Fixture,
                BetLeg.fixture_id
                == Fixture.stake_fixture_id,
            )
            .filter(
                Fixture.id.is_(None)
            )
            .limit(20)
            .all()
        )

        for leg in unlinked:
            print(
                {
                    "bet_leg_id": leg.id,
                    "fixture_id": leg.fixture_id,
                    "fixture_name": leg.fixture_name,
                    "market_name": leg.market_name,
                    "outcome_name": leg.outcome_name,
                }
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()