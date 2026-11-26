"""Central settings: config/settings.toml, overridden by config/settings.local.json (dashboard edits).

Use `cfg("training.xgb.rounds")` or `cfg("players")["half_life_days"]` at the point of use, so
edits apply without restarting (the files are re-read when they change).
"""

from __future__ import annotations

import copy
import json
import threading
import tomllib
from pathlib import Path
from typing import Any

from backend.core.config import PROJECT_ROOT

BASE_FILE = PROJECT_ROOT / "config" / "settings.toml"
LOCAL_FILE = PROJECT_ROOT / "config" / "settings.local.json"

_lock = threading.Lock()
_cache: dict[str, Any] = {"stamp": None, "data": None}


def _stamp() -> tuple[float, float]:
    def mtime(p: Path) -> float:
        return p.stat().st_mtime if p.exists() else 0.0
    return mtime(BASE_FILE), mtime(LOCAL_FILE)


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def overrides() -> dict[str, Any]:
    return json.loads(LOCAL_FILE.read_text(encoding="utf-8")) if LOCAL_FILE.exists() else {}


def defaults() -> dict[str, Any]:
    with open(BASE_FILE, "rb") as f:
        return tomllib.load(f)


def settings() -> dict[str, Any]:
    """The effective settings (a fresh deep copy is not made; treat it as read-only)."""
    stamp = _stamp()
    with _lock:
        if _cache["stamp"] != stamp:
            _cache["data"] = deep_merge(defaults(), overrides())
            _cache["stamp"] = stamp
        return _cache["data"]


def cfg(path: str, default: Any = KeyError) -> Any:
    """Dotted lookup, e.g. cfg("scraper.rate_limit.first_wait_seconds")."""
    node: Any = settings()
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            if default is KeyError:
                raise KeyError(f"Setting {path!r} is missing from config/settings.toml")
            return default
        node = node[part]
    return node


def save_overrides(patch: dict[str, Any]) -> dict[str, Any]:
    """Merge `patch` into config/settings.local.json (what the Settings page edits)."""
    with _lock:
        merged = deep_merge(overrides(), patch)
        LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
        _cache["stamp"] = None
    return merged


def reset_overrides(section: str | None = None) -> None:
    with _lock:
        if section is None:
            LOCAL_FILE.unlink(missing_ok=True)
        else:
            data = overrides()
            data.pop(section, None)
            LOCAL_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        _cache["stamp"] = None
