from pathlib import Path
import asyncio
import json
import os

from dotenv import load_dotenv
from stakeapi import StakeAPI
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "stake"
)


def save_json(
    filename: str,
    payload,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_DIR / filename,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            indent=4,
            default=str,
            ensure_ascii=False,
        )


async def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    print("PROJECT_ROOT =", PROJECT_ROOT)

    env_file = PROJECT_ROOT / ".env"

    print("ENV FILE =", env_file)

    print("ENV EXISTS =", env_file.exists())

    from dotenv import dotenv_values

    print(
        "ENV KEYS =",
        list(
            dotenv_values(
                env_file
            ).keys()
        )
    )


    token = os.getenv(
        "STAKE_ACCESS_TOKEN"
    )

    if not token:
        raise ValueError(
            "STAKE_ACCESS_TOKEN missing"
        )

    async with StakeAPI(
        access_token=token,
        cf_clearance=os.getenv(
            "STAKE_CF_CLEARANCE"
        ),
        user_agent=os.getenv(
            "STAKE_USER_AGENT"
        ),
    ) as client:
        
        print(
            "CF Loaded:",
            bool(os.getenv("STAKE_CF_CLEARANCE"))
        )

        print(
            "UA Loaded:",
            bool(os.getenv("STAKE_USER_AGENT"))
        )


        print(
            "Fetching balance..."
        )

        try:
            balance = (
                await client.get_user_balance()
            )

            save_json(
                "balance.json",
                balance,
            )

            print(
                "Balance saved."
            )

        except Exception as error:
            print(
                f"Balance failed: {error}"
            )

        print(
            "Fetching football events..."
        )

        try:
            events = (
                await client.get_sports_events(
                    sport="football"
                )
            )

            save_json(
                "football_events.json",
                [
                    event.model_dump()
                    for event in events
                ],
            )

            print(
                f"Saved {len(events)} football events."
            )

        except Exception as error:
            print(
                f"Events failed: {error}"
            )

        print(
            "Fetching bet history..."
        )

        try:
            history = (
                await client.get_bet_history(
                    limit=100
                )
            )

            save_json(
                "bet_history.json",
                [
                    bet.model_dump()
                    for bet in history
                ],
            )

            print(
                f"Saved {len(history)} bets."
            )

        except Exception as error:
            print(
                f"History failed: {error}"
            )


if __name__ == "__main__":
    asyncio.run(main())