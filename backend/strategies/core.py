"""Strategy maths: bankroll with compounding, stake sizing, picking and settling bets.

Pure functions only (no database), so every money rule is unit-tested.

Compounding: each strategy has a pot (money it bets from) and a banked amount.
When a bet wins, `reinvest_pct`% of the profit goes back into the pot and the rest is
banked (locked away). A losing stake comes out of the pot. 100% = full compounding,
0% = flat (all winnings banked).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from backend.core.settings import cfg

MARKETS = ("1x2", "ou25", "btts")
SELECTIONS = {"1x2": ("home", "draw", "away"), "ou25": ("over", "under"), "btts": ("yes", "no")}


@dataclass(frozen=True)
class Bankroll:
    pot: float  # available to bet (before open stakes)
    banked: float  # locked profit
    open_stakes: float
    peak_pot: float
    profit: float  # total settled profit

    @property
    def available(self) -> float:
        return max(0.0, self.pot - self.open_stakes)

    @property
    def drawdown_pct(self) -> float:
        return 0.0 if self.peak_pot <= 0 else max(0.0, (self.peak_pot - self.pot) / self.peak_pot * 100)


def bankroll(start: float, reinvest_pct: float, settled_profits: Iterable[float],
             open_stakes: Iterable[float] = ()) -> Bankroll:
    """Replay settled profits in order (oldest first)."""
    share = min(max(reinvest_pct, 0.0), 100.0) / 100.0
    pot, banked, peak, total = start, 0.0, start, 0.0
    for p in settled_profits:
        total += p
        if p > 0:
            pot += p * share
            banked += p * (1 - share)
        else:
            pot += p
        peak = max(peak, pot)
    return Bankroll(pot=round(pot, 2), banked=round(banked, 2), open_stakes=round(sum(open_stakes), 2),
                    peak_pot=round(peak, 2), profit=round(total, 2))


def kelly_fraction_full(p: float, price: float) -> float:
    """Full Kelly share of bankroll for a bet at decimal `price` with win probability p."""
    if price <= 1:
        return 0.0
    return max(0.0, (p * price - 1) / (price - 1))


def stake_size(kind: str, available: float, p: float, price: float, *, stake_pct: float,
               kelly_fraction: float, max_stake: float) -> float:
    """Stake in ₹, rounded down to whole rupees; 0 means "don't bet"."""
    if kind == "kelly":
        raw = kelly_fraction * kelly_fraction_full(p, price) * available
    else:  # flat: a fixed share of the current pot (compounds automatically as the pot grows)
        raw = stake_pct / 100.0 * available
    stake = min(raw, max_stake, available)
    stake = float(int(stake))  # whole rupees
    return stake if stake >= cfg("strategies.min_stake") else 0.0


@dataclass(frozen=True)
class Candidate:
    match_id: int
    market: str
    selection: str
    p: float
    price: float
    price_source: str
    outcome_id: str | None  # Stake outcome, needed for real bets

    @property
    def edge(self) -> float:
        return self.p * self.price - 1


def best_per_market(candidates: Iterable[Candidate]) -> list[Candidate]:
    """At most one selection per match and market: the one with the biggest edge."""
    best: dict[tuple[int, str], Candidate] = {}
    for c in candidates:
        key = (c.match_id, c.market)
        if key not in best or c.edge > best[key].edge:
            best[key] = c
    return sorted(best.values(), key=lambda c: c.edge, reverse=True)


def eligible(c: Candidate, *, min_edge: float, min_price: float, max_price: float,
             markets: Iterable[str], real_money: bool, min_prob: float = 0.0, max_prob: float = 1.0) -> bool:
    """Value check plus the strategy's confidence band (e.g. only 20-60% outcomes)."""
    if c.market not in set(markets):
        return False
    if not (min_prob <= c.p <= max_prob):
        return False
    if not (min_price <= c.price <= max_price):
        return False
    if c.edge < min_edge:
        return False
    return not (real_money and not c.outcome_id)  # real bets need a Stake outcome to bet on


def won(market: str, selection: str, home_goals: int, away_goals: int) -> bool:
    if market == "1x2":
        result = "home" if home_goals > away_goals else "draw" if home_goals == away_goals else "away"
        return selection == result
    if market == "ou25":
        return (home_goals + away_goals >= 3) == (selection == "over")
    if market == "btts":
        return (home_goals > 0 and away_goals > 0) == (selection == "yes")
    raise ValueError(f"Unknown market {market}")


def settle_profit(stake: float, price: float, is_win: bool) -> float:
    return round(stake * (price - 1), 2) if is_win else -stake


@dataclass(frozen=True)
class Multi:
    legs: tuple[Candidate, ...]

    @property
    def p(self) -> float:
        result = 1.0
        for leg in self.legs:
            result *= leg.p
        return result

    @property
    def price(self) -> float:
        result = 1.0
        for leg in self.legs:
            result *= leg.price
        return round(result, 3)

    @property
    def edge(self) -> float:
        return self.p * self.price - 1


def build_multi(candidates: Iterable[Candidate], legs: int, *, min_leg_edge: float = 0.0,
                min_edge: float = 0.0) -> Multi | None:
    """Best `legs` selections from different matches, each with positive value; None if not worth it.

    Legs from different matches are treated as independent (no same-match combinations).
    """
    chosen: list[Candidate] = []
    used: set[int] = set()
    for c in sorted(candidates, key=lambda c: c.edge, reverse=True):
        if c.match_id in used or c.edge < min_leg_edge:
            continue
        chosen.append(c)
        used.add(c.match_id)
        if len(chosen) == legs:
            break
    if len(chosen) < max(2, legs):
        return None
    multi = Multi(tuple(chosen))
    return multi if multi.edge >= min_edge else None


def multi_result(leg_results: Iterable[bool | None]) -> bool | None:
    """Won only if every leg won; lost as soon as any leg lost; None while undecided."""
    results = list(leg_results)
    if any(r is False for r in results):
        return False
    if all(r is True for r in results):
        return True
    return None
