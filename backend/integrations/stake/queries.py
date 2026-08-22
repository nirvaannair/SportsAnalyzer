from __future__ import annotations


USER_BALANCE_QUERY = """
query UserBalances {
  user {
    id
    balances {
      available {
        amount
        currency
      }
      vault {
        amount
        currency
      }
    }
  }
}
"""


SOCCER_FIXTURE_LIST_QUERY = """
query SlugSportFixtureList(
    $type: SportSearchEnum!,
    $sport: String!,
    $groups: String!,
    $limit: Int!,
    $offset: Int!
) {
  slugSport(
    sport: $sport
  ) {
    id
    name

    fixtureList(
      type: $type,
      limit: $limit,
      offset: $offset
    ) {
      id
      slug
      name
      provider
      status
      extId

      marketCount(
        status: [
          active,
          suspended
        ]
      )

      tournament {
        id
        name
        slug

        category {
          id
          name
          slug

          sport {
            id
            name
            slug
          }
        }
      }

      data {
        __typename

        ... on SportFixtureDataMatch {
          startTime

          competitors {
            name
            defaultName
            extId
            abbreviation
          }

          teams {
            name
            qualifier
          }
        }
      }

      groups(
        groups: [$groups],
        status: [
          active,
          suspended,
          deactivated
        ]
      ) {
        name
        translation
        rank

        templates(
          limit: 50,
          includeEmpty: true
        ) {
          extId
          rank
          name

          markets(
            limit: 50
          ) {
            id
            name
            status
            extId
            provider
            templateExtId

            outcomes {
              id
              active
              odds
              name
            }
          }
        }
      }
    }
  }
}
"""


FIXTURE_DETAILS_QUERY = """
query FixturePage_SlugFixture(
    $fixture: String!,
    $groups: [String!]!
) {
  slugFixture(
    fixture: $fixture
  ) {
    id
    slug
    name
    status

    tournament {
      id
      name
      slug

      category {
        id
        name
        slug

        sport {
          id
          name
          slug
        }
      }
    }

    data {
      __typename

      ... on SportFixtureDataMatch {
        startTime

        competitors {
          name
          extId
          abbreviation
        }

        teams {
          name
          qualifier
        }
      }
    }

    group: groups(
      groups: $groups
    ) {
      name
      translation
      rank

      templates(
        includeEmpty: false
      ) {
        id
        extId
        name
        rank

        markets {
          id
          extId
          name
          provider
          status
          templateExtId

          outcomes {
            id
            active
            odds
            name
            extId
          }
        }
      }
    }
  }
}
"""


BET_HISTORY_QUERY = """
query SportSportList(
    $limit: Int!,
    $offset: Int!,
    $name: String,
    $status: [SportBetStatusEnum!]
) {
  user(
    name: $name
  ) {
    id
    name

    sportBetList(
      limit: $limit,
      offset: $offset,
      status: $status
    ) {
      id
      iid

      bet {
        ... on SportBet {
          id
          amount
          currency
          status

          payout
          payoutMultiplier
          potentialMultiplier

          createdAt
          updatedAt

          outcomes {
            id
            odds
            totalOdds
            status

            outcome {
              id
              name
              odds
            }

            market {
              id
              name
              status
            }
            
            fixture {
              id
              slug
              name
              status

              tournament {
                id
                name
                slug

                category {
                  id
                  name
                  slug

                  sport {
                    id
                    name
                    slug
                  }
                }
              }

              data {
                __typename

                ... on SportFixtureDataMatch {
                  startTime

                  competitors {
                    name
                    defaultName
                    extId
                    abbreviation
                  }

                  teams {
                    name
                    qualifier
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""