"""Pure parsing of ESPN's public soccer feed (no network, no database), so it is easy to test.

Only football facts are kept. Betting fields in the feed ("odds", "pickcenter", ...) are
never copied: see README §5.0.
"""

from __future__ import annotations

import re
from typing import Any

from backend.core.leagues import League
from backend.core.settings import cfg

_CLOCK = re.compile(r"(\d+)'?(?:\s*\+\s*(\d+))?")


def scoreboard_url(league: League, month: str) -> str:
    """month as YYYYMM. (The feed accepts a single day or a whole month, not a date range.)"""
    return f"{cfg('scraper.espn.feed_url')}/{league.espn_slug}/scoreboard?dates={month}&limit=1000"


def summary_url(league: League, event_id: str) -> str:
    return f"{cfg('scraper.espn.feed_url')}/{league.espn_slug}/summary?event={event_id}"


def parse_minute(display: str | None) -> int | None:
    """"71'" -> 71, "45'+2'" -> 47, "90'+5'" -> 95."""
    if not display:
        return None
    match = _CLOCK.search(display)
    if not match:
        return None
    return int(match.group(1)) + int(match.group(2) or 0)


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_scoreboard(payload: dict[str, Any], league: League) -> list[dict[str, Any]]:
    """One record per match: ESPN ids, teams, score and whether it is finished."""
    fixtures = []
    for event in payload.get("events") or []:
        competition = (event.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in competition.get("competitors") or []}
        home, away = sides.get("home"), sides.get("away")
        if not home or not away or not event.get("id"):
            continue
        status = (event.get("status") or {}).get("type") or {}
        fixtures.append({
            "event_id": str(event["id"]),
            "league": league.code,
            "date": (event.get("date") or "")[:10],
            "kickoff": event.get("date"),
            "completed": bool(status.get("completed")),
            "status": status.get("name"),
            "home": {"id": str(home["team"]["id"]), "name": home["team"].get("displayName"),
                     "score": _int(home.get("score"))},
            "away": {"id": str(away["team"]["id"]), "name": away["team"].get("displayName"),
                     "score": _int(away.get("score"))},
        })
    return fixtures


def _player(entry: dict[str, Any]) -> dict[str, Any]:
    athlete = entry.get("athlete") or {}
    plays = entry.get("plays") or []
    sub_on = next((parse_minute(p.get("clock", {}).get("displayValue")) for p in plays
                   if p.get("substitution") and entry.get("subbedIn")), None)
    sub_off = next((parse_minute(p.get("clock", {}).get("displayValue")) for p in plays
                    if p.get("substitution") and entry.get("subbedOut")), None)
    red = next((parse_minute(p.get("clock", {}).get("displayValue")) for p in plays if p.get("redCard")), None)
    return {
        "id": str(athlete.get("id")),
        "name": athlete.get("displayName"),
        "position": (entry.get("position") or {}).get("abbreviation"),
        "jersey": entry.get("jersey"),
        "starter": bool(entry.get("starter")),
        "subbed_in": bool(entry.get("subbedIn")),
        "subbed_out": bool(entry.get("subbedOut")),
        "minute_in": sub_on,
        "minute_out": sub_off,
        "red_card_minute": red,
        "stats": {s["name"]: s.get("value") for s in entry.get("stats") or [] if "name" in s},
    }


_EVENT_KIND = {
    "goal": "goal", "goal - header": "goal", "goal - free-kick": "goal", "penalty - scored": "penalty_goal",
    "own goal": "own_goal", "substitution": "sub", "yellow card": "yellow", "red card": "red",
    "second yellow card": "red",
}


def parse_summary(payload: dict[str, Any], event_id: str, league: League) -> dict[str, Any]:
    """Lineups with on/off minutes, goals/subs/cards, and team match stats."""
    teams = []
    for roster in payload.get("rosters") or []:
        team = roster.get("team") or {}
        teams.append({
            "id": str(team.get("id")),
            "name": team.get("displayName"),
            "home_away": roster.get("homeAway"),
            "players": [_player(p) for p in roster.get("roster") or [] if (p.get("athlete") or {}).get("id")],
        })

    events = []
    for event in payload.get("keyEvents") or []:
        text = ((event.get("type") or {}).get("text") or "").lower()
        kind = _EVENT_KIND.get(text) or ("goal" if text.startswith("goal") else None)
        if kind is None:
            continue
        participants = [str((p.get("athlete") or {}).get("id")) for p in event.get("participants") or []]
        events.append({
            "kind": kind,
            "minute": parse_minute((event.get("clock") or {}).get("displayValue")),
            "team_id": str((event.get("team") or {}).get("id")) if event.get("team") else None,
            "player_id": participants[0] if participants else None,
            "other_player_id": participants[1] if len(participants) > 1 else None,
        })

    team_stats = []
    for entry in (payload.get("boxscore") or {}).get("teams") or []:
        stats = {}
        for stat in entry.get("statistics") or []:
            try:
                stats[stat["name"]] = float(stat.get("displayValue"))
            except (KeyError, TypeError, ValueError):
                continue
        team_stats.append({"team_id": str((entry.get("team") or {}).get("id")), "stats": stats})

    return {"event_id": event_id, "league": league.code, "teams": teams, "events": events,
            "team_stats": team_stats}
