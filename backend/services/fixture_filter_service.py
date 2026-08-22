from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone


def is_prediction_candidate(
    fixture_status: str,
    start_time: datetime,
) -> bool:
    if fixture_status.lower() != "not_started":
        return False

    now = datetime.now(
        timezone.utc
    )

    remaining = (
        start_time - now
    )

    return remaining >= timedelta(
        hours=1
    )