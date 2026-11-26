"""Free-plan collector: stays within plan limits, never asks for odds, reads provider errors correctly."""

import pytest

from backend.collector.engine import classify, finished_fixture_ids
from backend.collector.providers import PROVIDERS, check_endpoint


@pytest.mark.parametrize("name", list(PROVIDERS))
def test_budgets_and_pacing_stay_inside_free_plans(name) -> None:
    p = PROVIDERS[name]
    if p.plan_daily_limit is not None:
        assert p.default_daily_budget < p.plan_daily_limit  # headroom for manual use
    assert p.min_interval_s >= 3.0
    if name in ("api_football", "football_data_org"):  # both allow 10 requests per minute
        assert 60 / p.min_interval_s < 10


@pytest.mark.parametrize("name", list(PROVIDERS))
def test_planned_tasks_never_request_odds(name) -> None:
    tasks = PROVIDERS[name].planner()
    assert tasks
    for t in tasks:
        check_endpoint(t.endpoint)
        assert "odds" not in str(t.params).lower()


def test_odds_endpoints_are_refused() -> None:
    for endpoint in ("odds", "odds/live", "v4/bookmakers", "bets"):
        with pytest.raises(ValueError):
            check_endpoint(endpoint)


def test_api_football_only_asks_for_free_plan_seasons() -> None:
    seasons = {t.params["season"] for t in PROVIDERS["api_football"].planner()}
    assert seasons <= {2022, 2023, 2024}


@pytest.mark.parametrize(("provider", "status", "payload", "expected"), [
    ("api_football", 200, {"errors": {"requests": "You have reached the request limit for the day"}}, "quota"),
    ("api_football", 200, {"errors": {"plan": "Free plans do not have access to this season"}}, "unavailable"),
    ("api_football", 200, {"errors": {"token": "Error/Missing application key"}}, "auth"),
    ("api_football", 200, {"errors": [], "response": []}, "ok"),
    ("football_data_org", 403, {"message": "restricted"}, "unavailable"),
    ("football_data_org", 429, {}, "retry"),
    ("openligadb", 200, [], "ok"),
    ("openligadb", 503, None, "retry"),
])
def test_classify(provider, status, payload, expected) -> None:
    assert classify(provider, status, payload)[0] == expected


def test_finished_fixture_ids() -> None:
    payload = {"parameters": {"season": "2023"}, "response": [
        {"fixture": {"id": 1, "status": {"short": "FT"}}},
        {"fixture": {"id": 2, "status": {"short": "NS"}}},
        {"fixture": {"id": 3, "status": {"short": "PEN"}}},
    ]}
    assert finished_fixture_ids(payload) == [("1", 2023), ("3", 2023)]
