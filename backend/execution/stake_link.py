"""Save parsed Stake fixtures/outcomes and link Stake fixtures to our canonical matches."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.database.models import (
    Competition,
    Match,
    RawProviderObservation,
    StakeFixture,
    StakeOutcome,
    Team,
)
from backend.execution.stake_parse import parse_payload
from backend.identity.team_resolver import name_similarity

MIN_TEAM_SIMILARITY = 0.45
MIN_MARGIN = 0.15  # candidates are already limited to the same competition and date ±1


async def store_parsed(session: AsyncSession, fixtures: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> None:
    for f in fixtures:
        statement = insert(StakeFixture).values(**f)
        await session.execute(statement.on_conflict_do_update(
            index_elements=["id"],
            set_={k: statement.excluded[k] for k in f if k != "id"} | {"seen_at": statement.excluded.seen_at},
        ))
    for start in range(0, len(outcomes), 1000):
        chunk = outcomes[start:start + 1000]
        if not chunk:
            continue
        statement = insert(StakeOutcome).values(chunk)
        await session.execute(statement.on_conflict_do_update(
            index_elements=["outcome_id"],
            set_={k: statement.excluded[k] for k in chunk[0] if k != "outcome_id"} | {"seen_at": statement.excluded.seen_at},
        ))


async def link_stake_fixtures(session: AsyncSession) -> dict[str, int]:
    """Match each unlinked Stake fixture in a tracked league to our match on the same date."""
    pending = (await session.execute(select(StakeFixture).where(
        StakeFixture.league_code.is_not(None), StakeFixture.match_id.is_(None),
        StakeFixture.start_time.is_not(None)))).scalars().all()
    home, away = aliased(Team), aliased(Team)
    linked = 0
    for fixture in pending:
        day = fixture.start_time.date()
        candidates = (await session.execute(
            select(Match.id, home.name, away.name)
            .join(Competition, Competition.id == Match.competition_id)
            .join(home, home.id == Match.home_team_id).join(away, away.id == Match.away_team_id)
            .where(Competition.code == fixture.league_code,
                   Match.match_date.between(day - timedelta(days=1), day + timedelta(days=1)))
        )).all()
        scored = sorted(
            ((min(name_similarity(fixture.home_name or "", h), name_similarity(fixture.away_name or "", a)),
              match_id, h, a) for match_id, h, a in candidates),
            reverse=True)
        if not scored:
            fixture.link_detail = "No match of ours on that date yet"
            continue
        best = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if best[0] >= MIN_TEAM_SIMILARITY and best[0] - runner_up >= MIN_MARGIN:
            fixture.match_id = best[1]
            fixture.link_detail = f"Linked to {best[2]} v {best[3]} (name match {best[0]:.2f})"
            linked += 1
        else:
            fixture.link_detail = f"Unsure: best {best[2]} v {best[3]} ({best[0]:.2f})"
    await session.flush()
    return {"linked": linked, "unlinked": len(pending) - linked}


async def reparse_raw(session: AsyncSession) -> dict[str, int]:
    """Re-read every stored Stake response (raw first: no re-capturing needed)."""
    rows = (await session.execute(select(RawProviderObservation.payload).where(
        RawProviderObservation.provider_name == "stake"))).scalars().all()
    fixtures: dict[str, dict[str, Any]] = {}
    outcomes: dict[str, dict[str, Any]] = {}
    for payload in rows:
        data = json.loads(payload) if isinstance(payload, str) else payload
        f, o = parse_payload(data)
        fixtures.update({x["id"]: x for x in f})
        outcomes.update({x["outcome_id"]: x for x in o})
    await store_parsed(session, list(fixtures.values()), list(outcomes.values()))
    result = await link_stake_fixtures(session)
    return {"fixtures": len(fixtures), "outcomes": len(outcomes), **result}
