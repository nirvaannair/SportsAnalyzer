from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from dotenv import load_dotenv


load_dotenv()


class StakeGraphQLClient:
    def __init__(
        self,
    ) -> None:
        self.base_url = (
            "https://stake.com/_api/graphql"
        )

        self.access_token = os.getenv(
            "STAKE_ACCESS_TOKEN"
        )

        self.cf_clearance = os.getenv(
            "STAKE_CF_CLEARANCE"
        )

        self.user_agent = os.getenv(
            "STAKE_USER_AGENT"
        )

        if not self.access_token:
            raise ValueError(
                "STAKE_ACCESS_TOKEN missing"
            )

        if not self.cf_clearance:
            raise ValueError(
                "STAKE_CF_CLEARANCE missing"
            )

        if not self.user_agent:
            raise ValueError(
                "STAKE_USER_AGENT missing"
            )

    def _headers(
        self,
    ) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://stake.com",
            "Referer": "https://stake.com/",
            "X-Access-Token": self.access_token,
            "X-Language": "en",
        }

    def _cookies(
        self,
    ) -> dict[str, str]:
        return {
            "cf_clearance": self.cf_clearance,
        }

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "query": query,
            "variables": variables or {},
        }

        async with httpx.AsyncClient(
            timeout=60.0,
        ) as client:
            response = await client.post(
                self.base_url,
                json=payload,
                headers=self._headers(),
                cookies=self._cookies(),
            )

        if response.status_code == 401:
            raise RuntimeError(
                "Stake authentication failed"
            )

        if response.status_code == 403:
            raise RuntimeError(
                "Stake Cloudflare blocked request"
            )

        if response.status_code == 429:
            raise RuntimeError(
                "Stake rate limit reached"
            )


        response.raise_for_status()

        data = response.json()

        if "errors" in data:
            raise RuntimeError(
                str(data["errors"])
            )

        return data


async def _test() -> None:
    client = StakeGraphQLClient()

    query = """
    query UserBalances {
      user {
        id
      }
    }
    """

    result = await client.execute(
        query=query,
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(
        _test()
    )