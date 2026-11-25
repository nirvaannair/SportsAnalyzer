import pytest

from backend.execution.guardrails import (
    Exposure,
    GuardrailError,
    Limits,
    check_dispatch,
    check_new_order,
)
from backend.execution.stake_requests import (
    TemplateError,
    bet_result,
    build_bet_request,
    extract_outcomes,
    is_bet_mutation,
)

LIMITS = Limits(max_bet=1.0, budget=20.0, max_bets_per_day=10, currency="inr")


def test_new_order_limits() -> None:
    check_new_order(1.0, "inr", LIMITS)
    for amount in (0, -1, 1.01, 500):
        with pytest.raises(GuardrailError):
            check_new_order(amount, "inr", LIMITS)
    with pytest.raises(GuardrailError):
        check_new_order(1.0, "btc", LIMITS)


def test_dispatch_limits() -> None:
    fresh = Exposure(spent_total=0, bets_today=0)
    check_dispatch(1.0, "inr", LIMITS, fresh, enabled=True)
    with pytest.raises(GuardrailError, match="switched off"):
        check_dispatch(1.0, "inr", LIMITS, fresh, enabled=False)
    with pytest.raises(GuardrailError, match="Budget"):
        check_dispatch(1.0, "inr", LIMITS, Exposure(spent_total=19.5, bets_today=0), enabled=True)
    with pytest.raises(GuardrailError, match="Daily"):
        check_dispatch(1.0, "inr", LIMITS, Exposure(spent_total=0, bets_today=10), enabled=True)


def test_limits_from_env(monkeypatch) -> None:
    monkeypatch.setenv("STAKE_MAX_BET", "2")
    monkeypatch.setenv("STAKE_TEST_BUDGET", "oops")
    limits = Limits.from_env()
    assert limits.max_bet == 2.0 and limits.budget == 20.0 and limits.currency == "inr"


SAMPLE = {
    "amount": 1, "currency": "inr", "outcomeIds": ["old-outcome"], "oddsChange": "none",
    "identifier": "abc123", "betType": "sports",
}


def test_build_bet_request_swaps_only_bet_fields() -> None:
    body = build_bet_request("SportBet", "mutation SportBet { x }", SAMPLE, "new-outcome", 1.0, "inr")
    v = body["variables"]
    assert v["outcomeIds"] == ["new-outcome"] and v["amount"] == 1.0 and v["currency"] == "inr"
    assert v["identifier"] != "abc123" and v["oddsChange"] == "none" and v["betType"] == "sports"
    assert SAMPLE["outcomeIds"] == ["old-outcome"]  # template not mutated


def test_build_refuses_unrecognised_template() -> None:
    with pytest.raises(TemplateError):
        build_bet_request("X", "mutation X { y }", {"foo": 1}, "o", 1.0, "inr")


def test_bet_mutation_detection() -> None:
    assert is_bet_mutation("SportBet", "mutation")
    assert not is_bet_mutation("SportBet", "query")
    assert not is_bet_mutation("UserBalances", "query")


def test_extract_outcomes_from_nested_response() -> None:
    data = {"sportFixture": {"name": "Arsenal - Chelsea", "groups": [{"markets": [
        {"name": "1x2", "outcomes": [
            {"id": "o1", "name": "Arsenal", "odds": 1.9, "active": True},
            {"id": "o2", "name": "draw", "odds": 3.6, "active": True},
        ]}]}]}}
    found = extract_outcomes(data)
    assert [(o["outcome_id"], o["market_name"], o["fixture_name"]) for o in found] == [
        ("o1", "1x2", "Arsenal - Chelsea"), ("o2", "1x2", "Arsenal - Chelsea")]


def test_bet_result_parsing() -> None:
    assert bet_result({"data": {"sportBet": {"id": "b1"}}}) == (True, "b1", "Placed")
    assert bet_result({"errors": [{"message": "insufficientBalance"}]})[0] is False
    assert bet_result({"data": {"sportBet": None}})[0] is False
