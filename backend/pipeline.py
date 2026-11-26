"""Glue between the database, the models and the evaluation, used by the CLI.

backend/models never touches odds; this module hands odds only to backend/evaluation.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ModelRun, Prediction
from backend.evaluation.metrics import evaluate, load_prices
from backend.models.backtest import MODELS, live_predictions, run_backtest
from backend.models.data import load_matches
from backend.models.dixon_coles import DixonColesParams

PREDICTION_COLUMNS = ("p_home", "p_draw", "p_away", "p_over25", "p_btts", "exp_home_goals", "exp_away_goals")


def _clean(value: Any) -> Any:
    if isinstance(value, float | np.floating):
        return None if not np.isfinite(value) else float(value)
    return value


async def _store(session: AsyncSession, model: str, kind: str, preds: pd.DataFrame,
                 params: dict[str, Any], metrics: dict[str, Any], trained_until: date | None) -> int:
    """Replace the previous run of this model+kind with this one."""
    if kind == "live":  # apply what the forward test has learned about this model (no-op until enough matches)
        from backend.forward import calibrate_predictions
        preds = await calibrate_predictions(session, model, preds)
    old_runs = (await session.execute(
        select(ModelRun.id).where(ModelRun.model == model, ModelRun.kind == kind)
    )).scalars().all()
    if old_runs:
        await session.execute(delete(ModelRun).where(ModelRun.id.in_(old_runs)))

    run = ModelRun(model=model, kind=kind, params=params, metrics=metrics, trained_until=trained_until)
    session.add(run)
    await session.flush()

    records = [
        {"run_id": run.id, "match_id": int(row["match_id"]),
         **{c: _clean(row.get(c)) for c in PREDICTION_COLUMNS}}
        for row in preds.to_dict("records")
    ]
    for start in range(0, len(records), 3000):
        await session.execute(insert(Prediction), records[start:start + 3000])
    return run.id


async def backtest_and_store(session: AsyncSession, start: date,
                             progress: Callable[[str], None] = print) -> dict[str, dict[str, Any]]:
    matches = await load_matches(session)
    params = DixonColesParams()
    predictions = run_backtest(matches, pd.Timestamp(start), params, progress)

    results = matches[matches["status"] == "finished"][["match_id", "home_goals", "away_goals", "season", "league"]]
    prices = await load_prices(session, [int(m) for m in predictions["dixon_coles"]["match_id"]])

    summary = {}
    for model in MODELS:
        preds = predictions[model]
        metrics = evaluate(preds, results, prices)
        await _store(session, model, "backtest", preds,
                     {"start": str(start), **({"dixon_coles": vars(params)} if model != "elo" else {})},
                     metrics, trained_until=None)
        summary[model] = metrics
        progress(f"  {model:<12} n={metrics['n']:,}  1X2 log loss {metrics['1x2']['logloss']:.4f}  "
                 f"accuracy {metrics['1x2']['accuracy']:.1%}")
    baseline = summary["dixon_coles"]["baseline_1x2"]["logloss"]
    progress(f"  {'baseline':<12} always-the-average 1X2 log loss {baseline:.4f}")
    return summary


async def predict_and_store(session: AsyncSession, as_of: date) -> dict[str, int]:
    matches = await load_matches(session)
    predictions = live_predictions(matches, pd.Timestamp(as_of))
    counts = {}
    for model in MODELS:
        preds = predictions[model]
        await _store(session, model, "live", preds, {}, {}, trained_until=as_of)
        counts[model] = len(preds)
    # Trained ML models (saved by backend.training), if any have been trained yet.
    from backend.models.data import load_injuries, load_lineups, load_news_mentions, load_team_stats
    from backend.training import ml_live_predictions
    try:
        lineups, goal_events = await load_lineups(session)
        news = await load_news_mentions(session)
        team_stats = await load_team_stats(session)
        injuries = await load_injuries(session)
        ml = await ml_live_predictions(matches, as_of, lineups, goal_events, news, team_stats, injuries)
    except ImportError:  # xgboost / torch not installed
        ml = {}
    for model, preds in ml.items():
        await _store(session, model, "live", preds, {}, {}, trained_until=as_of)
        counts[model] = len(preds)
    return counts
