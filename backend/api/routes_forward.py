"""Forward test page: mock bets on upcoming matches, how they turned out, and what the models learned."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query
from sqlalchemy import select

from backend import forward
from backend.core.settings import cfg
from backend.database.engine import AsyncSessionFactory
from backend.database.models import Competition, ForwardPrediction, Match, MockBet, Team

router = APIRouter(prefix="/api/forward")


async def _frame(session) -> pd.DataFrame:
    rows = (await session.execute(
        select(ForwardPrediction.id, ForwardPrediction.model, ForwardPrediction.match_id, ForwardPrediction.kickoff_at,
               ForwardPrediction.p_home, ForwardPrediction.p_draw, ForwardPrediction.p_away,
               ForwardPrediction.outcome, ForwardPrediction.settled_at, ForwardPrediction.logloss_1x2,
               ForwardPrediction.correct_1x2, ForwardPrediction.locked, Competition.code)
        .join(Match, Match.id == ForwardPrediction.match_id)
        .join(Competition, Competition.id == Match.competition_id)
    )).all()
    return pd.DataFrame(rows, columns=["id", "model", "match_id", "kickoff_at", "p_home", "p_draw", "p_away", "outcome",
                                       "settled_at", "logloss", "correct", "locked", "league"])


async def _bets(session) -> pd.DataFrame:
    rows = (await session.execute(
        select(MockBet.prediction_id, MockBet.rule, MockBet.market, MockBet.selection, MockBet.price, MockBet.stake,
               MockBet.status, MockBet.profit)
    )).all()
    return pd.DataFrame(rows, columns=["prediction_id", "rule", "market", "selection", "price", "stake", "status", "profit"])


@router.get("/summary")
async def summary() -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        preds = await _frame(session)
        bets = await _bets(session)
        calib = await forward.calibrations(session)
    window = cfg("forward.rolling_window")
    models = []
    for model, group in preds.groupby("model") if not preds.empty else []:
        settled = group[group["settled_at"].notna()].sort_values("kickoff_at")
        mb = bets.merge(group[["id", "kickoff_at"]], left_on="prediction_id", right_on="id") if not bets.empty else bets
        rules = {}
        for rule, rb in (mb.groupby("rule") if not mb.empty else []):
            done = rb[rb["status"] != "open"]
            priced = done[done["profit"].notna()]
            series = priced.sort_values("kickoff_at")
            rules[rule] = {
                "bets": int(len(done)), "open": int((rb["status"] == "open").sum()),
                "won": int((done["status"] == "won").sum()), "priced": int(len(priced)),
                "profit": float(priced["profit"].sum()) if len(priced) else 0.0,
                "roi": float(priced["profit"].sum() / priced["stake"].sum()) if len(priced) else None,
                "cumulative": [{"t": str(k)[:10], "profit": round(float(v), 3)}
                               for k, v in zip(series["kickoff_at"], series["profit"].cumsum(), strict=False)],
            }
        rolling = []
        if len(settled):
            roll_loss = settled["logloss"].rolling(window, min_periods=1).mean()
            roll_acc = settled["correct"].astype(float).rolling(window, min_periods=1).mean()
            rolling = [{"t": str(k)[:10], "logloss": round(float(a), 4), "accuracy": round(float(b), 4)}
                       for k, a, b in zip(settled["kickoff_at"], roll_loss, roll_acc, strict=False)]
        calibration = []
        if len(settled):
            probs = settled[["p_home", "p_draw", "p_away"]].to_numpy()
            onehot = np.zeros_like(probs)
            onehot[np.arange(len(settled)), [forward.OUTCOMES.index(o) for o in settled["outcome"]]] = 1
            p, y = probs.ravel(), onehot.ravel()
            edges = np.linspace(0, 1, cfg("evaluation.calibration_bins") + 1)
            for lo, hi in zip(edges[:-1], edges[1:], strict=True):
                mask = (p >= lo) & (p < hi)
                if mask.sum():
                    calibration.append({"bucket": f"{lo:.1f}-{hi:.1f}", "predicted": float(p[mask].mean()),
                                        "observed": float(y[mask].mean()), "count": int(mask.sum())})
        models.append({
            "model": model, "predictions": int(len(group)), "open": int((~group["locked"]).sum()),
            "settled": int(len(settled)),
            "logloss": float(settled["logloss"].mean()) if len(settled) else None,
            "accuracy": float(settled["correct"].mean()) if len(settled) else None,
            "by_league": [{"league": lg, "n": int(len(g)), "logloss": float(g["logloss"].mean()),
                           "accuracy": float(g["correct"].mean())} for lg, g in settled.groupby("league")],
            "rules": rules, "rolling": rolling, "calibration": calibration, "correction": calib.get(model),
        })
    models.sort(key=lambda m: (m["logloss"] is None, m["logloss"] or 0))
    return {"models": models, "calibration_min_matches": cfg("forward.calibration_min_matches"),
            "first_prediction": str(preds["kickoff_at"].min())[:10] if not preds.empty else None}


@router.get("/predictions")
async def predictions(model: str | None = None, status: str = Query("open", pattern="^(open|settled)$"),
                      limit: int = Query(100, le=500)) -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        query = (select(ForwardPrediction, Match, Competition.code)
                 .join(Match, Match.id == ForwardPrediction.match_id)
                 .join(Competition, Competition.id == Match.competition_id))
        model = model or cfg("strategies.default_model")
        query = query.where(ForwardPrediction.model == model)
        if status == "open":
            query = query.where(ForwardPrediction.settled_at.is_(None)).order_by(ForwardPrediction.kickoff_at)
        else:
            query = query.where(ForwardPrediction.settled_at.is_not(None)).order_by(ForwardPrediction.kickoff_at.desc())
        rows = (await session.execute(query.limit(limit))).all()
        teams = dict((await session.execute(select(Team.id, Team.name))).all())
        ids = [fp.id for fp, _, _ in rows]
        bets = (await session.execute(select(MockBet).where(MockBet.prediction_id.in_(ids or [0])))).scalars().all()
    by_pred: dict[int, list[dict[str, Any]]] = {}
    for b in bets:
        by_pred.setdefault(b.prediction_id, []).append({"rule": b.rule, "market": b.market, "selection": b.selection,
                                                        "price": b.price, "status": b.status, "profit": b.profit})
    return [{"id": fp.id, "model": fp.model, "league": lg, "kickoff_at": fp.kickoff_at,
             "home": teams.get(m.home_team_id), "away": teams.get(m.away_team_id),
             "p_home": fp.p_home, "p_draw": fp.p_draw, "p_away": fp.p_away, "locked": fp.locked,
             "score": f"{m.home_goals}-{m.away_goals}" if m.home_goals is not None else None,
             "outcome": fp.outcome, "correct": fp.correct_1x2, "logloss": fp.logloss_1x2,
             "bets": by_pred.get(fp.id, [])} for fp, m, lg in rows]
