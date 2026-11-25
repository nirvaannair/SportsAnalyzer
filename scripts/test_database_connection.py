from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.engine import engine


async def main() -> None:
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT current_user, current_database()")
            )

            row = result.one()

            print(f"Database user: {row[0]}")
            print(f"Database name: {row[1]}")
            print("Database connection: SUCCESS")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())