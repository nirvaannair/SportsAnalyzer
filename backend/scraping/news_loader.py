"""Load scraped ESPN news into news_articles / news_mentions, scored by backend.scraping.news_analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import NewsArticle, NewsMention, ProviderEntityMapping, ScrapedItem
from backend.scraping.news_analysis import analyse

SPIDER = "espn_news"
PROVIDER = "espn"


async def _mapping(session: AsyncSession, entity_type: str) -> dict[str, int]:
    rows = (await session.execute(
        select(ProviderEntityMapping.provider_entity_id, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.provider_name == PROVIDER, ProviderEntityMapping.entity_type == entity_type,
            ProviderEntityMapping.canonical_id.is_not(None))
    )).all()
    return {str(k): int(v) for k, v in rows}


async def load_news(session: AsyncSession) -> dict[str, Any]:
    teams = await _mapping(session, "team")
    players = await _mapping(session, "player")
    items = (await session.execute(
        select(ScrapedItem).where(ScrapedItem.spider == SPIDER, ScrapedItem.item_type == "news",
                                  ScrapedItem.loaded_at.is_(None))
    )).scalars().all()
    loaded = linked = 0
    for item in items:
        a = item.data
        scored = analyse(a["headline"], a.get("summary"))
        values = {
            "provider": PROVIDER, "external_id": a["id"], "league": a.get("league"),
            "published_at": datetime.fromisoformat(a["published"].replace("Z", "+00:00")),
            "headline": a["headline"], "summary": a.get("summary"), "url": a.get("url"),
            "topics": a.get("topics") or [], **scored,
        }
        statement = insert(NewsArticle).values(**values)
        article_id = (await session.execute(statement.on_conflict_do_update(
            constraint="uq_news_articles_provider_id",
            set_={k: statement.excluded[k] for k in values if k not in ("provider", "external_id")},
        ).returning(NewsArticle.id))).scalar_one()
        await session.execute(delete(NewsMention).where(NewsMention.article_id == article_id))
        article_teams = a.get("teams") or []
        weight = 1.0 / max(1, len(article_teams))  # a story about two clubs counts half for each
        rows = [{"article_id": article_id, "team_id": teams.get(t["id"]), "player_id": None,
                 "provider_team_id": t["id"], "label": t["name"][:160] or t["id"], "weight": weight}
                for t in article_teams]
        rows += [{"article_id": article_id, "team_id": None, "player_id": players.get(p["id"]),
                  "provider_team_id": None, "label": p["name"][:160] or p["id"], "weight": 0.0}
                 for p in a.get("players") or []]
        if rows:
            await session.execute(insert(NewsMention).values(rows))
        linked += sum(1 for r in rows if r["team_id"])
        item.loaded_at = datetime.now(UTC)
        loaded += 1
    return {"news_loaded": loaded, "team_links": linked}
