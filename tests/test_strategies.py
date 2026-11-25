import pytest

from backend.strategies.core import (
    Candidate,
    bankroll,
    best_per_market,
    eligible,
    kelly_fraction_full,
    settle_profit,
    stake_size,
    won,
)


def test_compounding_splits_winnings() -> None:
    # +100 win, -50 loss, +100 win with 60% reinvested
    b = bankroll(500, 60, [100, -50, 100], open_stakes=[10])
    assert b.pot == pytest.approx(500 + 60 - 50 + 60)  # 570
    assert b.banked == pytest.approx(40 + 40)
    assert b.profit == pytest.approx(150)
    assert b.available == pytest.approx(560)
    assert b.peak_pot == pytest.approx(570)


def test_full_and_zero_reinvest() -> None:
    assert bankroll(100, 100, [50]).pot == 150 and bankroll(100, 100, [50]).banked == 0
    assert bankroll(100, 0, [50]).pot == 100 and bankroll(100, 0, [50]).banked == 50


def test_drawdown() -> None:
    b = bankroll(100, 100, [100, -60])  # peak 200, now 140
    assert b.drawdown_pct == pytest.approx(30)


def test_kelly() -> None:
    assert kelly_fraction_full(0.5, 3.0) == pytest.approx(0.25)
    assert kelly_fraction_full(0.3, 3.0) == 0.0  # no edge, no bet


def test_stake_size_rules() -> None:
    # flat 2% of 500 = 10, capped by max_stake
    assert stake_size("flat", 500, 0.5, 2.5, stake_pct=2, kelly_fraction=0.25, max_stake=1) == 1
    assert stake_size("flat", 500, 0.5, 2.5, stake_pct=2, kelly_fraction=0.25, max_stake=50) == 10
    # quarter Kelly: 0.25 * 0.25 * 400 = 25
    assert stake_size("kelly", 400, 0.5, 3.0, stake_pct=2, kelly_fraction=0.25, max_stake=100) == 25
    # below the ₹1 minimum -> no bet; never more than available
    assert stake_size("flat", 20, 0.5, 2.5, stake_pct=2, kelly_fraction=0.25, max_stake=10) == 0
    assert stake_size("flat", 3, 0.5, 2.5, stake_pct=100, kelly_fraction=0.25, max_stake=10) == 3


def test_settlement() -> None:
    assert won("1x2", "home", 2, 1) and won("1x2", "draw", 1, 1) and won("1x2", "away", 0, 3)
    assert won("ou25", "over", 2, 1) and won("ou25", "under", 1, 1)
    assert won("btts", "yes", 1, 1) and won("btts", "no", 2, 0)
    assert settle_profit(10, 2.5, True) == 15 and settle_profit(10, 2.5, False) == -10


def _c(match, market, selection, p, price, outcome="o"):
    return Candidate(match, market, selection, p, price, "stake", outcome)


def test_one_selection_per_market_best_edge_first() -> None:
    picks = best_per_market([_c(1, "1x2", "home", 0.5, 2.2), _c(1, "1x2", "away", 0.4, 3.0),
                             _c(1, "ou25", "over", 0.6, 1.9), _c(2, "1x2", "draw", 0.3, 3.2)])
    # edges: away +20% (beats home +10%), over +14%, draw -4%
    assert [(c.match_id, c.market, c.selection) for c in picks] == [
        (1, "1x2", "away"), (1, "ou25", "over"), (2, "1x2", "draw")]


def test_eligibility() -> None:
    kw = {"min_edge": 0.05, "min_price": 1.3, "max_price": 6.0, "markets": ["1x2"]}
    assert eligible(_c(1, "1x2", "home", 0.5, 2.2), real_money=True, **kw)
    assert not eligible(_c(1, "1x2", "home", 0.45, 2.2), real_money=False, **kw)  # edge -1%
    assert not eligible(_c(1, "ou25", "over", 0.6, 2.0), real_money=False, **kw)  # market off
    assert not eligible(_c(1, "1x2", "home", 0.2, 8.0), real_money=False, **kw)  # price too high
    assert not eligible(_c(1, "1x2", "home", 0.5, 2.2, outcome=None), real_money=True, **kw)  # no Stake outcome
