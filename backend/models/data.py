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


# ---------------------------------------------------------------------------
# Player data (lineups and goal minutes from the ESPN scraper). Also odds-free.
# ---------------------------------------------------------------------------

LINEUP_COLUMNS: tuple[str, ...] = ("match_id", "date", "team_id", "player_id", "started", "minute_on", "minute_off")
GOAL_COLUMNS: tuple[str, ...] = ("match_id", "team_id", "minute", "kind")


async def load_lineups(session: AsyncSession) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(appearances, goals): who played which minutes, and when each team scored.

    Own goals are credited to the team that benefited (ESPN lists them under the scoring side).
    """
    from backend.database.models import MatchEvent, MatchPlayer

    rows = (await session.execute(
        select(MatchPlayer.match_id, Match.match_date, MatchPlayer.team_id, MatchPlayer.player_id,
               MatchPlayer.started, MatchPlayer.minute_on, MatchPlayer.minute_off)
        .join(Match, Match.id == MatchPlayer.match_id)
    )).all()
    lineups = pd.DataFrame(rows, columns=list(LINEUP_COLUMNS))
    lineups["date"] = pd.to_datetime(lineups["date"])
    goal_rows = (await session.execute(
        select(MatchEvent.match_id, MatchEvent.team_id, MatchEvent.minute, MatchEvent.kind)
        .where(MatchEvent.kind.in_(("goal", "penalty_goal", "own_goal")), MatchEvent.team_id.is_not(None))
    )).all()
    goals = pd.DataFrame(goal_rows, columns=list(GOAL_COLUMNS))
    for frame in (lineups, goals):
        for column in frame.columns:
            if _ODDS_PATTERN.search(column):
                raise OddsLeakError(f"Column {column!r} looks odds-derived")
    return lineups, goals


NEWS_COLUMNS: tuple[str, ...] = ("team_id", "published_at", "sentiment", "injury", "weight")


async def load_news_mentions(session: AsyncSession) -> pd.DataFrame:
    """Team-linked news (headline/summary sentiment and injury flags). Betting talk is stripped
    before scoring (backend/scraping/news_analysis.py), and no prices are involved."""
    from backend.database.models import NewsArticle, NewsMention

    rows = (await session.execute(
        select(NewsMention.team_id, NewsArticle.published_at, NewsArticle.sentiment, NewsArticle.injury,
               NewsMention.weight)
        .join(NewsArticle, NewsArticle.id == NewsMention.article_id)
        .where(NewsMention.team_id.is_not(None))
    )).all()
    frame = pd.DataFrame(rows, columns=list(NEWS_COLUMNS))
    if not frame.empty:
        frame["published_at"] = pd.to_datetime(frame["published_at"], utc=True).dt.tz_localize(None)
    return frame


async def load_team_stats(session: AsyncSession) -> pd.DataFrame:
    """Per-team match stats listed in settings (features.team_stats): ESPN's and API-Football's (af_*)."""
    from backend.core.settings import cfg
    from backend.database.models import TeamMatchStats

    wanted = list(cfg("features.team_stats"))
    for name in wanted:
        if _ODDS_PATTERN.search(name):
            raise OddsLeakError(f"Team stat {name!r} looks odds-derived")
    rows = (await session.execute(select(TeamMatchStats.match_id, TeamMatchStats.team_id, TeamMatchStats.stats))).all()
    records = []
    for match_id, team_id, stats in rows:
        record = {"match_id": match_id, "team_id": team_id}
        for name in wanted:
            value = (stats or {}).get(name)
            record[name] = float(value) if isinstance(value, int | float) else None
        records.append(record)
    return pd.DataFrame.from_records(records, columns=["match_id", "team_id", *wanted])
