"""Load scraped news (ESPN and RSS feeds) into news_articles / news_mentions, scored by news_analysis.

ESPN articles carry ESPN's own team/player tags. RSS articles are linked to teams by name: every
name we know for a team (ours plus provider labels), skipping ambiguous words from settings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import cfg
from backend.database.models import (
    NewsArticle,
    NewsMention,
    ProviderEntityMapping,
    ScrapedItem,
    Team,
)
from backend.identity.normalization import normalize_for_comparison
from backend.scraping.news_analysis import analyse

SPIDERS = ("espn_news", "rss_news")
PROVIDER = "espn"


async def _mapping(session: AsyncSession, entity_type: str) -> dict[str, int]:
    rows = (await session.execute(
        select(ProviderEntityMapping.provider_entity_id, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.provider_name == PROVIDER, ProviderEntityMapping.entity_type == entity_type,
            ProviderEntityMapping.canonical_id.is_not(None))
    )).all()
    return {str(k): int(v) for k, v in rows}


def _alias(name: str) -> str | None:
    """A searchable form of a team name, or None if it would be ambiguous."""
    ambiguous = set(cfg("news.team_names.ambiguous"))
    strip = set(cfg("news.team_names.strip_words"))
    tokens = [t for t in normalize_for_comparison(name).split() if t]
    while len(tokens) > 1 and tokens[-1] in strip:
        tokens.pop()
    while len(tokens) > 1 and tokens[0] in strip:
        tokens.pop(0)
    alias = " ".join(tokens)
    if len(alias) < cfg("news.team_names.min_alias_length") or (len(tokens) == 1 and alias in ambiguous):
        return None
    return alias


async def team_aliases(session: AsyncSession) -> dict[str, int]:
    """alias -> team id, from our team names and every provider's label for the team.
    An alias that points to two different teams is dropped."""
    names = list((await session.execute(select(Team.name, Team.id))).all())
    names += list((await session.execute(
        select(ProviderEntityMapping.provider_label, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.entity_type == "team", ProviderEntityMapping.canonical_id.is_not(None),
            ProviderEntityMapping.provider_label.is_not(None))
    )).all())
    found: dict[str, set[int]] = {}
    for name, team_id in names:
        alias = _alias(name or "")
        if alias:
            found.setdefault(alias, set()).add(int(team_id))
    aliases = {alias: ids.pop() for alias, ids in found.items() if len(ids) == 1}
    # Nicknames from settings point at a team through one of its known names.
    for nickname, team_name in cfg("news.team_names.nicknames").items():
        target = _alias(team_name) or normalize_for_comparison(team_name)
        if target in aliases:
            aliases[normalize_for_comparison(nickname)] = aliases[target]
    return aliases


def teams_in_text(text: str, aliases: dict[str, int]) -> list[tuple[int, str]]:
    """Teams named in `text` (longest names first, so 'manchester united' wins over a shorter overlap)."""
    haystack = f" {normalize_for_comparison(text)} "
    found: dict[int, str] = {}
    for alias in sorted(aliases, key=len, reverse=True):
        if f" {alias} " in haystack and aliases[alias] not in found:
            found[aliases[alias]] = alias
            haystack = haystack.replace(f" {alias} ", " ")
    return list(found.items())


async def load_news(session: AsyncSession) -> dict[str, Any]:
    teams = await _mapping(session, "team")
    players = await _mapping(session, "player")
    aliases = await team_aliases(session)
    items = (await session.execute(
        select(ScrapedItem).where(ScrapedItem.spider.in_(SPIDERS), ScrapedItem.item_type == "news",
                                  ScrapedItem.loaded_at.is_(None))
    )).scalars().all()
    loaded = linked = 0
    for item in items:
        a = item.data
        scored = analyse(a["headline"], a.get("summary"))
        values = {
            "provider": a.get("source", PROVIDER), "external_id": a["id"], "league": a.get("league"),
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
        named: list[tuple[int, str]] = []
        if not article_teams:  # RSS: find teams by name
            named = teams_in_text(f"{a['headline']} {a.get('summary') or ''}", aliases)
        weight = 1.0 / max(1, len(article_teams) or len(named))  # a story about two clubs counts half for each
        rows = [{"article_id": article_id, "team_id": teams.get(t["id"]), "player_id": None,
                 "provider_team_id": t["id"], "label": t["name"][:160] or t["id"], "weight": weight}
                for t in article_teams]
        rows += [{"article_id": article_id, "team_id": team_id, "player_id": None, "provider_team_id": None,
                  "label": alias[:160], "weight": weight} for team_id, alias in named]
        rows += [{"article_id": article_id, "team_id": None, "player_id": players.get(p["id"]),
                  "provider_team_id": None, "label": p["name"][:160] or p["id"], "weight": 0.0}
                 for p in a.get("players") or []]
        if rows:
            await session.execute(insert(NewsMention).values(rows))
        linked += sum(1 for r in rows if r["team_id"])
        item.loaded_at = datetime.now(UTC)
        loaded += 1
    return {"news_loaded": loaded, "team_links": linked}
