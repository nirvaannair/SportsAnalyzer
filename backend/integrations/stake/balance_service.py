from __future__ import annotations

from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)

from backend.integrations.stake.models import (
    StakeBalance,
)

from backend.integrations.stake.queries import (
    BALANCE_QUERY,
)


class StakeBalanceService:
    def __init__(
        self,
        client: StakeGraphQLClient,
    ) -> None:
        self.client = client

    async def get_balance(
        self,
    ) -> StakeBalance:
        payload = (
            await self.client.execute(
                query=BALANCE_QUERY,
                operation_name="UserBalances",
            )
        )

        balances = {
            "available": {},
            "vault": {},
        }

        user = payload.get(
            "user",
            {},
        )

        for balance in user.get(
            "balances",
            [],
        ):
            available = balance.get(
                "available"
            )

            vault = balance.get(
                "vault"
            )

            if available:
                balances[
                    "available"
                ][
                    available[
                        "currency"
                    ].lower()
                ] = float(
                    available[
                        "amount"
                    ]
                )

            if vault:
                balances[
                    "vault"
                ][
                    vault[
                        "currency"
                    ].lower()
                ] = float(
                    vault[
                        "amount"
                    ]
                )

        return StakeBalance(
            **balances
        )