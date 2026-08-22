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

from backend.services.training_dataset_generator_service import (
    TrainingDatasetGeneratorService,
)


def main() -> None:
    db = SessionLocal()

    try:
        service = (
            TrainingDatasetGeneratorService(
                db
            )
        )

        inserted = (
            service.generate()
        )

        print(
            "\nTRAINING DATASET RESULTS\n"
        )

        print(
            f"Inserted Examples: {inserted}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()