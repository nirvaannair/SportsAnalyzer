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

from backend.services.historical_team_snapshot_generation_service import (
    HistoricalTeamSnapshotGenerationService,
)


def main() -> None:

    db = SessionLocal()

    try:

        service = (
            HistoricalTeamSnapshotGenerationService(
                db,
            )
        )

        fixtures = (
            db.query(
                APIFootballFixture
            )
            .order_by(
                APIFootballFixture.fixture_date.asc()
            )
            .all()
        )

        total = len(
            fixtures
        )

        for index, fixture in enumerate(
            fixtures,
            start=1,
        ):

            service.generate_for_fixture(
                fixture.id
            )

            if index % 100 == 0:

                print(
                    f"{index}/{total}"
                )

        print(
            "\nSnapshot generation complete."
        )

    finally:

        db.close()


if __name__ == "__main__":

    main()