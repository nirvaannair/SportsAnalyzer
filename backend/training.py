"""Train the ML models as a background job, with live progress for the dashboard's Training page.

Started by the dashboard (POST /api/training/runs) or by hand:
    .venv/Scripts/python -m backend.training --models xgb,nn            # create and run a job here
    .venv/Scripts/python -m backend.training --run-id 3                 # a job created by the API

For each model: walk-forward backtest by season (scored on real results, like the other
models), then a final fit on every finished match, saved to data/models/<name>/ and used
to predict upcoming matches. The automation loop re-predicts with the saved models every 6 h.

Prices are read here only for evaluate() (simulated bets / market comparison), never by a model.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
import traceback
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select, update

from backend.core.config import PROJECT_ROOT
from backend.core.settings import cfg
from backend.database.models import TrainingRun
from backend.scraping.db import engine

MODEL_DIR = PROJECT_ROOT / "data" / "models"
LOG_DIR = PROJECT_ROOT / "data" / "training"
ACTIVE = ("queued", "running")


def log_path(run_id: int) -> Path:
    return LOG_DIR / f"run_{run_id}.log"


def _set(run_id: int, **values: Any) -> None:
    with engine().begin() as connection:
        connection.execute(update(TrainingRun).where(TrainingRun.id == run_id).values(**values))


def default_feature_groups() -> dict[str, bool]:
    return {name: bool(g["default"]) for name, g in cfg("training.feature_groups").items()}


def default_first_test_season() -> int:
    """The first season with match data, plus training.first_test_seasons_after_start warm-up seasons."""
    from sqlalchemy import func

    from backend.database.models import Match, Season

    with engine().connect() as connection:
        first = connection.execute(
            select(func.min(Season.start_year)).join(Match, Match.season_id == Season.id)).scalar_one()
    if first is None:
        raise ValueError("No matches in the database yet; import results first.")
    return int(first) + int(cfg("training.first_test_seasons_after_start"))


def create_run(models: list[str], first_test_season: int | None = None,
               feature_groups: dict[str, bool] | None = None, auto_select: bool | None = None) -> int:
    from backend.models.ml import ML_MODELS

    unknown = [m for m in models if m not in ML_MODELS]
    if unknown or not models:
        raise ValueError(f"Choose models from {', '.join(ML_MODELS)}")
    first_test_season = first_test_season or default_first_test_season()
    groups = feature_groups if feature_groups is not None else default_feature_groups()
    with engine().begin() as connection:
        return connection.execute(
            TrainingRun.__table__.insert().values(
                models=models, status="queued",
                args={"first_test_season": first_test_season, "feature_groups": groups,
                      "auto_select": cfg("training.auto_select") if auto_select is None else auto_select},
            ).returning(TrainingRun.id)
        ).scalar_one()


def launch(run_id: int) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with open(log_path(run_id), "ab") as log:
        process = subprocess.Popen([sys.executable, "-m", "backend.training", "--run-id", str(run_id)],
                                   cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    _set(run_id, pid=process.pid)
    return process.pid


def stop(run_id: int) -> None:
    with engine().connect() as connection:
        run = connection.execute(select(TrainingRun.pid, TrainingRun.status).where(TrainingRun.id == run_id)).one()
    if run.pid and run.status in ACTIVE:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(run.pid), "/T", "/F"], capture_output=True, check=False)
            else:
                os.kill(run.pid, 15)
        except OSError:
            pass
    _set(run_id, status="stopped", finished_at=datetime.now(UTC), message="Stopped from the dashboard")


class _Reporter:
    """Collects progress events into a live curve and writes them to the DB at most once a second."""

    MAX_POINTS = 400

    def __init__(self, run_id: int, results: dict[str, Any]) -> None:
        self.run_id, self.results = run_id, results
        self.state: dict[str, Any] = {}
        self.key: tuple | None = None
        self.last_write = 0.0

    def stage(self, model: str, stage: str, message: str) -> None:
        self.state = {"model": model, "stage": stage, "message": message, "curve": []}
        self.key = None
        print(f"[{model}] {message}", flush=True)
        self._write(force=True)

    def __call__(self, event: dict[str, Any]) -> None:
        key = (event.get("fold"), event.get("task"))
        if key != self.key:
            self._close_curve()
            self.key = key
            self.state["curve"] = []
        curve = self.state["curve"]
        curve.append([event["step"], round(event["train_loss"], 5), round(event["val_loss"], 5)])
        if len(curve) > self.MAX_POINTS:
            del curve[1::2]  # thin out, keeping the shape
        self.state.update({k: v for k, v in event.items() if k not in ("train_loss", "val_loss")})
        self.state["train_loss"], self.state["val_loss"] = event["train_loss"], event["val_loss"]
        self._write()

    def _close_curve(self) -> None:
        """Remember how the finished fold/task ended, for the run's summary table."""
        curve = self.state.get("curve")
        if not curve or self.key is None:
            return
        best = min(curve, key=lambda p: p[2])
        model = self.state["model"]
        entry = {"stage": self.state.get("stage"), "season": self.state.get("season"),
                 "task": self.state.get("task"), "steps": curve[-1][0], "best_step": best[0],
                 "best_val_loss": best[2]}
        self.results.setdefault(model, {}).setdefault("fits", []).append(entry)

    def finish_model(self) -> None:
        self._close_curve()
        self.key = None

    def _write(self, force: bool = False) -> None:
        now = time.monotonic()
        if force or now - self.last_write >= 1.0:
            _set(self.run_id, progress=self.state, results=self.results)
            self.last_write = now


def _score(metrics: dict[str, Any]) -> dict[str, Any]:
    return {"n": metrics["n"], "logloss_1x2": metrics["1x2"]["logloss"], "accuracy_1x2": metrics["1x2"]["accuracy"],
            "ou25_logloss": metrics.get("ou25_logloss"), "btts_logloss": metrics.get("btts_logloss")}


def select_feature_groups(all_feats: pd.DataFrame, report: Any) -> tuple[dict[str, bool], dict[str, Any]]:
    """Quick XGBoost backtest on the latest seasons with and without each extra input group;
    keep the groups that lower log loss by at least training.auto_select_min_gain."""
    from backend.models.features import FEATURE_GROUPS, apply_feature_groups
    from backend.models.ml import logloss_1x2, training_rows, walk_forward

    seasons = sorted(training_rows(all_feats)["season"].unique())
    first = int(seasons[-cfg("training.auto_select_seasons")]) if len(seasons) > cfg("training.auto_select_seasons") else int(seasons[0])

    def score(groups: dict[str, bool], label: str) -> float:
        report.stage("selection", "selection", f"Testing which data helps: {label}")
        data = apply_feature_groups(all_feats, groups)
        preds, _ = walk_forward(data, "xgb", first, report, per_league=False)
        p = preds["global"].merge(data[["match_id", "y_1x2"]], on="match_id")
        return float(logloss_1x2(p, p["y_1x2"]).mean())

    baseline = score({}, "without extra groups")
    tested = {"baseline": round(baseline, 5), "first_season": first, "groups": {}}
    chosen = {}
    for group in FEATURE_GROUPS:
        with_group = score({group: True}, f"with {group}")
        gain = baseline - with_group
        chosen[group] = gain >= cfg("training.auto_select_min_gain")
        tested["groups"][group] = {"logloss": round(with_group, 5), "gain": round(gain, 5), "kept": chosen[group]}
    report.finish_model()
    return chosen, tested


async def _train(run_id: int, models: list[str], first_test_season: int, as_of: date,
                 feature_groups: dict[str, bool], auto_select: bool = False) -> dict[str, Any]:
    from backend.database.engine import AsyncSessionFactory
    from backend.evaluation.metrics import evaluate, load_prices
    from backend.models.data import (
        load_injuries,
        load_lineups,
        load_matches,
        load_news_mentions,
        load_team_stats,
    )
    from backend.models.features import FEATURE_COLUMNS, apply_feature_groups, build_features
    from backend.models.ml import (
        MODEL_CLASSES,
        compose_auto,
        ensemble,
        save_feature_groups,
        save_league_choice,
        stored_name,
        training_rows,
        upcoming_rows,
        walk_forward,
    )
    from backend.pipeline import _store

    results: dict[str, Any] = {}
    report = _Reporter(run_id, results)
    report.stage("data", "features", "Loading matches and building point-in-time features")
    async with AsyncSessionFactory() as session:
        matches = await load_matches(session)
        lineups, goal_events = await load_lineups(session)
        news = await load_news_mentions(session)
        team_stats = await load_team_stats(session)
        injuries = await load_injuries(session)
    all_feats = build_features(matches, lineups, goal_events, news, team_stats, injuries)
    if auto_select:
        feature_groups, results["feature_selection"] = select_feature_groups(all_feats, report)
        _set(run_id, args={"first_test_season": first_test_season, "feature_groups": feature_groups,
                           "auto_select": True})
    feats = apply_feature_groups(all_feats, feature_groups)
    finished = matches[matches["status"] == "finished"][["match_id", "home_goals", "away_goals", "season", "league"]]
    upcoming = upcoming_rows(feats, pd.Timestamp(as_of))
    results["data"] = {"matches": int(len(matches)), "training_rows": int(len(training_rows(feats))),
                       "features": len(FEATURE_COLUMNS), "upcoming": int(len(upcoming)),
                       "matches_with_lineups": int(lineups["match_id"].nunique()) if not lineups.empty else 0,
                       "news_mentions": int(len(news)), "team_stat_rows": int(len(team_stats)),
                       "injury_rows": int(len(injuries)),
                       "feature_groups": feature_groups}

    async def store(name: str, kind: str, preds: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
        async with AsyncSessionFactory() as session:
            metrics: dict[str, Any] = {}
            if kind == "backtest":
                prices = await load_prices(session, [int(m) for m in preds["match_id"]])
                metrics = evaluate(preds, finished, prices)
            await _store(session, name, kind, preds, params, metrics, as_of if kind == "live" else None)
            await session.commit()
        return metrics

    autos_backtest, autos_live = [], []
    for family in models:
        started = time.monotonic()
        report.stage(family, "backtest",
                     f"Walk-forward backtest from {first_test_season}/{(first_test_season + 1) % 100:02d}: "
                     "global model + per-league fine-tunes for every season")
        preds, chooser = walk_forward(feats, family, first_test_season, report)
        report.finish_model()
        scores = {}
        for variant, frame in preds.items():
            metrics = await store(stored_name(family, variant), "backtest", frame,
                                  {"family": family, "variant": variant, "first_test_season": first_test_season})
            scores[variant] = _score(metrics)
        autos_backtest.append(preds["auto"])

        report.stage(family, "final", "Final fit on every finished match (global + per league)")
        model = MODEL_CLASSES[family]().fit(training_rows(feats), report)
        report.finish_model()
        choice = chooser.all_choices()
        model.save(MODEL_DIR / family)
        save_league_choice(MODEL_DIR / family, choice)
        save_feature_groups(MODEL_DIR / family, feature_groups)
        live = {"global": model.predict(upcoming, "global"), "league": model.predict(upcoming, "league")}
        live["auto"] = compose_auto(live, upcoming, choice)
        for variant, frame in live.items():
            await store(stored_name(family, variant), "live", frame, {})
        autos_live.append(live["auto"])

        results[family] = {**results.get(family, {}), "variants": scores, "leagues": chooser.summary(),
                           "live_predictions": int(len(live["auto"])),
                           "seconds": round(time.monotonic() - started, 1)}
        print(f"[{family}] done: " + ", ".join(
            f"{v} {s['logloss_1x2']:.4f}" for v, s in scores.items()), flush=True)
        report.stage(family, "done", f"{family} finished")

    if len(autos_backtest) > 1:
        report.stage("ml_ensemble", "ensemble", "Averaging the models into the ensemble")
        metrics = await store("ml_ensemble", "backtest", ensemble(autos_backtest), {"members": models})
        await store("ml_ensemble", "live", ensemble(autos_live), {"members": models})
        results["ml_ensemble"] = {"variants": {"auto": _score(metrics)}}
    return results


def execute(run_id: int) -> None:
    from backend.models.ml import gpu_name

    with engine().connect() as connection:
        run = connection.execute(select(TrainingRun.models, TrainingRun.args).where(TrainingRun.id == run_id)).one()
    gpu = gpu_name()
    _set(run_id, status="running", started_at=datetime.now(UTC), pid=os.getpid(),
         device=f"GPU: {gpu}" if gpu else "CPU (no CUDA GPU found)")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        first = int((run.args or {}).get("first_test_season") or default_first_test_season())
        groups = dict((run.args or {}).get("feature_groups") or {})
        auto = bool((run.args or {}).get("auto_select"))
        results = asyncio.run(_run_async(run_id, list(run.models), first, groups, auto))
        _set(run_id, status="finished", finished_at=datetime.now(UTC), results=results,
             message="Trained, backtested and predicting upcoming matches")
    except Exception as exc:
        traceback.print_exc()
        _set(run_id, status="failed", finished_at=datetime.now(UTC), message=f"{type(exc).__name__}: {exc}")
        raise


async def _run_async(run_id: int, models: list[str], first: int, groups: dict[str, bool],
                     auto: bool = False) -> dict[str, Any]:
    from backend.database.engine import dispose_database_engine

    try:
        return await _train(run_id, models, first, date.today(), groups, auto)
    finally:
        await dispose_database_engine()


async def ml_live_predictions(matches: pd.DataFrame, as_of: date,
                              lineups: pd.DataFrame | None = None,
                              goal_events: pd.DataFrame | None = None,
                              news: pd.DataFrame | None = None,
                              team_stats: pd.DataFrame | None = None,
                              injuries: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Predict upcoming matches with every saved ML model (used by the automation loop)."""
    from backend.models.features import apply_feature_groups, build_features
    from backend.models.ml import (
        MODEL_CLASSES,
        compose_auto,
        ensemble,
        load_feature_groups,
        load_league_choice,
        stored_name,
        upcoming_rows,
    )

    saved = [name for name in MODEL_CLASSES if (MODEL_DIR / name / "meta.json").exists()]
    if not saved:
        return {}
    feats = await asyncio.to_thread(build_features, matches, lineups, goal_events, news, team_stats, injuries)
    upcoming = upcoming_rows(feats, pd.Timestamp(as_of))
    out: dict[str, pd.DataFrame] = {}
    autos = []
    for family in saved:
        try:
            model = await asyncio.to_thread(MODEL_CLASSES[family].load, MODEL_DIR / family)
        except (ValueError, KeyError, FileNotFoundError):  # saved with older features: wait for a retrain
            continue
        rows = apply_feature_groups(upcoming, load_feature_groups(MODEL_DIR / family))  # as it was trained
        preds = {v: await asyncio.to_thread(model.predict, rows, v) for v in ("global", "league")}
        preds["auto"] = compose_auto(preds, rows, load_league_choice(MODEL_DIR / family))
        for variant, frame in preds.items():
            out[stored_name(family, variant)] = frame
        autos.append(preds["auto"])
    if len(autos) > 1:
        out["ml_ensemble"] = ensemble(autos)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the ML models (XGBoost, neural net) with live progress")
    parser.add_argument("--run-id", type=int, help="run a job created by the API")
    parser.add_argument("--models", default="xgb,nn", help="comma-separated: xgb,nn")
    parser.add_argument("--first-test-season", type=int, help="default: derived from the data (see settings)")
    parser.add_argument("--players", action=argparse.BooleanOptionalAction, help="use the lineup/player features")
    parser.add_argument("--news", action=argparse.BooleanOptionalAction, help="use the news features")
    args = parser.parse_args()
    run_id = args.run_id or create_run([m.strip() for m in args.models.split(",") if m.strip()],
                                       args.first_test_season,
                                       {**default_feature_groups(),
                                        **{k: v for k, v in (("players", args.players), ("news", args.news)) if v is not None}})
    print(f"Training run #{run_id}", flush=True)
    execute(run_id)


if __name__ == "__main__":
    main()
