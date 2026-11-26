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
from backend.database.models import TrainingRun
from backend.scraping.db import engine

MODEL_DIR = PROJECT_ROOT / "data" / "models"
LOG_DIR = PROJECT_ROOT / "data" / "training"
DEFAULT_FIRST_TEST_SEASON = 2018
ACTIVE = ("queued", "running")


def log_path(run_id: int) -> Path:
    return LOG_DIR / f"run_{run_id}.log"


def _set(run_id: int, **values: Any) -> None:
    with engine().begin() as connection:
        connection.execute(update(TrainingRun).where(TrainingRun.id == run_id).values(**values))


def create_run(models: list[str], first_test_season: int = DEFAULT_FIRST_TEST_SEASON) -> int:
    from backend.models.ml import ML_MODELS

    unknown = [m for m in models if m not in ML_MODELS]
    if unknown or not models:
        raise ValueError(f"Choose models from {', '.join(ML_MODELS)}")
    with engine().begin() as connection:
        return connection.execute(
            TrainingRun.__table__.insert().values(
                models=models, args={"first_test_season": first_test_season}, status="queued",
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


async def _train(run_id: int, models: list[str], first_test_season: int, as_of: date) -> dict[str, Any]:
    from backend.database.engine import AsyncSessionFactory
    from backend.evaluation.metrics import evaluate, load_prices
    from backend.models.data import load_matches
    from backend.models.features import FEATURE_COLUMNS, build_features
    from backend.models.ml import (
        MODEL_CLASSES,
        compose_auto,
        ensemble,
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
    feats = build_features(matches)
    finished = matches[matches["status"] == "finished"][["match_id", "home_goals", "away_goals", "season", "league"]]
    upcoming = upcoming_rows(feats, pd.Timestamp(as_of))
    results["data"] = {"matches": int(len(matches)), "training_rows": int(len(training_rows(feats))),
                       "features": len(FEATURE_COLUMNS), "upcoming": int(len(upcoming))}

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
        first = int((run.args or {}).get("first_test_season", DEFAULT_FIRST_TEST_SEASON))
        results = asyncio.run(_run_async(run_id, list(run.models), first))
        _set(run_id, status="finished", finished_at=datetime.now(UTC), results=results,
             message="Trained, backtested and predicting upcoming matches")
    except Exception as exc:
        traceback.print_exc()
        _set(run_id, status="failed", finished_at=datetime.now(UTC), message=f"{type(exc).__name__}: {exc}")
        raise


async def _run_async(run_id: int, models: list[str], first: int) -> dict[str, Any]:
    from backend.database.engine import dispose_database_engine

    try:
        return await _train(run_id, models, first, date.today())
    finally:
        await dispose_database_engine()


async def ml_live_predictions(matches: pd.DataFrame, as_of: date) -> dict[str, pd.DataFrame]:
    """Predict upcoming matches with every saved ML model (used by the automation loop)."""
    from backend.models.features import build_features
    from backend.models.ml import (
        MODEL_CLASSES,
        compose_auto,
        ensemble,
        load_league_choice,
        stored_name,
        upcoming_rows,
    )

    saved = [name for name in MODEL_CLASSES if (MODEL_DIR / name / "meta.json").exists()]
    if not saved:
        return {}
    feats = await asyncio.to_thread(build_features, matches)
    upcoming = upcoming_rows(feats, pd.Timestamp(as_of))
    out: dict[str, pd.DataFrame] = {}
    autos = []
    for family in saved:
        try:
            model = await asyncio.to_thread(MODEL_CLASSES[family].load, MODEL_DIR / family)
        except (ValueError, KeyError, FileNotFoundError):  # saved with older features: wait for a retrain
            continue
        preds = {v: await asyncio.to_thread(model.predict, upcoming, v) for v in ("global", "league")}
        preds["auto"] = compose_auto(preds, upcoming, load_league_choice(MODEL_DIR / family))
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
    parser.add_argument("--first-test-season", type=int, default=DEFAULT_FIRST_TEST_SEASON)
    args = parser.parse_args()
    run_id = args.run_id or create_run([m.strip() for m in args.models.split(",") if m.strip()],
                                       args.first_test_season)
    print(f"Training run #{run_id}", flush=True)
    execute(run_id)


if __name__ == "__main__":
    main()
