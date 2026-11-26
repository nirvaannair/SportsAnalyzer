"""Players page: individual player ratings (with/without impact), team squads and best XI."""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from backend.database.engine import AsyncSessionFactory
from backend.database.models import Competition, Match, MatchPlayer, Player, Team
from backend.models.data import load_lineups, load_matches
from backend.models.players import PlayerRatings, player_features

router = APIRouter(prefix="/api/players")
CACHE_SECONDS = 600
_cache: dict[str, Any] = {"at": 0.0, "table": None}

POSITION_GROUP = {"G": "GK"}
FORMATION = {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3}
MIN_MINUTES_FOR_XI = 270
CURRENT_DAYS = 150  # about half a season


def position_group(code: str | None) -> str | None:
    if not code or code == "SUB":
        return None
    code = code.upper()
    if code.startswith("G"):
        return "GK"
    if code.startswith(("CD", "LB", "RB", "CB", "D", "LWB", "RWB", "SW")):
        return "DEF"
    if code.startswith(("F", "CF", "ST", "S", "LW", "RW")) or code in ("LF", "RF"):
        return "FWD"
    return "MID"


async def _table() -> pd.DataFrame:
    """One row per player with ratings and totals. Recomputed at most every 10 minutes."""
    if _cache["table"] is not None and time.monotonic() - _cache["at"] < CACHE_SECONDS:
        return _cache["table"]
    async with AsyncSessionFactory() as session:
        matches = await load_matches(session)
        lineups, goals = await load_lineups(session)
        names = dict((await session.execute(select(Player.id, Player.name))).all())
        teams = dict((await session.execute(select(Team.id, Team.name))).all())
        positions = (await session.execute(
            select(MatchPlayer.player_id, MatchPlayer.position, func.count())
            .where(MatchPlayer.position.is_not(None)).group_by(MatchPlayer.player_id, MatchPlayer.position))).all()
        scored = dict((await session.execute(
            select(MatchPlayer.player_id, func.sum(MatchPlayer.stats["totalGoals"].as_float()))
            .group_by(MatchPlayer.player_id))).all())
        assists = dict((await session.execute(
            select(MatchPlayer.player_id, func.sum(MatchPlayer.stats["goalAssists"].as_float()))
            .group_by(MatchPlayer.player_id))).all())
        league_of_team = dict((await session.execute(
            select(Match.home_team_id, Competition.code).join(Competition, Competition.id == Match.competition_id)
            .order_by(Match.match_date))).all())  # latest league each team played in

    ratings = PlayerRatings()
    player_features(matches, lineups, goals, ratings)
    usual: dict[int, Counter] = defaultdict(Counter)
    for player_id, position, n in positions:
        group = position_group(position)
        if group:
            usual[player_id][group] += n
    rows = []
    for player_id, s in ratings.players.items():
        team = ratings.team_of.get(player_id)
        rows.append({
            "id": player_id, "name": names.get(player_id, f"#{player_id}"),
            "team_id": team, "team": teams.get(team), "league": league_of_team.get(team),
            "position": usual[player_id].most_common(1)[0][0] if usual[player_id] else None,
            "apps": ratings.apps[player_id], "starts": ratings.starts[player_id],
            "minutes": round(ratings.total_minutes[player_id]),
            "goals": int(scored.get(player_id) or 0), "assists": int(assists.get(player_id) or 0),
            "impact": round(s.impact, 3),
            "on_gd90": round(s.on_gd / s.on_90s, 2) if s.on_90s > 0.5 else None,
            "off_gd90": round(s.off_gd / s.off_90s, 2) if s.off_90s > 0.5 else None,
            "last_played": ratings.last_played.get(player_id),
        })
    table = pd.DataFrame(rows)
    if not table.empty:
        # "Current" = played for his (last) club within CURRENT_DAYS of that club's latest match we
        # hold, and that club has played in the last year. A player who moved to a league we haven't
        # loaded yet (e.g. De Bruyne to Napoli) drops out of his old club's squad this way.
        latest = table["last_played"].max()
        club_latest = table.groupby("team_id")["last_played"].transform("max")
        recent_for_club = table["last_played"] >= club_latest - pd.Timedelta(days=CURRENT_DAYS)
        club_active = club_latest >= latest - pd.Timedelta(days=365)
        table["current"] = recent_for_club & club_active
        table["last_played"] = table["last_played"].dt.date.astype(str)
    _cache.update(at=time.monotonic(), table=table)
    return table


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.astype(object).where(frame.notna(), None).to_dict("records")


@router.get("")
async def players(league: str | None = None, team_id: int | None = None, q: str | None = None,
                  min_minutes: int = 450, current: bool = True,
                  limit: int = Query(100, le=1000)) -> dict[str, Any]:
    table = await _table()
    if table.empty:
        return {"total": 0, "players": [], "rated_players": 0}
    view = table[table["minutes"] >= min_minutes]
    if current:
        view = view[view["current"]]
    if league:
        view = view[view["league"] == league.upper()]
    if team_id:
        view = view[view["team_id"] == team_id]
    if q:
        view = view[view["name"].str.contains(q, case=False, na=False)]
    view = view.sort_values("impact", ascending=False)
    return {"total": int(len(view)), "players": _records(view.head(limit)),
            "rated_players": int(len(table))}


@router.get("/teams")
async def teams(league: str | None = None) -> list[dict[str, Any]]:
    table = await _table()
    if table.empty:
        return []
    view = table if not league else table[table["league"] == league.upper()]
    view = view[view["current"]]
    grouped = view.groupby(["team_id", "team", "league"], dropna=True).agg(players=("id", "count")).reset_index()
    return _records(grouped.sort_values(["league", "team"]))


@router.get("/teams/{team_id}")
async def squad(team_id: int) -> dict[str, Any]:
    table = await _table()
    if table.empty or team_id not in set(table["team_id"].dropna()):
        raise HTTPException(404, "No player data for this team yet")
    members = table[(table["team_id"] == team_id) & table["current"]].sort_values("minutes", ascending=False)
    if members.empty:
        raise HTTPException(404, "No current players for this team")
    eligible = members[members["minutes"] >= MIN_MINUTES_FOR_XI]
    xi, used = [], set()
    for group, count in FORMATION.items():
        pick = eligible[(eligible["position"] == group) & ~eligible["id"].isin(used)].nlargest(count, "impact")
        xi += [{**r, "slot": group} for r in _records(pick)]
        used |= set(pick["id"])
    return {
        "team_id": team_id, "team": members["team"].iloc[0], "league": members["league"].iloc[0],
        "squad": _records(members), "best_xi": xi,
        "best_xi_impact": round(sum(p["impact"] for p in xi), 3),
        "note": "Best XI = the highest with/without impact per position (4-3-3) among current players "
                "(played for this club in its last ~5 months of matches) with 270+ minutes.",
    }
