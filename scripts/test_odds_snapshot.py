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

import backend.database.models.__all_models

from backend.database.session import (
    SessionLocal,
)

from backend.services.odds_snapshot_service import (
    OddsSnapshotService,
)


def main() -> None:
    db = SessionLocal()

    try:
        service = OddsSnapshotService(
            db
        )

        count = (
            service.capture_all_current_odds()
        )

        print(
            f"Created {count} snapshots."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()