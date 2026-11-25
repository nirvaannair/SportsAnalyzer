from datetime import UTC, datetime

from backend.execution.stake_parse import league_code, parse_payload, parse_start


def _market(ext, name, outcomes, specifiers=""):
    return {"id": f"m-{ext}-{specifiers}", "name": name, "extId": ext, "status": "active", "specifiers": specifiers,
            "outcomes": [{"id": f"{ext}-{specifiers}-{i}", "name": n, "odds": p, "active": True}
                         for i, (n, p) in enumerate(outcomes)]}


FIXTURE = {"slugFixture": {
    "__typename": "SportFixture", "id": "fx1", "name": "Everton - Liverpool", "slug": "x", "extId": "sr:match:1",
    "data": {"startTime": "Sun, 29 Nov 2026 12:00:00 GMT",
             "teams": [{"name": "Everton", "qualifier": "home"}, {"name": "Liverpool", "qualifier": "away"}]},
    "tournament": {"__typename": "SportTournament", "name": "Premier League",
                   "category": {"__typename": "SportCategory", "name": "England",
                                "sport": {"__typename": "Sport", "slug": "soccer"}}},
    "groups": [{"templates": [{"markets": [
        _market("1", "1x2", [("Everton", 3.9), ("Draw", 3.6), ("Liverpool", 1.9)]),
        _market("18", "Total", [("Over 2.5", 1.8), ("Under 2.5", 2.0)], "total=2.5"),
        _market("29", "Both Teams to Score", [("Yes", 1.7), ("No", 2.1)]),
        _market("45", "Correct Score", [("1:0", 9.0)]),
    ]}]}],
}}


def test_league_mapping_and_dates() -> None:
    assert league_code("England", "Premier League") == "ENG1"
    assert league_code("Spain", "LaLiga 2") == "ESP2"
    assert league_code("International Clubs", "UEFA Champions League") is None
    assert parse_start("Sun, 29 Nov 2026 12:00:00 GMT") == datetime(2026, 11, 29, 12, tzinfo=UTC)
    assert parse_start("2026-11-29T12:00:00Z") == datetime(2026, 11, 29, 12, tzinfo=UTC)
    assert parse_start(None) is None


def test_parse_fixture_and_selections() -> None:
    (fixture,), outcomes = parse_payload(FIXTURE)
    assert fixture["league_code"] == "ENG1" and fixture["home_name"] == "Everton"
    assert fixture["start_time"] == datetime(2026, 11, 29, 12, tzinfo=UTC)
    selections = {(o["market_code"], o["name"]): o["selection"] for o in outcomes}
    assert selections[("1", "Everton")] == "home"
    assert selections[("1", "Draw")] == "draw"
    assert selections[("1", "Liverpool")] == "away"
    assert selections[("18", "Over 2.5")] == "over" and selections[("18", "Under 2.5")] == "under"
    assert selections[("29", "Yes")] == "yes"
    assert selections[("45", "1:0")] is None  # kept, but not a market we model
    over = next(o for o in outcomes if o["name"] == "Over 2.5")
    assert over["specifiers"] == "total=2.5" and over["price"] == 1.8 and over["stake_fixture_id"] == "fx1"


def test_untracked_sport_gets_no_league() -> None:
    other = {"x": {**FIXTURE["slugFixture"], "id": "fx2", "tournament": {
        "__typename": "SportTournament", "name": "Premier League",
        "category": {"__typename": "SportCategory", "name": "England", "sport": {"__typename": "Sport", "slug": "darts"}}}}}
    (fixture,), _ = parse_payload(other)
    assert fixture["league_code"] is None
