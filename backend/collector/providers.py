"""The free API providers the background collector uses, their free-plan limits, and what to fetch.

Every provider is used on its FREE plan only. Each has:
  * a minimum gap between requests (below the plan's per-minute limit), and
  * a default daily budget (below the plan's daily limit, leaving headroom for manual use).
The owner can switch each provider on/off and change its daily budget on the Data Sources page.

Odds endpoints are never requested: the models must not learn from bookmaker odds.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from backend.core.leagues import LEAGUES


@dataclass(frozen=True)
class TaskSpec:
    kind: str
    endpoint: str
    params: dict[str, Any]
    label: str
    priority: int


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    base_url: str
    plan: str  # human description of the free plan
    min_interval_s: float  # gap between requests
    plan_daily_limit: int | None  # None = no published daily cap
    default_daily_budget: int
    key_env: str | None  # .env variable holding the key (None = no key needed)
    key_header: str | None
    collects: str
    signup_url: str | None = None
    planner: Callable[[], list[TaskSpec]] = field(default=lambda: [])

    def key(self) -> str | None:
        return os.getenv(self.key_env) if self.key_env else None

    def configured(self) -> bool:
        return self.key_env is None or bool((self.key() or "").strip())

    def headers(self) -> dict[str, str]:
        if self.key_header and self.key():
            return {self.key_header: self.key() or ""}
        return {}


def _season_start(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


# --- API-Football (api-sports.io) ------------------------------------------
# Free plan: 100 requests/day, 10/minute, seasons 2022-2024 only (no current season).
API_FOOTBALL_SEASONS = (2024, 2023, 2022)


def _api_football_tasks() -> list[TaskSpec]:
    tasks = []
    for season in API_FOOTBALL_SEASONS:
        for lg in LEAGUES:
            p = {"league": lg.api_football_id, "season": season}
            tasks.append(TaskSpec("injuries", "injuries", p, f"Injuries {lg.name} {season}/{(season + 1) % 100:02d}", 10))
            tasks.append(TaskSpec("fixtures", "fixtures", p, f"Fixtures {lg.name} {season}/{(season + 1) % 100:02d}", 20))
    # Per-fixture player stats are added by expand_followups() once fixture lists are in.
    return tasks


# --- football-data.org --------------------------------------------------------
# Free plan: 10 requests/minute, 12 competitions incl. the Champions League (cross-league
# matches!). A free key is needed: https://www.football-data.org/client/register
FOOTBALL_DATA_COMPETITIONS = {"PL": "Premier League", "ELC": "Championship", "PD": "La Liga",
                              "SA": "Serie A", "BL1": "Bundesliga", "FL1": "Ligue 1",
                              "CL": "Champions League", "EC": "European Championship"}


def _football_data_tasks() -> list[TaskSpec]:
    tasks = []
    current = _season_start()
    for code, name in FOOTBALL_DATA_COMPETITIONS.items():
        tasks.append(TaskSpec("teams", f"v4/competitions/{code}/teams", {"season": current},
                              f"Squads {name} {current}/{(current + 1) % 100:02d}", 10))
        for season in range(current, current - 3, -1):  # the free plan serves recent seasons
            tasks.append(TaskSpec("matches", f"v4/competitions/{code}/matches", {"season": season},
                                  f"Matches {name} {season}/{(season + 1) % 100:02d}", 20 if season == current else 30))
    return tasks


# --- OpenLigaDB (Germany) -------------------------------------------------------
# Free, no key, community-run: goal minutes and scorers for Bundesliga and 2. Bundesliga.
def _openligadb_tasks() -> list[TaskSpec]:
    tasks = []
    for shortcut, name in (("bl1", "Bundesliga"), ("bl2", "2. Bundesliga")):
        for season in range(_season_start(), 2014, -1):
            tasks.append(TaskSpec("matches", f"getmatchdata/{shortcut}/{season}", {},
                                  f"Matches {name} {season}/{(season + 1) % 100:02d}", 20))
    return tasks


# --- TheSportsDB ------------------------------------------------------------------
# Free test key "123": about 30 requests/minute; team and venue metadata.
THESPORTSDB_LEAGUES = {"ENG1": 4328, "ENG2": 4329, "ESP1": 4335, "ESP2": 4400, "ITA1": 4332,
                       "ITA2": 4394, "GER1": 4331, "GER2": 4399, "FRA1": 4334, "FRA2": 4401}


def _thesportsdb_tasks() -> list[TaskSpec]:
    names = {lg.code: lg.name for lg in LEAGUES}
    key = os.getenv("THESPORTSDB_API_KEY") or "123"
    return [TaskSpec("teams", f"{key}/lookup_all_teams.php", {"id": league_id}, f"Teams {names[code]}", 10)
            for code, league_id in THESPORTSDB_LEAGUES.items()]


PROVIDERS: dict[str, Provider] = {p.name: p for p in (
    Provider(
        name="api_football", label="API-Football", base_url="https://v3.football.api-sports.io",
        plan="Free: 100 requests/day, 10/minute, seasons 2022–2024", min_interval_s=7.0,
        plan_daily_limit=100, default_daily_budget=90, key_env="API_FOOTBALL_API_KEY",
        key_header="x-apisports-key", signup_url="https://dashboard.api-football.com/register",
        collects="Injuries per league and season, fixture lists, then per-match player stats (minutes, "
                 "rating, shots, passes, duels) for every fixture, newest first.",
        planner=_api_football_tasks,
    ),
    Provider(
        name="football_data_org", label="football-data.org", base_url="https://api.football-data.org",
        plan="Free: 10 requests/minute, 12 competitions incl. Champions League", min_interval_s=7.0,
        plan_daily_limit=None, default_daily_budget=500, key_env="FOOTBALL_DATA_API_KEY",
        key_header="X-Auth-Token", signup_url="https://www.football-data.org/client/register",
        collects="Squads and matches for the top divisions plus the Champions League and Euros, "
                 "which link teams across leagues.",
        planner=_football_data_tasks,
    ),
    Provider(
        name="openligadb", label="OpenLigaDB", base_url="https://api.openligadb.de",
        plan="Free, no key (community project; we keep it gentle)", min_interval_s=3.0,
        plan_daily_limit=None, default_daily_budget=200, key_env=None, key_header=None,
        collects="Bundesliga and 2. Bundesliga matches 2015 to now with goal minutes and scorers.",
        planner=_openligadb_tasks,
    ),
    Provider(
        name="thesportsdb", label="TheSportsDB", base_url="https://www.thesportsdb.com/api/v1/json",
        plan="Free test key: about 30 requests/minute", min_interval_s=3.0,
        plan_daily_limit=None, default_daily_budget=100, key_env=None, key_header=None,
        collects="Team metadata (stadium, founded, badges) for the 10 leagues.",
        planner=_thesportsdb_tasks,
    ),
)}

FORBIDDEN_ENDPOINT_WORDS = ("odds", "bookmaker", "bets")


def check_endpoint(endpoint: str) -> None:
    """The collector never asks for odds."""
    lowered = endpoint.lower()
    if any(word in lowered for word in FORBIDDEN_ENDPOINT_WORDS):
        raise ValueError(f"Collector refuses odds endpoint {endpoint!r}")
