from __future__ import annotations

import asyncio
import subprocess


async def main() -> None:
    while True:
        print(
            "\nStarting fixture sync..."
        )

        subprocess.run(
            [
                "python",
                "scripts/sync_stake_fixtures.py",
            ]
        )

        subprocess.run(
            [
                "python",
                "scripts/sync_stake_main_markets.py",
            ]
        )

        print(
            "\nSleeping 15 minutes..."
        )

        await asyncio.sleep(
            15 * 60
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )