"""Data Sources page: switch the free-plan API collector and each provider on/off, set budgets, see usage."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.collector import engine
from backend.collector.providers import PROVIDERS
from backend.database.engine import AsyncSessionFactory

router = APIRouter(prefix="/api/collector")


class ProviderPatch(BaseModel):
    enabled: bool | None = None
    daily_budget: int | None = Field(default=None, ge=0, le=100_000)


class CollectorPatch(BaseModel):
    enabled: bool | None = None
    providers: dict[str, ProviderPatch] = Field(default_factory=dict)


@router.get("")
async def overview() -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        return await engine.overview(session)


@router.patch("")
async def change(body: CollectorPatch) -> dict[str, Any]:
    unknown = [name for name in body.providers if name not in PROVIDERS]
    if unknown:
        raise HTTPException(400, f"Unknown providers: {', '.join(unknown)}")
    async with AsyncSessionFactory() as session:
        state = await engine.get_state(session)
        turned_on = body.enabled and not state["enabled"]
        if body.enabled is not None:
            state["enabled"] = body.enabled
        for name, patch in body.providers.items():
            limit = PROVIDERS[name].plan_daily_limit
            if patch.daily_budget is not None and limit is not None and patch.daily_budget > limit:
                raise HTTPException(400, f"{PROVIDERS[name].label}'s free plan allows {limit} requests a day")
            if patch.enabled and not PROVIDERS[name].configured():
                raise HTTPException(400, f"{PROVIDERS[name].label} needs {PROVIDERS[name].key_env} in .env first")
            state["providers"][name].update(patch.model_dump(exclude_none=True))
            if patch.enabled is not None or patch.daily_budget is not None:
                engine.RUNTIME[name].pop("paused_until", None)  # re-check budget with the new settings
        await engine.save_state(session, state)
        if turned_on:
            await engine.plan(session)
        await session.commit()
        return await engine.overview(session)


@router.post("/plan")
async def plan() -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        added = await engine.plan(session)
        await session.commit()
    return {"added": added}


@router.post("/providers/{name}/retry-failed")
async def retry_failed(name: str) -> dict[str, Any]:
    if name not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    async with AsyncSessionFactory() as session:
        n = await engine.reset_failed(session, name)
        await session.commit()
    return {"requeued": n}
