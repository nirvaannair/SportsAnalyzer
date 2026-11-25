"""Strategy engine: turn predictions + prices into bets, settle them, and enforce stops.

One cycle (`run_cycle`):
  1. settle open bets whose match has finished (and void real bets that never went through);
  2. pause strategies whose pot fell past their drawdown stop;
  3. for each enabled strategy, pick the best-edge bets on upcoming matches and record them:
       paper   -> simulated only
       approve -> also a Stake order waiting for your click on the Stake page
       auto    -> also a Stake order approved immediately (still sent only while Execution
                  is ON, and only within the .env caps)

Probabilities come from the odds-free models. Prices are used only as the payout:
Stake's own price when the match is linked, else (paper only) the market-average price.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    Competition,
    Match,
    ModelRun,
    OddsQuote,
    Prediction,
    StakeFixture,
    StakeOrder,
    StakeOutcome,
    Strategy,
    StrategyBet,
)
from backend.execution.guardrails import GuardrailError, Limits
from backend.execution.orders import create_stake_order
from backend.strategies.core import (
    Candidate,
    bankroll,
    best_per_market,
    build_multi,
    eligible,
    multi_result,
    settle_profit,
    stake_size,
    won,
)

MIN_MINUTES_BEFORE_KICKOFF = 10
LOOKAHEAD_DAYS = 4
STAKE_PRICE_MAX_AGE = timedelta(hours=6)
REAL_MODES = ("approve", "auto")


# ----------------------------------------------------------------------------- inputs

async def upcoming_predictions(session: AsyncSession, model: str) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows = (await session.execute(
        select(Prediction, Match, Competition.code)
        .join(ModelRun, ModelRun.id == Prediction.run_id)
        .join(Match, Match.id == Prediction.match_id)
        .join(Competition, Competition.id == Match.competition_id)
        .where(ModelRun.model == model, ModelRun.kind == "live", Match.status == "scheduled",
               Match.match_date.between(date.today(), date.today() + timedelta(days=LOOKAHEAD_DAYS)))
    )).all()
    out = []
    for p, m, league in rows:
        if m.kickoff_at and m.kickoff_at < now + timedelta(minutes=MIN_MINUTES_BEFORE_KICKOFF):
            continue
        out.append({"match_id": m.id, "league": league, "p": {
            ("1x2", "home"): p.p_home, ("1x2", "draw"): p.p_draw, ("1x2", "away"): p.p_away,
            ("ou25", "over"): p.p_over25, ("ou25", "under"): None if p.p_over25 is None else 1 - p.p_over25,
            ("btts", "yes"): p.p_btts, ("btts", "no"): None if p.p_btts is None else 1 - p.p_btts,
        }})
    return out


async def stake_prices(session: AsyncSession, match_ids: list[int]) -> dict[tuple, tuple[float, str]]:
    """(match, market, selection) -> (price, stake outcome id), from fresh, active Stake outcomes."""
    if not match_ids:
        return {}
    rows = (await session.execute(
        select(StakeFixture.match_id, StakeOutcome.market_code, StakeOutcome.specifiers, StakeOutcome.selection,
               StakeOutcome.price, StakeOutcome.outcome_id)
        .join(StakeFixture, StakeFixture.id == StakeOutcome.stake_fixture_id)
        .where(StakeFixture.match_id.in_(match_ids), StakeOutcome.selection.is_not(None),
               StakeOutcome.active.is_(True), StakeOutcome.seen_at >= datetime.now(UTC) - STAKE_PRICE_MAX_AGE)
    )).all()
    out: dict[tuple, tuple[float, str]] = {}
    for match_id, code, specifiers, selection, price, outcome_id in rows:
        market = {"1": "1x2", "29": "btts"}.get(code) or ("ou25" if code == "18" and specifiers == "total=2.5" else None)
        if market and price:
            out[(match_id, market, selection)] = (float(price), outcome_id)
    return out


async def market_prices(session: AsyncSession, match_ids: list[int]) -> dict[tuple, float]:
    """Market-average pre-match prices (football-data.co.uk fixtures file), for paper trading only."""
    if not match_ids:
        return {}
    rows = (await session.execute(
        select(OddsQuote.match_id, OddsQuote.market, OddsQuote.selection, OddsQuote.price)
        .where(OddsQuote.match_id.in_(match_ids), OddsQuote.bookmaker == "avg", OddsQuote.is_closing.is_(False))
    )).all()
    return {(m, market, sel): float(price) for m, market, sel, price in rows}


# ----------------------------------------------------------------------------- settlement

async def settle(session: AsyncSession) -> int:
    open_bets = (await session.execute(
        select(StrategyBet, Match).join(Match, Match.id == StrategyBet.match_id).where(StrategyBet.status == "open")
    )).all()
    settled = 0
    now = datetime.now(UTC)
    for bet, match in open_bets:
        order = await session.get(StakeOrder, bet.stake_order_id) if bet.stake_order_id else None
        if order is not None and order.status in ("failed", "blocked", "rejected"):
            bet.status, bet.profit, bet.settled_at = "void", 0.0, now  # the real bet never happened
            settled += 1
            continue
        kicked_off = match.kickoff_at is not None and match.kickoff_at <= now or match.match_date < date.today()
        if order is not None and order.status in ("pending_approval", "approved") and kicked_off:
            order.status, order.finished_at = "rejected", now
            order.status_detail = "Expired: the match started before the bet was placed"
            bet.status, bet.profit, bet.settled_at = "void", 0.0, now
            settled += 1
            continue
        if bet.market == "multi":
            is_win = await _multi_outcome(session, bet)
            if is_win is None:
                continue
            bet.status = "won" if is_win else "lost"
            bet.profit = settle_profit(bet.stake, bet.price, is_win)
            bet.settled_at = now
            settled += 1
            continue
        if match.status != "finished" or match.home_goals is None or match.away_goals is None:
            continue
        is_win = won(bet.market, bet.selection, match.home_goals, match.away_goals)
        bet.status = "won" if is_win else "lost"
        bet.profit = settle_profit(bet.stake, bet.price, is_win)
        bet.settled_at = now
        settled += 1
    await session.flush()
    return settled


async def _multi_outcome(session: AsyncSession, bet: StrategyBet) -> bool | None:
    results = []
    for leg in bet.legs or []:
        match = await session.get(Match, leg["match_id"])
        if match is None or match.status != "finished" or match.home_goals is None or match.away_goals is None:
            results.append(None)
        else:
            results.append(won(leg["market"], leg["selection"], match.home_goals, match.away_goals))
    return multi_result(results)


async def strategy_bankroll(session: AsyncSession, strategy: Strategy):
    rows = (await session.execute(
        select(StrategyBet.status, StrategyBet.profit, StrategyBet.stake)
        .where(StrategyBet.strategy_id == strategy.id).order_by(StrategyBet.settled_at.nulls_last(), StrategyBet.id)
    )).all()
    profits = [p for status, p, _ in rows if status in ("won", "lost") and p is not None]
    open_stakes = [s for status, _, s in rows if status == "open"]
    return bankroll(strategy.bankroll_start, strategy.reinvest_pct, profits, open_stakes)


# ----------------------------------------------------------------------------- generation

async def generate(session: AsyncSession, strategy: Strategy) -> dict[str, Any]:
    if not strategy.enabled or strategy.paused_reason:
        return {"created": 0, "skipped": "disabled" if not strategy.enabled else "paused"}
    real = strategy.mode in REAL_MODES
    limits = Limits.from_env()

    bank = await strategy_bankroll(session, strategy)
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = (await session.execute(select(func.count()).select_from(StrategyBet).where(
        StrategyBet.strategy_id == strategy.id, StrategyBet.created_at >= today_start))).scalar_one()
    already = set((await session.execute(select(StrategyBet.match_id, StrategyBet.market).where(
        StrategyBet.strategy_id == strategy.id))).all())

    preds = await upcoming_predictions(session, strategy.model)
    if strategy.leagues:
        preds = [p for p in preds if p["league"] in strategy.leagues]
    ids = [p["match_id"] for p in preds]
    stake_px = await stake_prices(session, ids)
    market_px = {} if real else await market_prices(session, ids)

    candidates = []
    for pred in preds:
        for (market, selection), p in pred["p"].items():
            if p is None or (pred["match_id"], market) in already:
                continue
            key = (pred["match_id"], market, selection)
            if key in stake_px:
                price, outcome_id, source = *stake_px[key], "stake"
            elif key in market_px:
                price, outcome_id, source = market_px[key], None, "market_avg"
            else:
                continue
            c = Candidate(pred["match_id"], market, selection, float(p), price, source, outcome_id)
            # Multis judge value on the combined bet; each leg just has to be fair value or better.
            leg_edge = 0.0 if strategy.kind == "multi" else strategy.min_edge
            if eligible(c, min_edge=leg_edge, min_price=strategy.min_price, max_price=strategy.max_price,
                        markets=strategy.markets, real_money=real,
                        min_prob=strategy.min_prob, max_prob=strategy.max_prob):
                candidates.append(c)

    if strategy.kind == "multi":
        return await _generate_multi(session, strategy, candidates, bank.available, today_count, real, limits)

    created, notes = 0, []
    available = bank.available
    for c in best_per_market(candidates):
        if today_count + created >= strategy.max_bets_per_day:
            notes.append("daily limit reached")
            break
        cap = min(strategy.max_stake, limits.max_bet) if real else strategy.max_stake
        stake = stake_size(strategy.kind, available, c.p, c.price, stake_pct=strategy.stake_pct,
                           kelly_fraction=strategy.kelly_fraction, max_stake=cap)
        if stake <= 0:
            continue
        bet = StrategyBet(strategy_id=strategy.id, match_id=c.match_id, market=c.market, selection=c.selection,
                          mode=strategy.mode, p_model=c.p, price=c.price, price_source=c.price_source,
                          edge=round(c.edge, 4), stake=stake)
        if real:
            outcome = (await session.execute(select(StakeOutcome).where(
                StakeOutcome.outcome_id == c.outcome_id))).scalar_one()
            try:
                order = await create_stake_order(session, outcome, stake, source=f"strategy:{strategy.name}",
                                                 auto_approve=strategy.mode == "auto", match_id=c.match_id)
            except GuardrailError as exc:
                notes.append(str(exc))
                continue
            bet.stake_order_id = order.id
        session.add(bet)
        available -= stake
        created += 1
    await session.flush()
    return {"created": created, "candidates": len(candidates), "notes": notes}


async def _generate_multi(session: AsyncSession, strategy: Strategy, candidates: list[Candidate],
                          available: float, today_count: int, real: bool, limits: Limits) -> dict[str, Any]:
    if today_count >= strategy.max_bets_per_day:
        return {"created": 0, "candidates": len(candidates), "notes": ["daily limit reached"]}
    multi = build_multi(best_per_market(candidates), strategy.multi_legs, min_edge=strategy.min_edge)
    if multi is None:
        return {"created": 0, "candidates": len(candidates),
                "notes": [f"no {strategy.multi_legs}-leg combination with {strategy.min_edge:.0%} value"]}
    cap = min(strategy.max_stake, limits.max_bet) if real else strategy.max_stake
    stake = stake_size("flat", available, multi.p, multi.price, stake_pct=strategy.stake_pct,
                       kelly_fraction=strategy.kelly_fraction, max_stake=cap)
    if stake <= 0:
        return {"created": 0, "candidates": len(candidates), "notes": ["stake below the ₹1 minimum"]}
    legs = [{"match_id": c.match_id, "market": c.market, "selection": c.selection, "p": round(c.p, 4),
             "price": c.price, "outcome_id": c.outcome_id, "price_source": c.price_source} for c in multi.legs]
    bet = StrategyBet(strategy_id=strategy.id, match_id=multi.legs[0].match_id, market="multi",
                      selection=f"{len(legs)} legs", mode=strategy.mode, p_model=multi.p, price=multi.price,
                      price_source="stake" if all(c.price_source == "stake" for c in multi.legs) else "mixed",
                      edge=round(multi.edge, 4), stake=stake, legs=legs)
    if real:
        outcomes = [(await session.execute(select(StakeOutcome).where(
            StakeOutcome.outcome_id == c.outcome_id))).scalar_one() for c in multi.legs]
        try:
            order = await create_stake_order(session, outcomes, stake, source=f"strategy:{strategy.name}",
                                             auto_approve=strategy.mode == "auto", match_id=multi.legs[0].match_id)
        except GuardrailError as exc:
            return {"created": 0, "candidates": len(candidates), "notes": [str(exc)]}
        bet.stake_order_id = order.id
    session.add(bet)
    await session.flush()
    return {"created": 1, "candidates": len(candidates), "notes": []}


async def apply_drawdown_stop(session: AsyncSession, strategy: Strategy) -> bool:
    bank = await strategy_bankroll(session, strategy)
    if not strategy.paused_reason and bank.drawdown_pct >= strategy.drawdown_stop_pct:
        strategy.paused_reason = (f"Paused automatically: pot fell {bank.drawdown_pct:.0f}% from its peak "
                                  f"(stop at {strategy.drawdown_stop_pct:.0f}%)")
        return True
    return False


async def run_cycle(session: AsyncSession) -> dict[str, Any]:
    settled = await settle(session)
    strategies = (await session.execute(select(Strategy).order_by(Strategy.id))).scalars().all()
    report: dict[str, Any] = {"settled": settled, "strategies": {}}
    for strategy in strategies:
        paused_now = await apply_drawdown_stop(session, strategy)
        result = await generate(session, strategy)
        if paused_now:
            result["paused"] = strategy.paused_reason
        report["strategies"][strategy.name] = result
    await session.flush()
    return report



