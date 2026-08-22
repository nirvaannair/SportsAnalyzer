from __future__ import annotations

from backend.integrations.stake.graphql_client import (
    StakeGraphQLClient,
)


SPORT_OUTCOME_QUERY = """
query SportBet_SportMarketOutcome(
  $outcomeId: String!,
  $provider: SportsbookOddsProviderEnum!
) {
  sportMarketOutcome(
    outcomeId: $outcomeId,
    provider: $provider
  ) {
    id
    name
    odds

    market {
      id
      extId
      name
      status
      provider
      specifiers

      fixture {
        id
        slug
        status

        data {
          __typename

          ... on SportFixtureDataMatch {
            startTime

            competitors {
              name
            }
          }
        }
      }
    }
  }
}
"""


class StakeBetPlacementService:
    def __init__(
        self,
        client: StakeGraphQLClient,
    ) -> None:
        self.client = client

    async def get_outcome_details(
        self,
        outcome_id: str,
        provider: str,
    ) -> dict:
        return await self.client.execute(
            query=SPORT_OUTCOME_QUERY,
            operation_name=(
                "SportBet_SportMarketOutcome"
            ),
            variables={
                "outcomeId": outcome_id,
                "provider": provider,
            },
        )   