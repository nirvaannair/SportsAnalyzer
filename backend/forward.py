"""Forward test: mock bets on every upcoming match, inside the app only (never sent to Stake).

1. snapshot()  — copies each model's live prediction for every upcoming match into
                 forward_predictions; it keeps updating until kickoff, then it is LOCKED.
                 Mock bets (pretend, 1 unit, no money) are placed from it:
                   * favourite: the outcome the model thinks most likely;
                   * value: any 1X2 / Over-Under pick where p × price − 1 ≥ forward.value_min_edge
                     (price = the pre-match price, used only as the payout).
2. settle()    — once the real result is in: log loss, right/wrong, mock bet profit.
3. calibrate() — learns from the misses: per model, a temperature T fitted on settled forward
                 predictions (p ∝ p_raw^(1/T)). T > 1 means the model was over-confident and
                 gets softened, T < 1 means it was too timid. Applied to live predictions once a
                 model has enough settled matches (forward.calibration_min_matches).
Everything here learns from real results only; prices are payouts, never inputs (README §5.0).
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import cfg
from backend.database.models import (
    AppSetting,
    ForwardPrediction,
    Match,
    MockBet,
    ModelRun,
    Prediction,
)

CALIBRATION_KEY = "forward_calibration"
OUTCOMES = ("home", "draw", "away")


# ---------------------------------------------------------------------------------------------
# Calibration (learning from forward-test misses)
# ---------------------------------------------------------------------------------------------

def apply_temperature(probs: np.ndarray, temperature: float) -> np.ndarray:
    """Rows of probabilities -> softened (T>1) or sharpened (T<1), still summing to 1."""
    scaled = np.power(np.clip(probs, 1e-12, 1), 1.0 / temperature)
    return scaled / scaled.sum(axis=1, keepdims=True)


def fit_temperature(probs: np.ndarray, outcome: np.ndarray) -> float:
    low, high = cfg("forward.temperature_bounds")

    def loss(t: float) -> float:
        p = apply_temperature(probs, t)
        return float(-np.mean(np.log(np.clip(p[np.arange(len(outcome)), outcome], 1e-12, 1))))

    return float(minimize_scalar(loss, bounds=(low, high), method="bounded").x)


async def calibrations(session: AsyncSession) -> dict[str, dict[str, Any]]:
    row = await session.get(AppSetting, CALIBRATION_KEY)
    return dict(row.value) if row and isinstance(row.value, dict) else {}


async def active_temperature(session: AsyncSession, model: str) -> float:
    entry = (await calibrations(session)).get(model)
    return float(entry["temperature"]) if entry and entry.get("active") else 1.0


async def calibrate(session: AsyncSession) -> dict[str, dict[str, Any]]:
    """Fit a temperature per model on its settled forward predictions (raw probabilities)."""
    rows = (await session.execute(
        select(ForwardPrediction.model, ForwardPrediction.raw, ForwardPrediction.outcome)
        .where(ForwardPrediction.settled_at.is_not(None))
    )).all()
    by_model: dict[str, list[tuple[list[float], int]]] = {}
    for model, raw, outcome in rows:
        if raw and outcome in OUTCOMES:
            by_model.setdefault(model, []).append(([raw["p_home"], raw["p_draw"], raw["p_away"]], OUTCOMES.index(outcome)))
    result: dict[str, dict[str, Any]] = {}
    for model, items in by_model.items():
        probs = np.array([p for p, _ in items])
        outcome = np.array([o for _, o in items])
        t = fit_temperature(probs, outcome)
        before = float(-np.mean(np.log(probs[np.arange(len(outcome)), outcome])))
        after_p = apply_temperature(probs, t)
        after = float(-np.mean(np.log(after_p[np.arange(len(outcome)), outcome])))
        result[model] = {"temperature": round(t, 4), "n": len(items), "logloss_before": round(before, 5),
                         "logloss_after": round(after, 5),
                         "active": len(items) >= cfg("forward.calibration_min_matches"),
                         "fitted_at": datetime.now(UTC).isoformat()}
    statement = insert(AppSetting).values(key=CALIBRATION_KEY, value=result)
    await session.execute(statement.on_conflict_do_update(index_elements=["key"], set_={"value": statement.excluded.value}))
    return result


async def calibrate_predictions(session: AsyncSession, model: str, preds: pd.DataFrame) -> pd.DataFrame:
    """Apply the model's learned temperature to its live 1X2 probabilities (no-op until active)."""
    t = await active_temperature(session, model)
    if t == 1.0 or preds.empty:
        return preds
    preds = preds.copy()
    cols = ["p_home", "p_draw", "p_away"]
    preds[cols] = apply_temperature(preds[cols].to_numpy(dtype=float), t)
    return preds


# ---------------------------------------------------------------------------------------------
# Snapshot + mock bets
# ---------------------------------------------------------------------------------------------

def _kickoff(match: Match) -> datetime:
    if match.kickoff_at:
        return match.kickoff_at if match.kickoff_at.tzinfo else match.kickoff_at.replace(tzinfo=UTC)
    return datetime.combine(match.match_date, time.min, tzinfo=UTC)


def mock_picks(p: dict[str, float | None], prices: dict[str, float]) -> list[dict[str, Any]]:
    """The pretend bets for one prediction: the favourite, plus value picks at the available prices."""
    stake = cfg("forward.mock_stake")
    probs = {"1x2": {s: p[f"p_{s}"] for s in OUTCOMES}}
    if p.get("p_over25") is not None:
        probs["ou25"] = {"over": p["p_over25"], "under": 1 - p["p_over25"]}
    favourite = max(OUTCOMES, key=lambda s: probs["1x2"][s])
    picks = [{"rule": "favourite", "market": "1x2", "selection": favourite, "p_model": probs["1x2"][favourite],
              "price": prices.get(f"1x2_{favourite}"), "stake": stake}]
    for market, selections in probs.items():
        for selection, prob in selections.items():
            price = prices.get(f"{market}_{selection}")
            if price and prob * price - 1 >= cfg("forward.value_min_edge"):
                picks.append({"rule": "value", "market": market, "selection": selection, "p_model": prob,
                              "price": price, "stake": stake})
    return picks


async def stake_prices(session: AsyncSession, match_ids: list[int]) -> dict[int, dict[str, float]]:
    """Latest Stake prices for our matches (1X2 and Over/Under 2.5), from the helper's captures."""
    from backend.database.models import StakeFixture, StakeOutcome
    from backend.execution.stake_parse import MARKET_1X2, MARKET_TOTAL

    rows = (await session.execute(
        select(StakeFixture.match_id, StakeOutcome.market_code, StakeOutcome.specifiers, StakeOutcome.selection,
               StakeOutcome.price)
        .join(StakeOutcome, StakeOutcome.stake_fixture_id == StakeFixture.id)
        .where(StakeFixture.match_id.in_(match_ids or [0]), StakeOutcome.price.is_not(None))
        .order_by(StakeOutcome.seen_at)
    )).all()
    out: dict[int, dict[str, float]] = {}
    for match_id, market, specifiers, selection, price in rows:
        if market == MARKET_1X2 and selection in OUTCOMES:
            out.setdefault(match_id, {})[f"1x2_{selection}"] = float(price)
        elif market == MARKET_TOTAL and specifiers == "total=2.5" and selection in ("over", "under"):
            out.setdefault(match_id, {})[f"ou25_{selection}"] = float(price)
    return out


async def snapshot(session: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    """Record/refresh forward predictions for upcoming matches; lock those that have kicked off."""
    from backend.evaluation.metrics import load_prices

    now = now or datetime.now(UTC)
    wanted = set(cfg("forward.models"))
    calib = await calibrations(session)
    rows = (await session.execute(
        select(ModelRun.model, Prediction, Match)
        .join(ModelRun, ModelRun.id == Prediction.run_id)
        .join(Match, Match.id == Prediction.match_id)
        .where(ModelRun.kind == "live", Match.status == "scheduled")
    )).all()
    existing = {(f.match_id, f.model): f for f in (await session.execute(
        select(ForwardPrediction).where(ForwardPrediction.match_id.in_({m.id for _, _, m in rows} or {0}))
    )).scalars().all()}
    prices_frame = await load_prices(session, list({m.id for _, _, m in rows}))
    prices = {int(r["match_id"]): {k: float(v) for k, v in r.items() if k != "match_id" and pd.notna(v)}
              for r in prices_frame.to_dict("records")} if not prices_frame.empty else {}
    for match_id, stake in (await stake_prices(session, list({m.id for _, _, m in rows}))).items():
        prices[match_id] = {**prices.get(match_id, {}), **stake}  # Stake's own price first: it's what we'd get
    recorded = locked = 0
    for model, pred, match in rows:
        if wanted and model not in wanted:
            continue
        kickoff = _kickoff(match)
        current = existing.get((match.id, model))
        if current and current.locked:
            continue
        if kickoff <= now:  # kicked off: freeze what we had
            if current:
                current.locked = True
                locked += 1
            continue
        t = float(calib.get(model, {}).get("temperature", 1.0)) if calib.get(model, {}).get("active") else 1.0
        live = np.array([[pred.p_home, pred.p_draw, pred.p_away]])
        raw = apply_temperature(live, 1.0 / t)[0] if t != 1.0 else live[0]  # undo the calibration for "raw"
        values = {"p_home": pred.p_home, "p_draw": pred.p_draw, "p_away": pred.p_away,
                  "p_over25": pred.p_over25, "p_btts": pred.p_btts, "kickoff_at": kickoff, "updated_at": now,
                  "raw": {"p_home": float(raw[0]), "p_draw": float(raw[1]), "p_away": float(raw[2]), "temperature": t}}
        if current:
            for k, v in values.items():
                setattr(current, k, v)
        else:
            current = ForwardPrediction(match_id=match.id, model=model, first_seen_at=now, **values)
            session.add(current)
        await session.flush()
        await session.execute(delete(MockBet).where(MockBet.prediction_id == current.id))
        picks = mock_picks(values, prices.get(match.id, {}))
        if picks:
            await session.execute(insert(MockBet).values([{**pk, "prediction_id": current.id, "status": "open"} for pk in picks]))
        recorded += 1
    return {"recorded": recorded, "locked": locked}


async def settle(session: AsyncSession) -> int:
    """Score locked forward predictions whose real result is in; settle their mock bets."""
    rows = (await session.execute(
        select(ForwardPrediction, Match).join(Match, Match.id == ForwardPrediction.match_id)
        .where(ForwardPrediction.settled_at.is_(None), Match.status == "finished",
               Match.home_goals.is_not(None), Match.away_goals.is_not(None))
    )).all()
    now = datetime.now(UTC)
    for fp, match in rows:
        hg, ag = match.home_goals, match.away_goals
        outcome = "home" if hg > ag else "draw" if hg == ag else "away"
        p = {"home": fp.p_home, "draw": fp.p_draw, "away": fp.p_away}
        fp.locked, fp.outcome, fp.settled_at = True, outcome, now
        fp.logloss_1x2 = float(-np.log(max(p[outcome], 1e-12)))
        fp.correct_1x2 = max(p, key=p.get) == outcome
        won = {("1x2", outcome), ("ou25", "over" if hg + ag > 2.5 else "under")}
        for bet in (await session.execute(select(MockBet).where(MockBet.prediction_id == fp.id))).scalars():
            bet.status = "won" if (bet.market, bet.selection) in won else "lost"
            bet.profit = None if bet.price is None else (bet.stake * (bet.price - 1) if bet.status == "won" else -bet.stake)
    return len(rows)


async def cycle(session: AsyncSession) -> dict[str, Any]:
    """One automation step: snapshot upcoming, settle finished, re-learn calibration."""
    report = await snapshot(session)
    report["settled"] = await settle(session)
    if report["settled"]:
        fitted = await calibrate(session)
        report["calibrated"] = {m: v["temperature"] for m, v in fitted.items() if v["active"]}
    return report
