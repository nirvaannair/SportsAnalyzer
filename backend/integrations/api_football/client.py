from __future__ import annotations

import os
from typing import Any

import httpx

from dotenv import load_dotenv


load_dotenv()


class APIFootballClient:
    def __init__(
        self,
    ) -> None:

        self.base_url = (
            os.getenv(
                "API_FOOTBALL_BASE_URL"
            )
            or
            "https://v3.football.api-sports.io"
        )

        self.api_key = os.getenv(
            "API_FOOTBALL_API_KEY"
        )

        if not self.api_key:
            raise ValueError(
                "API_FOOTBALL_API_KEY missing"
            )

    def _headers(
        self,
    ) -> dict[str, str]:
        return {
            "x-apisports-key":
            self.api_key,
        }

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        url = (
            f"{self.base_url}"
            f"{endpoint}"
        )

        async with httpx.AsyncClient(
            timeout=60.0,
        ) as client:

            response = await client.get(
                url,
                headers=self._headers(),
                params=params or {},
            )

        response.raise_for_status()

        return response.json()