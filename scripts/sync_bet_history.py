from __future__ import annotations

import asyncio
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

from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)

from backend.integrations.stake.bet_history_service import (
    StakeBetHistoryService,
)

from backend.services.stake_bet_history_sync_service import (
    StakeBetHistorySyncService,
)


async def main() -> None:
    client = StakeGraphQLClient()

    history_service = (
        StakeBetHistoryService(
            client
        )
    )

    sync_service = (
        StakeBetHistorySyncService(
            history_service
        )
    )

    imported = (
        await sync_service.sync_all_history()
    )

    print(
        f"\nImported {imported} bets\n"
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )