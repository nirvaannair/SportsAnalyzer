"""The competitions SportsAnalyzer tracks, with each provider's identifier.

This is the one place where provider league IDs are written down. Everything
else (teams, players, matches) is discovered from provider data and matched
through the identity layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.settings import cfg


@dataclass(frozen=True, slots=True)
class League:
    code: str  # our stable code, e.g. "ENG1"
    name: str
    country: str
    tier: int
    fdcuk_division: str  # football-data.co.uk division code, e.g. "E0"
    api_football_id: int  # API-Football league id
    timezone: str  # timezone football-data.co.uk kickoff times are given in
    espn_slug: str  # ESPN league slug, e.g. "eng.1"


def _load() -> tuple[League, ...]:
    """Leagues come from config/settings.toml ([[leagues]]); restart after editing them."""
    return tuple(
        League(lg["code"], lg["name"], lg["country"], int(lg["tier"]), lg["fdcuk"], int(lg["api_football"]),
               lg.get("timezone", "Europe/London"), lg["espn"])
        for lg in cfg("leagues")
    )


LEAGUES: tuple[League, ...] = _load()

LEAGUES_BY_CODE = {league.code: league for league in LEAGUES}
LEAGUES_BY_FDCUK = {league.fdcuk_division: league for league in LEAGUES}
LEAGUES_BY_API_FOOTBALL = {league.api_football_id: league for league in LEAGUES}
LEAGUES_BY_ESPN = {league.espn_slug: league for league in LEAGUES}


def season_label(start_year: int) -> str:
    """2024 -> '2024/25'."""
    return f"{start_year}/{(start_year + 1) % 100:02d}"
