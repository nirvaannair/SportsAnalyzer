"""Settings page: read and change config/settings.toml values (changes go to config/settings.local.json)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core import settings as store
from backend.core.settings import cfg

router = APIRouter(prefix="/api/settings")

# Sections that only take effect after a restart (they are read once at start-up).
RESTART_SECTIONS = ("leagues", "collector")


class Patch(BaseModel):
    values: dict[str, Any]


def _check(patch: dict[str, Any], defaults: dict[str, Any], path: str = "") -> None:
    """Only existing keys may be changed, and only to a value of the same kind."""
    for key, value in patch.items():
        where = f"{path}{key}"
        if key not in defaults:
            raise HTTPException(400, f"Unknown setting {where!r}")
        current = defaults[key]
        if isinstance(current, dict):
            if not isinstance(value, dict):
                raise HTTPException(400, f"{where!r} is a group of settings")
            _check(value, current, f"{where}.")
        elif isinstance(current, bool) != isinstance(value, bool):
            raise HTTPException(400, f"{where!r} must be true or false")
        elif isinstance(current, (int, float)) and not isinstance(current, bool):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise HTTPException(400, f"{where!r} must be a number")
        elif isinstance(current, str) and not isinstance(value, str):
            raise HTTPException(400, f"{where!r} must be text")
        elif isinstance(current, list) and not isinstance(value, list):
            raise HTTPException(400, f"{where!r} must be a list")


@router.get("")
async def get_settings() -> dict[str, Any]:
    return {"effective": store.settings(), "defaults": store.defaults(), "overrides": store.overrides(),
            "restart_sections": list(RESTART_SECTIONS)}


@router.patch("")
async def change(body: Patch) -> dict[str, Any]:
    _check(body.values, store.defaults())
    store.save_overrides(body.values)
    return await get_settings()


@router.post("/reset")
async def reset(section: str | None = None) -> dict[str, Any]:
    store.reset_overrides(section)
    return await get_settings()


@router.get("/leagues")
async def leagues() -> list[dict[str, Any]]:
    return [{"code": lg["code"], "name": lg["name"], "country": lg["country"], "tier": lg["tier"]}
            for lg in cfg("leagues")]
