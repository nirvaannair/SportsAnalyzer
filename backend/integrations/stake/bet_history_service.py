from __future__ import annotations

from typing import Any

from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)

from backend.integrations.stake.queries import (
    BET_HISTORY_QUERY,
)


class StakeBetHistoryService:
    def __init__(
        self,
        client: StakeGraphQLClient,
    ) -> None:
        self.client = client

    async def get_bet_history(
        self,
        limit: int = 100,
        offset: int = 0,
        username: str | None = None,
    ) -> list[dict[str, Any]]:
        response = await self.client.execute(
            query=BET_HISTORY_QUERY,
            variables={
                "limit": limit,
                "offset": offset,
                "name": username,
                "status": [
                    "settled",
                    "settledManual",
                    "settledPending",
                    "cancelPending",
                    "cancelled",
                    "cashout",
                    "cashoutPending",
                ],
            }
        )

        bets = (
            response
            .get("data", {})
            .get("user", {})
            .get("sportBetList", [])
        )

        normalized: list[
            dict[str, Any]
        ] = []

        for item in bets:
            bet = item.get(
                "bet",
                {}
            )

            if not bet:
                continue

            normalized.append(
                self._normalize_bet(
                    item
                )
            )

        return normalized

    def _normalize_bet(
        self,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        bet = item.get(
            "bet",
            {}
        )

        outcomes = []

        for leg in bet.get(
            "outcomes",
            [],
        ):
            outcome = leg.get(
                "outcome",
                {}
            )

            market = leg.get(
                "market",
                {}
            )

            fixture = leg.get(
                "fixture",
                {}
            )

            outcomes.append(
                {
                    "bet_outcome_id": leg.get(
                        "id"
                    ),
                    "leg_status": leg.get(
                        "status"
                    ),
                    "odds": leg.get(
                        "odds"
                    ),
                    "total_odds": leg.get(
                        "totalOdds"
                    ),
                    "outcome": {
                        "id": outcome.get(
                            "id"
                        ),
                        "name": outcome.get(
                            "name"
                        ),
                        "odds": outcome.get(
                            "odds"
                        ),
                    },
                    "market": {
                        "id": market.get(
                            "id"
                        ),
                        "name": market.get(
                            "name"
                        ),
                        "status": market.get(
                            "status"
                        ),
                    },
                    "fixture": fixture,
                }
            )

        return {
            "bet_id": bet.get(
                "id"
            ),
            "bet_slip_id": item.get(
                "id"
            ),
            "bet_iid": item.get(
                "iid"
            ),
            "amount": bet.get(
                "amount"
            ),
            "currency": bet.get(
                "currency"
            ),
            "status": bet.get(
                "status"
            ),
            "payout": bet.get(
                "payout"
            ),
            "payout_multiplier": bet.get(
                "payoutMultiplier"
            ),
            "potential_multiplier": bet.get(
                "potentialMultiplier"
            ),
            "created_at": bet.get(
                "createdAt"
            ),
            "updated_at": bet.get(
                "updatedAt"
            ),
            "outcomes": outcomes,
        }