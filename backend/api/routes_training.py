"""Training page: start/stop ML training jobs and follow their live progress."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from backend import training
from backend.database.engine import AsyncSessionFactory
from backend.database.models import TrainingRun
from backend.scraping.run import pid_alive

router = APIRouter(prefix="/api/training")

MODEL_INFO = {
    "xgb": {"label": "XGBoost (gradient-boosted trees)",
            "description": "Five boosted-tree models (home/draw/away, Over/Under 2.5, BTTS, home and away goals). GPU via CUDA."},
    "nn": {"label": "Neural net (PyTorch)",
           "description": "One shared network with a head per market; goals as Poisson rates. GPU via CUDA."},
}


class StartTraining(BaseModel):
    models: list[str] = Field(default_factory=lambda: ["xgb", "nn"])
    first_test_season: int = training.DEFAULT_FIRST_TEST_SEASON
    feature_groups: dict[str, bool] = Field(default_factory=lambda: {"players": False, "news": False})


def _json(run: TrainingRun, full: bool = True) -> dict[str, Any]:
    data = {
        "id": run.id, "models": run.models, "args": run.args, "status": run.status, "device": run.device,
        "message": run.message, "created_at": run.created_at, "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
    if full:
        data["results"], data["progress"] = run.results, run.progress
    else:  # the runs list only needs the headline; fold histories and curves stay on the detail call
        data["results"] = {}
        data["progress"] = {k: v for k, v in (run.progress or {}).items() if k != "curve"}
    return data


async def _mark_dead(session, rows: list[TrainingRun]) -> None:
    for run in rows:
        if run.status == "running" and not await asyncio.to_thread(pid_alive, run.pid):
            run.status, run.finished_at = "failed", datetime.now(UTC)
            run.message = run.message or "The training process ended unexpectedly (see the log)."
    await session.commit()


@router.get("/info")
async def info() -> dict[str, Any]:
    from backend.models.ml import gpu_name

    try:
        import xgboost  # noqa: F401
        has_xgb = True
    except ImportError:
        has_xgb = False
    try:
        import torch  # noqa: F401
        has_torch = True
    except ImportError:
        has_torch = False
    gpu = await asyncio.to_thread(gpu_name)
    saved = {name: (training.MODEL_DIR / name / "meta.json").exists() for name in MODEL_INFO}
    return {"gpu": gpu, "libraries": {"xgboost": has_xgb, "torch": has_torch},
            "models": [{"name": n, **i, "saved": saved[n]} for n, i in MODEL_INFO.items()]}


@router.get("/runs")
async def runs(limit: int = 20) -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(
            select(TrainingRun).order_by(TrainingRun.id.desc()).limit(limit))).scalars().all()
        await _mark_dead(session, list(rows))
    return [_json(r, full=False) for r in rows]


@router.get("/runs/{run_id}")
async def run(run_id: int) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        row = await session.get(TrainingRun, run_id)
        if row is None:
            raise HTTPException(404, "No such training run")
        await _mark_dead(session, [row])
        return _json(row)


@router.get("/runs/{run_id}/log")
async def run_log(run_id: int, tail: int = 80) -> dict[str, Any]:
    path = training.log_path(run_id)
    if not path.exists():
        return {"lines": []}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"lines": lines[-tail:]}


@router.post("/runs")
async def start(body: StartTraining) -> dict[str, Any]:
    unknown = [m for m in body.models if m not in MODEL_INFO]
    if unknown or not body.models:
        raise HTTPException(400, f"Choose models from {', '.join(MODEL_INFO)}")
    async with AsyncSessionFactory() as session:
        busy = (await session.execute(select(func.count()).select_from(TrainingRun).where(
            TrainingRun.status.in_(training.ACTIVE)))).scalar_one()
    if busy:
        raise HTTPException(409, "A training run is already going. Stop it or wait for it to finish.")
    run_id = await asyncio.to_thread(training.create_run, body.models, body.first_test_season,
                                     body.feature_groups)
    await asyncio.to_thread(training.launch, run_id)
    return {"id": run_id}


@router.post("/runs/{run_id}/stop")
async def stop(run_id: int) -> dict[str, Any]:
    await asyncio.to_thread(training.stop, run_id)
    return {"ok": True}
