"""Competitions, seasons and the provider-mapping helpers every importer shares."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.leagues import LEAGUES, League, season_label
from backend.database.models import Competition, ProviderEntityMapping, Season, Team
from backend.identity.mappings import MappingStatus, ResolutionMethod


async def ensure_competitions(session: AsyncSession) -> dict[str, int]:
    """Insert the tracked leagues if missing. Returns {league code: competition id}."""
    await session.execute(
        insert(Competition)
        .values([
            {"code": lg.code, "name": lg.name, "country": lg.country, "tier": lg.tier}
            for lg in LEAGUES
        ])
        .on_conflict_do_nothing(index_elements=["code"])
    )
    rows = await session.execute(select(Competition.code, Competition.id))
    return dict(rows.all())


async def ensure_season(session: AsyncSession, competition_id: int, start_year: int) -> int:
    await session.execute(
        insert(Season)
        .values(competition_id=competition_id, start_year=start_year, label=season_label(start_year))
        .on_conflict_do_nothing(index_elements=["competition_id", "start_year"])
    )
    return (
        await session.execute(
            select(Season.id).where(
                Season.competition_id == competition_id, Season.start_year == start_year
            )
        )
    ).scalar_one()


@dataclass
class TeamDirectory:
    """Cache of one provider's team mappings for the duration of an import."""

    provider: str
    by_provider_id: dict[str, int | None] = field(default_factory=dict)

    async def load(self, session: AsyncSession) -> None:
        rows = await session.execute(
            select(ProviderEntityMapping.provider_entity_id, ProviderEntityMapping.canonical_id).where(
                ProviderEntityMapping.provider_name == self.provider,
                ProviderEntityMapping.entity_type == "team",
            )
        )
        self.by_provider_id = dict(rows.all())

    async def seed_team(self, session: AsyncSession, provider_id: str, name: str, league: League) -> int:
        """Get or create the canonical team for a *seed* provider.

        A seed provider (football-data.co.uk) defines canonical teams: the first time it
        mentions a team, that team is created. Other providers are matched against these
        by the resolver instead.
        """
        existing = self.by_provider_id.get(provider_id)
        if existing is not None:
            return existing

        team = Team(name=name, country=league.country)
        session.add(team)
        await session.flush()
        session.add(
            ProviderEntityMapping(
                provider_name=self.provider,
                entity_type="team",
                provider_entity_id=provider_id,
                provider_label=name,
                context={"country": league.country, "first_seen_league": league.code},
                canonical_id=team.id,
                status=MappingStatus.ACTIVE.value,
                method=ResolutionMethod.DETERMINISTIC_RULE.value,
                confidence=1.0,
            )
        )
        self.by_provider_id[provider_id] = team.id
        return team.id
