"""Read endpoints for canonical football data, plus the identity review queue."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from backend.core.leagues import LEAGUES
from backend.database.engine import AsyncSessionFactory
from backend.database.models import (
    Competition,
    Match,
    OddsQuote,
    ProviderEntityMapping,
    Season,
    Team,
)
from backend.identity.mappings import MappingStatus, ResolutionMethod

router = APIRouter(prefix="/api")


@router.get("/summary")
async def summary() -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        teams = (await session.execute(select(func.count()).select_from(Team))).scalar_one()
        matches = (await session.execute(select(func.count()).select_from(Match))).scalar_one()
        odds = (await session.execute(select(func.count()).select_from(OddsQuote))).scalar_one()
        first, last = (await session.execute(select(func.min(Match.match_date), func.max(Match.match_date)))).one()
        review = (await session.execute(
            select(func.count()).select_from(ProviderEntityMapping).where(
                ProviderEntityMapping.entity_type == "team",
                ProviderEntityMapping.status == MappingStatus.UNRESOLVED.value,
            )
        )).scalar_one()
    return {
        "teams": teams, "matches": matches, "odds_quotes": odds,
        "first_match": first, "last_match": last, "identity_review": review,
    }


@router.get("/competitions")
async def competitions() -> list[dict[str, Any]]:
    """Each tracked league with its seasons and match counts."""
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(
            select(Competition.code, Season.start_year, Season.label, func.count(Match.id),
                   func.max(Match.match_date))
            .join(Season, Season.competition_id == Competition.id)
            .join(Match, Match.season_id == Season.id, isouter=True)
            .group_by(Competition.code, Season.start_year, Season.label)
            .order_by(Competition.code, Season.start_year.desc())
        )).all()
    seasons: dict[str, list[dict[str, Any]]] = {}
    for code, start_year, label, n, latest in rows:
        seasons.setdefault(code, []).append(
            {"start_year": start_year, "label": label, "matches": n, "latest": latest}
        )
    return [
        {"code": lg.code, "name": lg.name, "country": lg.country, "tier": lg.tier,
         "seasons": seasons.get(lg.code, [])}
        for lg in LEAGUES
    ]


@router.get("/matches")
async def matches(
    league: str = Query(..., description="league code, e.g. ENG1"),
    season: int = Query(..., description="season start year"),
    limit: int = Query(50, le=500),
    offset: int = 0,
) -> dict[str, Any]:
    """Matches for one league-season, newest first, with Pinnacle (or average) closing 1X2 odds."""
    home, away = aliased(Team), aliased(Team)
    async with AsyncSessionFactory() as session:
        base = (
            select(Match.id)
            .join(Competition, Competition.id == Match.competition_id)
            .join(Season, Season.id == Match.season_id)
            .where(Competition.code == league.upper(), Season.start_year == season)
        )
        total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await session.execute(
            select(Match, home.name, away.name)
            .join(home, home.id == Match.home_team_id)
            .join(away, away.id == Match.away_team_id)
            .where(Match.id.in_(base))
            .order_by(Match.match_date.desc(), Match.kickoff_at.desc().nulls_last(), Match.id.desc())
            .limit(limit).offset(offset)
        )).all()

        ids = [m.id for m, _, _ in rows]
        odds: dict[int, dict[str, dict[str, float]]] = {}
        if ids:
            quotes = await session.execute(
                select(OddsQuote.match_id, OddsQuote.bookmaker, OddsQuote.market, OddsQuote.selection,
                       OddsQuote.price, OddsQuote.is_closing)
                .where(and_(OddsQuote.match_id.in_(ids), OddsQuote.bookmaker.in_(["pinnacle", "avg"])))
            )
            for match_id, bookmaker, market, selection, price, is_closing in quotes:
                key = f"{bookmaker}:{market}:{'close' if is_closing else 'open'}"
                odds.setdefault(match_id, {}).setdefault(key, {})[selection] = float(price)

    def best_1x2(match_id: int) -> dict[str, Any] | None:
        book = odds.get(match_id, {})
        for key in ("pinnacle:1x2:close", "avg:1x2:close", "pinnacle:1x2:open", "avg:1x2:open"):
            if len(book.get(key, {})) == 3:
                bookmaker, _, kind = key.split(":")
                return {"bookmaker": bookmaker, "kind": kind, **book[key]}
        return None

    return {
        "total": total,
        "items": [
            {
                "id": m.id, "date": m.match_date, "kickoff_at": m.kickoff_at, "status": m.status,
                "home": home_name, "away": away_name,
                "home_goals": m.home_goals, "away_goals": m.away_goals,
                "ht_home_goals": m.ht_home_goals, "ht_away_goals": m.ht_away_goals,
                "odds_1x2": best_1x2(m.id),
            }
            for m, home_name, away_name in rows
        ],
    }


@router.get("/identity/review")
async def identity_review() -> dict[str, Any]:
    """Provider teams the resolver could not match confidently, plus overall mapping counts."""
    async with AsyncSessionFactory() as session:
        pending = (await session.execute(
            select(ProviderEntityMapping).where(
                ProviderEntityMapping.entity_type == "team",
                ProviderEntityMapping.status == MappingStatus.UNRESOLVED.value,
            ).order_by(ProviderEntityMapping.provider_name, ProviderEntityMapping.provider_label)
        )).scalars().all()
        counts = (await session.execute(
            select(ProviderEntityMapping.provider_name, ProviderEntityMapping.status,
                   ProviderEntityMapping.method, func.count())
            .where(ProviderEntityMapping.entity_type == "team")
            .group_by(ProviderEntityMapping.provider_name, ProviderEntityMapping.status,
                      ProviderEntityMapping.method)
        )).all()
    return {
        "pending": [
            {
                "id": m.id, "provider": m.provider_name, "provider_id": m.provider_entity_id,
                "label": m.provider_label, "country": m.context.get("country"),
                "fixtures": sum(len(v) for v in m.context.get("fixtures", {}).values()),
                "candidates": m.candidates,
            }
            for m in pending
        ],
        "counts": [
            {"provider": p, "status": s, "method": meth, "count": n} for p, s, meth, n in counts
        ],
    }


class ResolveBody(BaseModel):
    team_id: int


async def _pending_mapping(session, mapping_id: int) -> ProviderEntityMapping:
    mapping = await session.get(ProviderEntityMapping, mapping_id)
    if mapping is None or mapping.entity_type != "team":
        raise HTTPException(404, "Mapping not found")
    return mapping


@router.post("/identity/{mapping_id}/resolve")
async def resolve(mapping_id: int, body: ResolveBody) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        mapping = await _pending_mapping(session, mapping_id)
        team = await session.get(Team, body.team_id)
        if team is None:
            raise HTTPException(404, "Team not found")
        clash = (await session.execute(
            select(ProviderEntityMapping.provider_label).where(
                ProviderEntityMapping.provider_name == mapping.provider_name,
                ProviderEntityMapping.entity_type == "team",
                ProviderEntityMapping.status == MappingStatus.ACTIVE.value,
                ProviderEntityMapping.canonical_id == team.id,
                ProviderEntityMapping.id != mapping.id,
            )
        )).scalar_one_or_none()
        if clash:
            raise HTTPException(409, f"{team.name} is already matched to {mapping.provider_name} team '{clash}'")
        mapping.canonical_id = team.id
        mapping.status = MappingStatus.ACTIVE.value
        mapping.method = ResolutionMethod.MANUAL_OVERRIDE.value
        mapping.confidence = 1.0
        await session.commit()
    return {"ok": True}


@router.post("/identity/{mapping_id}/reject")
async def reject(mapping_id: int) -> dict[str, Any]:
    """Mark a provider team as not one of ours (e.g. a cup opponent from another country)."""
    async with AsyncSessionFactory() as session:
        mapping = await _pending_mapping(session, mapping_id)
        mapping.canonical_id = None
        mapping.status = MappingStatus.REJECTED.value
        mapping.method = ResolutionMethod.MANUAL_OVERRIDE.value
        await session.commit()
    return {"ok": True}
