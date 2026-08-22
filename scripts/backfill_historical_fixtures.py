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

from backend.services.historical_fixture_backfill_service import (
    HistoricalFixtureBackfillService,
)


def main() -> None:
    db = SessionLocal()

    try:
        service = (
            HistoricalFixtureBackfillService(
                db
            )
        )

        results = (
            service.backfill()
        )

        print(
            "\nBACKFILL RESULTS\n"
        )

        print(
            results
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()