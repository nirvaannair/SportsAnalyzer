"""The free API providers the background collector uses and what to fetch from each.

Everything about a provider (address, free-plan limits, budgets, seasons, league IDs, key
names) comes from config/settings.toml under [collector.providers.*] and [[leagues]];
this module only knows HOW to turn those settings into a queue of requests.
Odds endpoints are never requested: the models must not learn from bookmaker odds.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.core.settings import cfg


@dataclass(frozen=True)
class TaskSpec:
    kind: str
    endpoint: str
    params: dict[str, Any]
    label: str
    priority: int


def _season_start(today: date | None = None) -> int:
    """European seasons start in July/August: Nov 2026 -> 2026, Mar 2027 -> 2026."""
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def _season_label(season: int) -> str:
    return f"{season}/{(season + 1) % 100:02d}"


@dataclass(frozen=True)
class Provider:
    name: str
    planner: Callable[[], list[TaskSpec]]

    @property
    def settings(self) -> dict[str, Any]:
        return cfg(f"collector.providers.{self.name}")

    def __getattr__(self, item: str) -> Any:  # label, base_url, plan, min_interval_seconds, ...
        try:
            return self.settings[item]
        except KeyError:
            if item in ("key_env", "key_header", "signup_url", "plan_daily_limit"):
                return None
            raise AttributeError(item) from None

    @property
    def min_interval_s(self) -> float:
        return float(self.settings["min_interval_seconds"])

    def key(self) -> str | None:
        if self.key_env:
            return os.getenv(self.key_env)
        optional = self.settings.get("key_env_optional")
        return (os.getenv(optional) if optional else None) or self.settings.get("default_key")

    def configured(self) -> bool:
        return self.key_env is None or bool((self.key() or "").strip())

    def headers(self) -> dict[str, str]:
        if self.key_header and self.key():
            return {self.key_header: self.key() or ""}
        return {}


# --- planners: which requests each provider should get -------------------------------------------

def _api_football_tasks() -> list[TaskSpec]:
    tasks = []
    for season in cfg("collector.providers.api_football.seasons"):
        for lg in cfg("leagues"):
            p = {"league": lg["api_football"], "season": season}
            label = f"{lg['name']} {_season_label(season)}"
            tasks.append(TaskSpec("injuries", "injuries", p, f"Injuries {label}", 10))
            tasks.append(TaskSpec("fixtures", "fixtures", p, f"Fixtures {label}", 20))
    # Per-fixture player stats are added by expand_followups() once fixture lists are in.
    return tasks


def _football_data_tasks() -> list[TaskSpec]:
    settings = cfg("collector.providers.football_data_org")
    competitions = {lg["football_data_org"]: lg["name"] for lg in cfg("leagues") if lg.get("football_data_org")}
    competitions.update(settings.get("extra_competitions", {}))
    current = _season_start()
    tasks = []
    for code, name in competitions.items():
        tasks.append(TaskSpec("teams", f"v4/competitions/{code}/teams", {"season": current},
                              f"Squads {name} {_season_label(current)}", 10))
        for season in range(current, current - settings["seasons_back"], -1):
            tasks.append(TaskSpec("matches", f"v4/competitions/{code}/matches", {"season": season},
                                  f"Matches {name} {_season_label(season)}", 20 if season == current else 30))
    return tasks


def _openligadb_tasks() -> list[TaskSpec]:
    shortcuts = cfg("collector.providers.openligadb.league_shortcuts")
    names = {lg["code"]: lg["name"] for lg in cfg("leagues")}
    first = date.fromisoformat(cfg("scraper.history_start")).year
    tasks = []
    for code, shortcut in shortcuts.items():
        for season in range(_season_start(), first - 1, -1):
            tasks.append(TaskSpec("matches", f"getmatchdata/{shortcut}/{season}", {},
                                  f"Matches {names.get(code, code)} {_season_label(season)}", 20))
    return tasks


def _thesportsdb_tasks() -> list[TaskSpec]:
    provider = PROVIDERS["thesportsdb"]
    return [TaskSpec("teams", f"{provider.key()}/lookup_all_teams.php", {"id": lg["thesportsdb"]}, f"Teams {lg['name']}", 10)
            for lg in cfg("leagues") if lg.get("thesportsdb")]


_PLANNERS: dict[str, Callable[[], list[TaskSpec]]] = {
    "api_football": _api_football_tasks,
    "football_data_org": _football_data_tasks,
    "openligadb": _openligadb_tasks,
    "thesportsdb": _thesportsdb_tasks,
}
# Only providers that are configured in settings are used.
PROVIDERS: dict[str, Provider] = {name: Provider(name, planner) for name, planner in _PLANNERS.items()
                                  if name in cfg("collector.providers")}


def check_endpoint(endpoint: str) -> None:
    """The collector never asks for odds."""
    lowered = endpoint.lower()
    if any(word in lowered for word in cfg("collector.forbidden_endpoint_words")):
        raise ValueError(f"Collector refuses odds endpoint {endpoint!r}")
