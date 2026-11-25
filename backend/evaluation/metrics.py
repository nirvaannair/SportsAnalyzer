"""How good are the predictions? Judged on real results first.

Primary (real outcomes): log loss, Brier score, ranked probability score, accuracy,
calibration, for 1X2, Over/Under 2.5 and both-teams-to-score.

Prices are used here ONLY as the payout of simulated bets (ROI) and for a reporting-only
comparison with the bookmakers' closing prices. Nothing here feeds back into a model.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import OddsQuote

EPS = 1e-12
EDGE_THRESHOLDS = (0.03, 0.05, 0.10)


def _outcomes(results: pd.DataFrame) -> np.ndarray:
    hg, ag = results["home_goals"].to_numpy(), results["away_goals"].to_numpy()
    return np.where(hg > ag, 0, np.where(hg == ag, 1, 2))


def _binary_logloss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def score_1x2(probs: np.ndarray, outcome: np.ndarray) -> dict[str, float]:
    n = len(outcome)
    onehot = np.zeros_like(probs)
    onehot[np.arange(n), outcome] = 1
    cum_p, cum_y = np.cumsum(probs, axis=1)[:, :2], np.cumsum(onehot, axis=1)[:, :2]
    return {
        "logloss": float(-np.mean(np.log(np.clip(probs[np.arange(n), outcome], EPS, 1)))),
        "brier": float(np.mean(np.sum((probs - onehot) ** 2, axis=1))),
        "rps": float(np.mean(np.sum((cum_p - cum_y) ** 2, axis=1) / 2)),
        "accuracy": float(np.mean(np.argmax(probs, axis=1) == outcome)),
    }


def calibration(probs: np.ndarray, outcome: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    """Pooled over home/draw/away: within each probability bucket, how often did it happen?"""
    n = len(outcome)
    onehot = np.zeros_like(probs)
    onehot[np.arange(n), outcome] = 1
    p, y = probs.ravel(), onehot.ravel()
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (p >= lo) & (p < hi)
        if mask.sum() >= 20:
            out.append({"bucket": f"{lo:.1f}-{hi:.1f}", "predicted": float(p[mask].mean()),
                        "observed": float(y[mask].mean()), "count": int(mask.sum())})
    return out


async def load_prices(session: AsyncSession, match_ids: list[int]) -> pd.DataFrame:
    """Prices for simulated bets: market-average closing, else Bet365 closing, else average opening."""
    rows = (await session.execute(
        select(OddsQuote.match_id, OddsQuote.bookmaker, OddsQuote.market, OddsQuote.selection,
               OddsQuote.price, OddsQuote.is_closing)
        .where(OddsQuote.match_id.in_(match_ids), OddsQuote.bookmaker.in_(["avg", "bet365", "pinnacle"]))
    )).all()
    frame = pd.DataFrame(rows, columns=["match_id", "bookmaker", "market", "selection", "price", "is_closing"])
    if frame.empty:
        return pd.DataFrame(columns=["match_id"])
    frame["price"] = frame["price"].astype(float)
    preference = {("avg", True): 0, ("bet365", True): 1, ("pinnacle", True): 2, ("avg", False): 3}
    frame["rank"] = [preference.get((b, c), 9) for b, c in zip(frame["bookmaker"], frame["is_closing"], strict=True)]
    frame = frame.sort_values("rank").drop_duplicates(["match_id", "market", "selection"])
    wide = frame.pivot_table(index="match_id", columns=["market", "selection"], values="price")
    wide.columns = [f"{m}_{s}" for m, s in wide.columns]
    return wide.reset_index()


def market_reference(prices: pd.DataFrame, results: pd.DataFrame) -> dict[str, float] | None:
    """Reporting only: how the bookmakers' own (margin-removed) closing prices would have scored."""
    cols = ["1x2_home", "1x2_draw", "1x2_away"]
    if not set(cols) <= set(prices.columns):
        return None
    merged = results.merge(prices, on="match_id").dropna(subset=cols)
    if merged.empty:
        return None
    implied = 1 / merged[cols].to_numpy()
    implied /= implied.sum(axis=1, keepdims=True)
    return {**score_1x2(implied, _outcomes(merged)), "n": int(len(merged))}


def simulate_bets(preds: pd.DataFrame, results: pd.DataFrame, prices: pd.DataFrame) -> list[dict[str, Any]]:
    """Flat 1-unit bets wherever model probability × price − 1 exceeds the threshold."""
    merged = preds.merge(results, on="match_id").merge(prices, on="match_id", how="inner")
    outcome = _outcomes(merged)
    total_goals = merged["home_goals"].to_numpy() + merged["away_goals"].to_numpy()
    # football-data.co.uk has no BTTS prices, so BTTS is scored for accuracy but not bet on yet.

    bets = {
        "1x2": [("p_home", "1x2_home", outcome == 0), ("p_draw", "1x2_draw", outcome == 1),
                ("p_away", "1x2_away", outcome == 2)],
        "ou25": [("p_over25", "ou25_over", total_goals >= 3), ("p_under25", "ou25_under", total_goals < 3)],
    }
    if "p_over25" in merged.columns:
        merged["p_under25"] = 1 - merged["p_over25"]

    out = []
    for threshold in EDGE_THRESHOLDS:
        for market, selections in bets.items():
            staked = profit = 0.0
            for p_col, price_col, won in selections:
                if p_col not in merged.columns or price_col not in merged.columns:
                    continue
                p, price = merged[p_col].to_numpy(float), merged[price_col].to_numpy(float)
                take = np.isfinite(p) & np.isfinite(price) & (p * price - 1 > threshold)
                staked += take.sum()
                profit += float(np.sum(np.where(won[take], price[take] - 1, -1)))
            if staked:
                out.append({"market": market, "edge_threshold": threshold, "bets": int(staked),
                            "profit_units": round(profit, 2), "roi": round(profit / staked, 4)})
    return out


def evaluate(preds: pd.DataFrame, results: pd.DataFrame, prices: pd.DataFrame | None = None) -> dict[str, Any]:
    """Full metrics for one model's predictions on finished matches."""
    data = preds.merge(results, on="match_id")
    data = data.dropna(subset=["home_goals", "away_goals"])
    probs = data[["p_home", "p_draw", "p_away"]].to_numpy(float, copy=True)
    probs = probs / probs.sum(axis=1, keepdims=True)
    outcome = _outcomes(data)

    metrics: dict[str, Any] = {"n": int(len(data)), "1x2": score_1x2(probs, outcome),
                               "calibration_1x2": calibration(probs, outcome)}
    total = data["home_goals"].to_numpy() + data["away_goals"].to_numpy()
    if "p_over25" in data.columns:
        metrics["ou25_logloss"] = _binary_logloss(data["p_over25"].to_numpy(float), (total >= 3).astype(float))
        metrics["btts_logloss"] = _binary_logloss(
            data["p_btts"].to_numpy(float),
            ((data["home_goals"] > 0) & (data["away_goals"] > 0)).to_numpy(float))

    # Naive baseline: always predict the long-run home/draw/away frequencies.
    freq = np.bincount(outcome, minlength=3) / len(outcome)
    metrics["baseline_1x2"] = score_1x2(np.tile(freq, (len(outcome), 1)), outcome)

    metrics["by_season"] = [
        {"season": int(season), "n": int(len(g)),
         **score_1x2(g[["p_home", "p_draw", "p_away"]].to_numpy(float), _outcomes(g))}
        for season, g in data.groupby("season")
    ]
    metrics["by_league"] = [
        {"league": league, "n": int(len(g)),
         **score_1x2(g[["p_home", "p_draw", "p_away"]].to_numpy(float), _outcomes(g))}
        for league, g in data.groupby("league")
    ]
    if prices is not None and not prices.empty:
        metrics["market_reference_1x2"] = market_reference(prices, data[["match_id", "home_goals", "away_goals"]])
        metrics["simulated_bets"] = simulate_bets(preds, data[["match_id", "home_goals", "away_goals"]], prices)
    return metrics
