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

from backend.database.models.api_football_fixture import (
    APIFootballFixture,
)

from backend.services.football_feature_generation_service import (
    FootballFeatureGenerationService,
)


def main() -> None:

    db = SessionLocal()

    try:

        service = (
            FootballFeatureGenerationService(
                db,
            )
        )

        fixtures = (
            db.query(
                APIFootballFixture
            )
            .all()
        )

        inserted = 0

        for fixture in fixtures:

            was_created = (
                service.generate_for_fixture(
                    fixture.id
                )
            )

            if was_created:
                inserted += 1

        print(
            f"\nCreated {inserted} feature rows."
        )

    finally:

        db.close()


if __name__ == "__main__":

    main()