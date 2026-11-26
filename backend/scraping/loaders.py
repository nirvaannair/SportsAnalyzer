"""Turn scraped ESPN items into canonical data: team/match links, players, lineups, events, team stats.

Runs after every crawl (and via `python -m backend.cli load-scraped`). Safe to re-run.

1. ESPN teams are matched to our teams with the same results-based resolver as API-Football.
2. ESPN matches are linked to our matches (same teams, same date ±1 day).
3. Match details whose match and teams are linked become players / match_players /
   match_events / team_match_stats rows.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.leagues import LEAGUES_BY_CODE
from backend.database.models import (
    Match,
    MatchEvent,
    MatchPlayer,
    Player,
    ProviderEntityMapping,
    ScrapedItem,
    TeamMatchStats,
)
from backend.identity.mappings import MappingStatus, ResolutionMethod
from backend.identity.team_resolver import link_fixtures_to_matches, resolve_unresolved_teams
from backend.ingestion.catalog import ensure_competitions, ensure_season
from backend.ingestion.fdcuk import season_start_for

PROVIDER = "espn"
SPIDER = "espn_matches"


async def register_espn_teams_and_matches(session: AsyncSession) -> int:
    """Rebuild ESPN team evidence from all scraped fixtures; add match mappings for new events."""
    fixtures = (await session.execute(
        select(ScrapedItem.data).where(ScrapedItem.spider == SPIDER, ScrapedItem.item_type == "fixture")
    )).scalars().all()

    evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, tuple[str, str]] = {}
    match_rows = []
    for f in fixtures:
        league = LEAGUES_BY_CODE[f["league"]]
        for side in ("home", "away"):
            team = f[side]
            names[team["id"]] = (team["name"] or team["id"], league.country)
            evidence[team["id"]].append({
                "fixture_id": f["event_id"], "date": f["date"], "is_home": side == "home",
                "home_goals": f["home"]["score"] if f["completed"] else None,
                "away_goals": f["away"]["score"] if f["completed"] else None,
            })
        match_rows.append({
            "provider_name": PROVIDER, "entity_type": "match", "provider_entity_id": f["event_id"],
            "provider_label": f"{f['home']['name']} v {f['away']['name']} {f['date']}",
            "context": {"date": f["date"], "home_id": f["home"]["id"], "away_id": f["away"]["id"]},
            "status": MappingStatus.UNRESOLVED.value,
        })

    existing = {
        m.provider_entity_id: m for m in (await session.execute(
            select(ProviderEntityMapping).where(ProviderEntityMapping.provider_name == PROVIDER,
                                                ProviderEntityMapping.entity_type == "team")
        )).scalars()
    }
    for team_id, (name, country) in names.items():
        context = {"country": country, "fixtures": {"espn": evidence[team_id]}}
        mapping = existing.get(team_id)
        if mapping is None:
            session.add(ProviderEntityMapping(provider_name=PROVIDER, entity_type="team",
                                              provider_entity_id=team_id, provider_label=name,
                                              context=context, status=MappingStatus.UNRESOLVED.value))
        else:
            mapping.context = context
            mapping.provider_label = name

    for start in range(0, len(match_rows), 2000):
        await session.execute(insert(ProviderEntityMapping).values(match_rows[start:start + 2000])
                              .on_conflict_do_nothing(constraint="uq_provider_entity_mappings_key"))
    await session.flush()
    return len(names)


async def _player_ids(session: AsyncSession, players: dict[str, tuple[str, str | None]]) -> dict[str, int]:
    """Get or create canonical players for ESPN athlete ids (ESPN is the player seed source)."""
    known = dict((await session.execute(
        select(ProviderEntityMapping.provider_entity_id, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.provider_name == PROVIDER, ProviderEntityMapping.entity_type == "player",
            ProviderEntityMapping.provider_entity_id.in_(list(players)))
    )).all())
    for espn_id, (name, position) in players.items():
        if espn_id in known:
            continue
        player = Player(name=name or espn_id, position=position)
        session.add(player)
        await session.flush()
        session.add(ProviderEntityMapping(
            provider_name=PROVIDER, entity_type="player", provider_entity_id=espn_id, provider_label=name or espn_id,
            canonical_id=player.id, status=MappingStatus.ACTIVE.value,
            method=ResolutionMethod.DETERMINISTIC_RULE.value, confidence=1.0,
        ))
        known[espn_id] = player.id
    return known


def _played(row: dict[str, Any]) -> tuple[int, int]:
    """Sort key: (played at all, minutes on the pitch)."""
    if row["minute_on"] is None:
        return (0, 0)
    return (1, (row["minute_off"] or 90) - row["minute_on"])


def _on_off(p: dict[str, Any], end_minute: int) -> tuple[int | None, int | None]:
    if p["starter"]:
        on = 0
    elif p["subbed_in"]:
        on = p["minute_in"] if p["minute_in"] is not None else None
    else:
        return None, None  # unused substitute
    if on is None:
        return None, None
    off = end_minute
    if p["subbed_out"] and p["minute_out"] is not None:
        off = p["minute_out"]
    if p["red_card_minute"] is not None:
        off = min(off, p["red_card_minute"])
    return on, max(on, off)


async def load_match_details(session: AsyncSession, limit: int = 5000) -> dict[str, int]:
    """Write lineups/events/stats for scraped matches whose match and teams are linked."""
    team_map = dict((await session.execute(
        select(ProviderEntityMapping.provider_entity_id, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.provider_name == PROVIDER, ProviderEntityMapping.entity_type == "team",
            ProviderEntityMapping.status == MappingStatus.ACTIVE.value)
    )).all())
    match_map = dict((await session.execute(
        select(ProviderEntityMapping.provider_entity_id, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.provider_name == PROVIDER, ProviderEntityMapping.entity_type == "match",
            ProviderEntityMapping.status == MappingStatus.ACTIVE.value)
    )).all())
    items = (await session.execute(
        select(ScrapedItem).where(ScrapedItem.spider == SPIDER, ScrapedItem.item_type == "match_detail",
                                  ScrapedItem.loaded_at.is_(None)).limit(limit)
    )).scalars().all()

    loaded = waiting = 0
    for item in items:
        d = item.data
        match_id = match_map.get(d["event_id"])
        teams = {t["id"]: team_map.get(t["id"]) for t in d["teams"]}
        if match_id is None or None in teams.values() or not teams:
            waiting += 1
            continue

        players = {p["id"]: (p["name"], p["position"]) for t in d["teams"] for p in t["players"]}
        player_ids = await _player_ids(session, players)
        end_minute = max([90] + [e["minute"] for e in d["events"] if e["minute"] is not None])

        by_player: dict[int, dict] = {}
        for team in d["teams"]:
            for p in team["players"]:
                on, off = _on_off(p, end_minute)
                row = {"match_id": match_id, "team_id": teams[team["id"]], "player_id": player_ids[p["id"]],
                       "started": p["starter"], "minute_on": on, "minute_off": off,
                       "position": p["position"], "stats": p["stats"]}
                # ESPN sometimes lists a player twice in one match (e.g. once as starter, once in the
                # unused-subs list). Keep the entry that actually played the most.
                previous = by_player.get(row["player_id"])
                if previous is None or _played(row) > _played(previous):
                    by_player[row["player_id"]] = row
        rows = list(by_player.values())
        if rows:
            statement = insert(MatchPlayer).values(rows)
            await session.execute(statement.on_conflict_do_update(
                constraint="uq_match_players_match_player",
                set_={c: statement.excluded[c] for c in ("team_id", "started", "minute_on", "minute_off",
                                                          "position", "stats")}))

        await session.execute(delete(MatchEvent).where(MatchEvent.match_id == match_id))
        events = [{"match_id": match_id, "minute": e["minute"], "kind": e["kind"],
                   "team_id": teams.get(e["team_id"]) if e["team_id"] else None,
                   "player_id": player_ids.get(e["player_id"]) if e["player_id"] else None,
                   "other_player_id": player_ids.get(e["other_player_id"]) if e["other_player_id"] else None}
                  for e in d["events"]]
        if events:
            await session.execute(insert(MatchEvent).values(events))

        for ts in d["team_stats"]:
            if teams.get(ts["team_id"]) is None or not ts["stats"]:
                continue
            statement = insert(TeamMatchStats).values(match_id=match_id, team_id=teams[ts["team_id"]],
                                                      stats=ts["stats"])
            await session.execute(statement.on_conflict_do_update(
                constraint="uq_team_match_stats", set_={"stats": statement.excluded.stats}))

        item.loaded_at = datetime.now(UTC)
        loaded += 1
    await session.flush()
    return {"loaded": loaded, "waiting_for_links": waiting}


async def create_scheduled_matches(session: AsyncSession, days_back: int = 2) -> int:
    """Use ESPN's schedule to add upcoming matches we don't have yet (both teams must be linked).

    football-data.co.uk only lists the next few days; ESPN lists weeks ahead. Results for
    these matches later arrive from football-data.co.uk on the same row (same teams + date).
    """
    team_map = dict((await session.execute(
        select(ProviderEntityMapping.provider_entity_id, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.provider_name == PROVIDER, ProviderEntityMapping.entity_type == "team",
            ProviderEntityMapping.status == MappingStatus.ACTIVE.value)
    )).all())
    today = date.today()
    fixtures = (await session.execute(
        select(ScrapedItem.data).where(ScrapedItem.spider == SPIDER, ScrapedItem.item_type == "fixture")
    )).scalars().all()
    competition_ids = await ensure_competitions(session)
    created = 0
    for f in fixtures:
        if f.get("completed") or not f.get("date"):
            continue
        day = date.fromisoformat(f["date"])
        if day < today - timedelta(days=days_back):
            continue
        home, away = team_map.get(f["home"]["id"]), team_map.get(f["away"]["id"])
        if home is None or away is None:
            continue
        exists = (await session.execute(select(Match.id).where(
            Match.home_team_id == home, Match.away_team_id == away,
            Match.match_date.between(day - timedelta(days=2), day + timedelta(days=2))))).first()
        if exists:
            continue
        season_id = await ensure_season(session, competition_ids[f["league"]], season_start_for(day))
        kickoff = datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00")) if f.get("kickoff") else None
        session.add(Match(competition_id=competition_ids[f["league"]], season_id=season_id, match_date=day,
                          kickoff_at=kickoff, home_team_id=home, away_team_id=away, status="scheduled"))
        created += 1
    await session.flush()
    return created


async def load_espn(session: AsyncSession) -> dict[str, Any]:
    teams = await register_espn_teams_and_matches(session)
    resolution = await resolve_unresolved_teams(session)
    scheduled = await create_scheduled_matches(session)
    linked = await link_fixtures_to_matches(session, provider=PROVIDER)
    details = await load_match_details(session)
    return {"espn_teams": teams, "teams_resolved": resolution["resolved"], "upcoming_matches_added": scheduled,
            "teams_to_review": resolution["review"], "matches_linked": linked, **details}
