"""The competitions SportsAnalyzer tracks, with each provider's identifier.

This is the one place where provider league IDs are written down. Everything
else (teams, players, matches) is discovered from provider data and matched
through the identity layer.
"""

from __future__ import annotations

from dataclasses import dataclass


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


LEAGUES: tuple[League, ...] = (
    League("ENG1", "Premier League", "England", 1, "E0", 39, "Europe/London", "eng.1"),
    League("ENG2", "Championship", "England", 2, "E1", 40, "Europe/London", "eng.2"),
    League("ESP1", "La Liga", "Spain", 1, "SP1", 140, "Europe/London", "esp.1"),
    League("ESP2", "Segunda División", "Spain", 2, "SP2", 141, "Europe/London", "esp.2"),
    League("ITA1", "Serie A", "Italy", 1, "I1", 135, "Europe/London", "ita.1"),
    League("ITA2", "Serie B", "Italy", 2, "I2", 136, "Europe/London", "ita.2"),
    League("GER1", "Bundesliga", "Germany", 1, "D1", 78, "Europe/London", "ger.1"),
    League("GER2", "2. Bundesliga", "Germany", 2, "D2", 79, "Europe/London", "ger.2"),
    League("FRA1", "Ligue 1", "France", 1, "F1", 61, "Europe/London", "fra.1"),
    League("FRA2", "Ligue 2", "France", 2, "F2", 62, "Europe/London", "fra.2"),
)

LEAGUES_BY_CODE = {league.code: league for league in LEAGUES}
LEAGUES_BY_FDCUK = {league.fdcuk_division: league for league in LEAGUES}
LEAGUES_BY_API_FOOTBALL = {league.api_football_id: league for league in LEAGUES}
LEAGUES_BY_ESPN = {league.espn_slug: league for league in LEAGUES}


def season_label(start_year: int) -> str:
    """2024 -> '2024/25'."""
    return f"{start_year}/{(start_year + 1) % 100:02d}"
