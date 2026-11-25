"""Read-only Stake client (Phase 6 foundation).

Talks to Stake's own GraphQL endpoint (what the stake.com website uses) with the access
token and browser user agent from .env. This module only READS (balance, and later bet
history and markets). Placing bets lives elsewhere, behind the strategy's execution mode
(paper -> approve -> auto), per-bet caps and the user's own switch on the dashboard.

The token is never logged or returned by any function here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

BALANCES_QUERY = """
query UserBalances {
  user {
    id
    balances {
      available { amount currency }
      vault { amount currency }
    }
  }
}
"""


class StakeError(RuntimeError):
    pass


@dataclass(frozen=True)
class StakeConfig:
    access_token: str
    user_agent: str
    base_url: str = "https://stake.com"
    currency: str = "inr"

    @classmethod
    def from_env(cls) -> StakeConfig:
        token = os.getenv("STAKE_ACCESS_TOKEN", "").strip()
        agent = os.getenv("STAKE_USER_AGENT", "").strip()
        if not token or not agent:
            raise StakeError("STAKE_ACCESS_TOKEN and STAKE_USER_AGENT must be set in .env")
        return cls(token, agent, os.getenv("STAKE_BASE_URL", "https://stake.com").rstrip("/"),
                   os.getenv("STAKE_CURRENCY", "inr").strip().lower() or "inr")


class StakeReadClient:
    def __init__(self, config: StakeConfig) -> None:
        self.config = config
        self._http = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=20,
            headers={
                "x-access-token": config.access_token,
                "user-agent": config.user_agent,
                "content-type": "application/json",
                "accept": "application/json",
                "origin": config.base_url,
                "referer": f"{config.base_url}/",
            },
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _graphql(self, query: str, operation: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._http.post("/_api/graphql", json={
            "query": query, "operationName": operation, "variables": variables or {},
        })
        if response.status_code == 403 and "cloudflare" in response.text.lower():
            raise StakeError("Blocked by Cloudflare (403). The user agent or network may need adjusting.")
        if response.status_code >= 400:
            raise StakeError(f"Stake returned HTTP {response.status_code}")
        body = response.json()
        if body.get("errors"):
            messages = "; ".join(str(e.get("message")) for e in body["errors"])
            raise StakeError(f"Stake GraphQL error: {messages}")
        return body.get("data") or {}

    async def balances(self) -> dict[str, dict[str, float]]:
        """{"available": {"inr": 500.0, ...}, "vault": {...}}"""
        data = await self._graphql(BALANCES_QUERY, "UserBalances")
        out: dict[str, dict[str, float]] = {"available": {}, "vault": {}}
        for entry in ((data.get("user") or {}).get("balances") or []):
            for kind in ("available", "vault"):
                item = entry.get(kind) or {}
                if item.get("currency"):
                    out[kind][item["currency"].lower()] = float(item.get("amount") or 0)
        return out
