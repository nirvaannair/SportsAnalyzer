"""Training data for the prediction models: football data only, never bookmaker odds.

THE ODDS FIREWALL (README §5.0)
Everything in backend/models learns only from what happened on the pitch. This module
is the single way models get data, and it:
  * reads only the matches, seasons and competitions tables (never the odds table);
  * returns only whitelisted columns;
  * refuses any column whose name looks odds-related.
tests/test_odds_firewall.py also scans backend/models source code for odds access.
Prices are used only later, in backend/evaluation, as the payout of a simulated bet.
"""

from __future__ import annotations

import re

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Competition, Match, Season

# Every column a model may ever see.
ALLOWED_COLUMNS: frozenset[str] = frozenset({
    "match_id", "date", "league", "country", "tier", "season",
    "home_id", "away_id", "status", "home_goals", "away_goals",
    "home_shots", "away_shots", "home_shots_target", "away_shots_target",
    "home_corners", "away_corners", "home_red", "away_red",
})

_ODDS_PATTERN = re.compile(r"odd|price|implied|market|bookmaker|b365|pinnacle|closing|margin", re.I)


class OddsLeakError(RuntimeError):
    """Raised when odds-derived data tries to enter a model."""


def assert_odds_free(columns) -> None:
    """Fail loudly if any column is not whitelisted or looks like odds."""
    for column in columns:
        if _ODDS_PATTERN.search(str(column)):
            raise OddsLeakError(f"Column {column!r} looks odds-derived; models must not use odds.")
        if column not in ALLOWED_COLUMNS:
            raise OddsLeakError(f"Column {column!r} is not on the model data whitelist.")


_STAT_COLUMNS = {
    "HS": "home_shots", "AS": "away_shots", "HST": "home_shots_target", "AST": "away_shots_target",
    "HC": "home_corners", "AC": "away_corners", "HR": "home_red", "AR": "away_red",
}


async def load_matches(session: AsyncSession) -> pd.DataFrame:
    """All matches (finished and scheduled), oldest first, with on-pitch stats only."""
    rows = (await session.execute(
        select(
            Match.id, Match.match_date, Competition.code, Competition.country, Competition.tier,
            Season.start_year, Match.home_team_id, Match.away_team_id, Match.status,
            Match.home_goals, Match.away_goals, Match.stats,
        )
        .join(Competition, Competition.id == Match.competition_id)
        .join(Season, Season.id == Match.season_id)
        .order_by(Match.match_date, Match.id)
    )).all()

    records = []
    for (match_id, day, league, country, tier, season, home, away, status, hg, ag, stats) in rows:
        record = {
            "match_id": match_id, "date": pd.Timestamp(day), "league": league, "country": country,
            "tier": tier, "season": season, "home_id": home, "away_id": away, "status": status,
            "home_goals": hg, "away_goals": ag,
        }
        for source, column in _STAT_COLUMNS.items():
            value = (stats or {}).get(source)
            record[column] = value if isinstance(value, int) else None
        records.append(record)

    frame = pd.DataFrame.from_records(records, columns=sorted(ALLOWED_COLUMNS))
    assert_odds_free(frame.columns)
    return frame
