"""API-Football: fetch one season of fixtures per league and register its team and fixture IDs.

Costs one request per league (10 for all leagues) out of the free plan's daily quota.
The raw response is stored first; team matching then happens in the identity layer.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.leagues import LEAGUES, League
from backend.database.models import ProviderEntityMapping
from backend.identity.mappings import MappingStatus
from backend.identity.team_resolver import link_fixtures_to_matches, resolve_unresolved_teams
from backend.integrations.api_football import ApiFootballAdapter
from backend.integrations.api_football_config import build_api_football_config
from backend.integrations.base import ProviderEntityType, ProviderRequestContext
from backend.integrations.postgres_raw_repository import PostgresRawPayloadRepository
from backend.integrations.raw import RawPayload

PROVIDER = "api_football"


def parse_fixtures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten API-Football /fixtures items into the fields the identity layer needs."""
    fixtures = []
    for item in payload.get("response") or []:
        fixture, teams, goals = item.get("fixture", {}), item.get("teams", {}), item.get("goals", {})
        home, away = teams.get("home") or {}, teams.get("away") or {}
        if not fixture.get("id") or not home.get("id") or not away.get("id") or not fixture.get("date"):
            continue
        fixtures.append({
            "fixture_id": str(fixture["id"]),
            "kickoff": fixture["date"],
            "date": fixture["date"][:10],
            "status": (fixture.get("status") or {}).get("short"),
            "home_id": str(home["id"]),
            "home_name": home.get("name") or "",
            "away_id": str(away["id"]),
            "away_name": away.get("name") or "",
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
        })
    return fixtures


def team_evidence(fixtures: list[dict[str, Any]], team_id: str) -> list[dict[str, Any]]:
    """The fixtures one team played, from its own point of view (used to match it later)."""
    evidence = []
    for f in fixtures:
        if team_id not in (f["home_id"], f["away_id"]):
            continue
        evidence.append({
            "fixture_id": f["fixture_id"],
            "date": f["date"],
            "is_home": f["home_id"] == team_id,
            "home_goals": f["home_goals"],
            "away_goals": f["away_goals"],
        })
    return evidence


async def register_fixtures(session: AsyncSession, league: League, season: int,
                            fixtures: list[dict[str, Any]]) -> int:
    """Upsert one unresolved-or-existing team mapping per API-Football team, with match evidence."""
    teams: dict[str, str] = {}
    for f in fixtures:
        teams[f["home_id"]] = f["home_name"]
        teams[f["away_id"]] = f["away_name"]

    existing = {
        m.provider_entity_id: m
        for m in (await session.execute(
            select(ProviderEntityMapping).where(
                ProviderEntityMapping.provider_name == PROVIDER,
                ProviderEntityMapping.entity_type == "team",
                ProviderEntityMapping.provider_entity_id.in_(list(teams)),
            )
        )).scalars()
    }

    season_key = f"{league.code}:{season}"
    for team_id, name in teams.items():
        evidence = team_evidence(fixtures, team_id)
        mapping = existing.get(team_id)
        if mapping is None:
            session.add(ProviderEntityMapping(
                provider_name=PROVIDER,
                entity_type="team",
                provider_entity_id=team_id,
                provider_label=name,
                context={"country": league.country, "fixtures": {season_key: evidence}},
                status=MappingStatus.UNRESOLVED.value,
            ))
        else:
            context = dict(mapping.context)
            context["fixtures"] = {**context.get("fixtures", {}), season_key: evidence}
            mapping.context = context
            mapping.provider_label = name

    # Fixtures themselves, so later injuries/lineups calls (keyed by fixture id) can find our match.
    if fixtures:
        await session.execute(
            insert(ProviderEntityMapping)
            .values([{
                "provider_name": PROVIDER,
                "entity_type": "match",
                "provider_entity_id": f["fixture_id"],
                "provider_label": f"{f['home_name']} v {f['away_name']} {f['date']}",
                "context": f,
                "status": MappingStatus.UNRESOLVED.value,
            } for f in fixtures])
            .on_conflict_do_nothing(constraint="uq_provider_entity_mappings_key")
        )
    await session.flush()
    return len(teams)


async def sync_fixtures(session_factory: Callable[[], AsyncSession], season: int,
                        leagues: Iterable[League] = LEAGUES,
                        print_fn: Callable[..., None] = print) -> None:
    adapter = ApiFootballAdapter(build_api_football_config())
    try:
        async with session_factory() as session:
            repo = PostgresRawPayloadRepository(session)
            for league in leagues:
                context = ProviderRequestContext(
                    provider_name=PROVIDER,
                    endpoint="fixtures",
                    requested_at=datetime.now(UTC),
                    request_id=str(uuid4()),
                    entity_type=ProviderEntityType.MATCH,
                    parameters={"league": league.api_football_id, "season": season},
                )
                response = await adapter.fetch(context)
                if response.payload is not None:
                    await repo.store_if_new(RawPayload.from_provider_response(response))
                    await session.commit()

                payload = response.payload if isinstance(response.payload, dict) else {}
                errors = payload.get("errors")
                if not response.succeeded or errors:
                    print_fn(f"  {league.code} {season}: {response.status} {errors or response.error_message}",
                             flush=True)
                    # Quota used up, or the plan does not cover this season: every other league
                    # would fail the same way, so stop instead of wasting requests.
                    if any(word in str(errors).lower() for word in ("requests", "plan", "season", "token", "key")):
                        print_fn("  Stopping early so no more requests are spent.", flush=True)
                        break
                    continue

                fixtures = parse_fixtures(payload)
                n_teams = await register_fixtures(session, league, season, fixtures)
                await session.commit()
                print_fn(f"  {league.code} {season}: {len(fixtures)} fixtures, {n_teams} teams", flush=True)

            summary = await resolve_unresolved_teams(session)
            linked = await link_fixtures_to_matches(session)
            await session.commit()
            print_fn(f"Teams: {summary['resolved']} matched automatically, {summary['review']} need review. "
                     f"Fixtures linked to matches: {linked}.", flush=True)
    finally:
        await adapter.close()
