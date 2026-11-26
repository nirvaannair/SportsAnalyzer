"""Team news page: latest scored articles and a 7-day news mood per team."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import Integer, cast, func, select

from backend.database.engine import AsyncSessionFactory
from backend.database.models import NewsArticle, NewsMention, Team

router = APIRouter(prefix="/api/news")


@router.get("/articles")
async def articles(league: str | None = None, team_id: int | None = None, injury: bool | None = None,
                   limit: int = Query(60, le=300)) -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        query = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
        if league:
            query = query.where(NewsArticle.league == league.upper())
        if injury is not None:
            query = query.where(NewsArticle.injury == injury)
        if team_id:
            query = query.where(NewsArticle.id.in_(select(NewsMention.article_id).where(NewsMention.team_id == team_id)))
        rows = (await session.execute(query)).scalars().all()
        ids = [a.id for a in rows]
        mentions = (await session.execute(
            select(NewsMention.article_id, NewsMention.team_id, NewsMention.label, NewsMention.player_id)
            .where(NewsMention.article_id.in_(ids)))).all() if ids else []
    tags: dict[int, dict[str, list]] = {}
    for article_id, team, label, player in mentions:
        entry = tags.setdefault(article_id, {"teams": [], "players": []})
        (entry["players"] if player or team is None else entry["teams"]).append({"id": team or player, "name": label})
    return [{"id": a.id, "league": a.league, "published_at": a.published_at, "headline": a.headline,
             "summary": a.summary, "url": a.url, "sentiment": a.sentiment, "injury": a.injury,
             "signals": a.signals, **tags.get(a.id, {"teams": [], "players": []})} for a in rows]


@router.get("/teams")
async def team_mood(league: str | None = None, days: int = 7) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=days)
    async with AsyncSessionFactory() as session:
        query = (
            select(NewsMention.team_id, Team.name, func.max(NewsArticle.league),
                   func.sum(NewsMention.weight), func.sum(NewsMention.weight * NewsArticle.sentiment),
                   func.sum(NewsMention.weight * cast(NewsArticle.injury, Integer)),
                   func.count())
            .join(NewsArticle, NewsArticle.id == NewsMention.article_id)
            .join(Team, Team.id == NewsMention.team_id)
            .where(NewsArticle.published_at >= since)
            .group_by(NewsMention.team_id, Team.name)
        )
        if league:
            query = query.where(NewsArticle.league == league.upper())
        rows = (await session.execute(query)).all()
        total = (await session.execute(select(func.count()).select_from(NewsArticle))).scalar_one()
        oldest = (await session.execute(select(func.min(NewsArticle.published_at)))).scalar_one()
    teams = [{"team_id": t, "team": name, "league": lg, "weight": round(w, 2),
              "sentiment": round(s / w, 3) if w else None, "injury_stories": round(i or 0, 2), "articles": n}
             for t, name, lg, w, s, i, n in rows]
    teams.sort(key=lambda r: (r["sentiment"] is None, -(r["sentiment"] or 0)))
    return {"days": days, "teams": teams, "total_articles": total, "collecting_since": oldest}
