import pytest

from backend.execution.guardrails import Limits, needs_approval
from backend.execution.stake_requests import (
    TemplateError,
    build_bet_request,
    build_cashout_variables,
    parse_sport_bets,
    template_name,
)
from backend.strategies.core import Candidate, build_multi, eligible, multi_result


def _c(match, market, selection, p, price):
    return Candidate(match, market, selection, p, price, "stake", f"o{match}{selection}")


def test_approval_threshold() -> None:
    limits = Limits(max_bet=5000, budget=10000, max_bets_per_day=10, currency="inr", approval_above=1000)
    assert not needs_approval(1000, limits)
    assert needs_approval(1000.01, limits)


def test_confidence_band() -> None:
    kw = {"min_edge": 0.0, "min_price": 1.1, "max_price": 20, "markets": ["1x2"], "real_money": False}
    assert eligible(_c(1, "1x2", "draw", 0.3, 4.0), min_prob=0.2, max_prob=0.5, **kw)
    assert not eligible(_c(1, "1x2", "home", 0.7, 1.6), min_prob=0.2, max_prob=0.5, **kw)
    assert not eligible(_c(1, "1x2", "away", 0.1, 12.0), min_prob=0.2, max_prob=0.5, **kw)


def test_multi_uses_distinct_matches_and_combines_odds() -> None:
    cands = [_c(1, "1x2", "home", 0.6, 2.0), _c(1, "ou25", "over", 0.6, 1.9),  # same match: only one used
             _c(2, "1x2", "away", 0.5, 2.3), _c(3, "btts", "yes", 0.55, 1.95), _c(4, "1x2", "home", 0.3, 3.0)]
    multi = build_multi(cands, 3)
    assert {leg.match_id for leg in multi.legs} == {1, 2, 3}
    assert multi.price == pytest.approx(2.0 * 2.3 * 1.95, rel=1e-3)
    assert multi.p == pytest.approx(0.6 * 0.5 * 0.55)
    assert build_multi(cands[:2], 3) is None  # not enough distinct matches
    assert build_multi(cands, 3, min_edge=5.0) is None  # not enough combined value


def test_multi_result() -> None:
    assert multi_result([True, True, True]) is True
    assert multi_result([True, False, None]) is False  # lost as soon as one leg loses
    assert multi_result([True, None]) is None


def test_multi_template_and_outcome_list() -> None:
    sample = {"amount": 1, "currency": "inr", "outcomeIds": ["a", "b"], "idempotencyKey": "k", "betType": "sports"}
    assert template_name("BetSlipFooter_SportBet", "mutation", sample) == "BetSlipFooter_SportBet#multi"
    assert template_name("BetSlipFooter_SportBet", "mutation", {**sample, "outcomeIds": ["a"]}) == "BetSlipFooter_SportBet"
    v = build_bet_request("BetSlipFooter_SportBet", "mutation X { y }", sample, ["x", "y", "z"], 2.0, "inr")["variables"]
    assert v["outcomeIds"] == ["x", "y", "z"] and v["amount"] == 2.0
    with pytest.raises(TemplateError):
        build_bet_request("X", "mutation X { y }", {"amount": 1, "currency": "inr", "outcomeId": "a"}, ["x", "y"], 1, "inr")


def test_cashout_variables() -> None:
    v = build_cashout_variables({"betId": "old", "multiplier": 0.5}, "bet-9", 0.83)
    assert v == {"betId": "bet-9", "multiplier": 0.83}
    with pytest.raises(TemplateError):
        build_cashout_variables({"foo": 1}, "bet-9", 0.83)


def test_parse_sport_bets() -> None:
    data = {"user": {"activeSportBets": [{
        "__typename": "SportBet", "id": "b1", "active": True, "status": "active", "amount": 1, "currency": "inr",
        "potentialMultiplier": 2.37, "cashoutMultiplier": 0.9, "cashoutDisabled": False, "createdAt": "2026-11-25T08:00:00Z",
        "outcomes": [{"fixture": {"name": "Vanraure Hachinohe - Niigata"}, "outcome": {"name": "Vanraure Hachinohe"}}],
    }]}}
    (bet,) = parse_sport_bets(data)
    assert bet["id"] == "b1" and bet["potential_multiplier"] == 2.37 and bet["cashout_multiplier"] == 0.9
    assert "Vanraure" in bet["description"]
