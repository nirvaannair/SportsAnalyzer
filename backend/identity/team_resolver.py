"""Match other providers' teams to canonical teams.

Two kinds of evidence:

1. Fixture evidence (strong). A provider team that played on the same dates, at the
   same venue side, with the same scores as one canonical team *is* that team, however
   differently it is spelled ("Manchester United" vs "Man United", "Borussia
   Mönchengladbach" vs "M'gladbach").
2. Name similarity (weak). Used to rank candidates for manual review, and to decide
   alone only on an exact normalized-name match within the same country.

Anything not decided confidently stays `unresolved` and appears on the dashboard's
Identity review page.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import cfg
from backend.database.models import Competition, Match, ProviderEntityMapping, Team
from backend.identity.mappings import MappingStatus, ResolutionMethod
from backend.identity.normalization import EntityNameNormalizer

# Words that carry no identity in club names.
_normalizer = EntityNameNormalizer(
    remove_tokens=["fc", "cf", "afc", "sc", "ac", "ssc", "as", "us", "club", "calcio", "de", "the", "1"],
)



def normalize(name: str) -> str:
    try:
        return _normalizer.normalize(name).normalized
    except ValueError:
        return name.casefold().strip()


def name_similarity(a: str, b: str) -> float:
    """0..1. Combines character similarity with abbreviation-aware token overlap."""
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    ta, tb = na.split(), nb.split()
    # "man" matches "manchester", "ath" matches "athletic": count prefix hits
    hits = sum(1 for x in ta if any(y.startswith(x) or x.startswith(y) for y in tb))
    overlap = hits / max(len(ta), len(tb))
    return max(ratio, 0.5 * ratio + 0.5 * overlap)


@dataclass
class Candidate:
    team_id: int
    name: str
    fixture_score: float | None
    name_score: float

    def as_json(self) -> dict[str, Any]:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "fixture_score": None if self.fixture_score is None else round(self.fixture_score, 3),
            "name_score": round(self.name_score, 3),
        }


async def _canonical_matches(session: AsyncSession, country: str, dates: set[date]) -> dict:
    """{(date, home_goals, away_goals): [(home_team_id, away_team_id), ...]} for the dates needed."""
    window = {d + timedelta(days=k) for d in dates for k in (-1, 0, 1)}
    rows = await session.execute(
        select(Match.match_date, Match.home_goals, Match.away_goals, Match.home_team_id, Match.away_team_id)
        .join(Competition, Competition.id == Match.competition_id)
        .where(and_(Competition.country == country, Match.match_date.in_(window), Match.status == "finished"))
    )
    index: dict[tuple[date, int, int], list[tuple[int, int]]] = defaultdict(list)
    for d, hg, ag, home, away in rows:
        index[(d, hg, ag)].append((home, away))
    return index


def _fixture_votes(evidence: list[dict[str, Any]], index: dict) -> tuple[dict[int, int], int]:
    """Count, per canonical team, how many of the provider team's results it also has."""
    votes: dict[int, int] = defaultdict(int)
    usable = 0
    covered = {key[0] for key in index}  # dates for which we have finished results to compare with
    for f in evidence:
        if f.get("home_goals") is None or f.get("away_goals") is None:
            continue
        d = date.fromisoformat(f["date"])
        # Provider dates are UTC; the local (our) date is the same day or, for late kickoffs, the next.
        if not any(d + timedelta(days=k) in covered for k in (0, 1)):
            continue  # our results for that day aren't in yet: neither for nor against
        usable += 1
        seen: set[int] = set()
        for k in (0, -1, 1):  # kickoff dates can differ by a day across timezones
            for home, away in index.get((d + timedelta(days=k), f["home_goals"], f["away_goals"]), []):
                team = home if f["is_home"] else away
                if team not in seen:
                    seen.add(team)
                    votes[team] += 1
    return votes, usable


async def resolve_mapping(session: AsyncSession, mapping: ProviderEntityMapping,
                          teams_in_country: list[Team], taken: set[int]) -> bool:
    """Try to resolve one unresolved team mapping in place. Returns True if resolved."""
    evidence = [f for season in mapping.context.get("fixtures", {}).values() for f in season]
    dates = {date.fromisoformat(f["date"]) for f in evidence}
    index = await _canonical_matches(session, mapping.context.get("country", ""), dates) if dates else {}
    votes, usable = _fixture_votes(evidence, index)

    candidates = [
        Candidate(
            team_id=t.id,
            name=t.name,
            fixture_score=(votes.get(t.id, 0) / usable) if usable else None,
            name_score=name_similarity(mapping.provider_label, t.name),
        )
        for t in teams_in_country
    ]
    candidates.sort(key=lambda c: ((c.fixture_score or 0), c.name_score), reverse=True)
    mapping.candidates = [c.as_json() for c in candidates[:5]]

    best = candidates[0] if candidates else None
    runner_up = candidates[1] if len(candidates) > 1 else None
    decision: tuple[str, float] | None = None

    if best and usable >= cfg("identity.min_fixtures") and best.fixture_score is not None:
        second = (runner_up.fixture_score or 0) if runner_up else 0
        if best.fixture_score >= cfg("identity.auto_accept") and second <= cfg("identity.max_runner_up"):
            decision = (ResolutionMethod.COMPOSITE_SCORE.value, best.fixture_score)
    elif best and best.name_score == 1.0 and (not runner_up or runner_up.name_score < 0.9):
        decision = (ResolutionMethod.NAME_AND_CONTEXT.value, 0.97)
    elif best and usable >= 2 and best.fixture_score == 1.0:
        # Few results, but every one of them lines up with this team.
        second = (runner_up.fixture_score or 0) if runner_up else 0
        if usable >= 3 and second <= 0.34:
            decision = (ResolutionMethod.COMPOSITE_SCORE.value, 0.92)
        elif best.name_score >= 0.5 and second <= 0.5:
            decision = (ResolutionMethod.COMPOSITE_SCORE.value, 0.9)
    elif best and best.name_score >= 0.8 and (best.fixture_score is None or best.fixture_score >= 0.5):
        # Very close name ("Birmingham City" / "Birmingham"), clearly ahead, results don't disagree.
        by_name = sorted((c.name_score for c in candidates), reverse=True)
        if len(by_name) < 2 or by_name[1] <= best.name_score - 0.15:
            decision = (ResolutionMethod.NAME_AND_CONTEXT.value, 0.9)

    if decision is None or best is None or best.team_id in taken:
        mapping.status = MappingStatus.UNRESOLVED.value
        return False

    mapping.canonical_id = best.team_id
    mapping.status = MappingStatus.ACTIVE.value
    mapping.method, mapping.confidence = decision
    taken.add(best.team_id)
    return True


async def resolve_unresolved_teams(session: AsyncSession) -> dict[str, int]:
    """Run the resolver over every unresolved team mapping."""
    unresolved = list((await session.execute(
        select(ProviderEntityMapping).where(
            ProviderEntityMapping.entity_type == "team",
            ProviderEntityMapping.status == MappingStatus.UNRESOLVED.value,
        )
    )).scalars())

    teams_by_country: dict[str, list[Team]] = defaultdict(list)
    for team in (await session.execute(select(Team))).scalars():
        teams_by_country[team.country].append(team)

    # One provider team per canonical team, per provider.
    taken_rows = await session.execute(
        select(ProviderEntityMapping.provider_name, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.entity_type == "team",
            ProviderEntityMapping.status == MappingStatus.ACTIVE.value,
        )
    )
    taken: dict[str, set[int]] = defaultdict(set)
    for provider, canonical_id in taken_rows:
        taken[provider].add(canonical_id)

    resolved = 0
    for mapping in unresolved:
        country_teams = teams_by_country.get(mapping.context.get("country", ""), [])
        if await resolve_mapping(session, mapping, country_teams, taken[mapping.provider_name]):
            resolved += 1
    await session.flush()
    return {"resolved": resolved, "review": len(unresolved) - resolved}


async def link_fixtures_to_matches(session: AsyncSession, provider: str = "api_football") -> int:
    """Map a provider's fixtures to canonical matches once both teams are resolved."""
    team_map = dict((await session.execute(
        select(ProviderEntityMapping.provider_entity_id, ProviderEntityMapping.canonical_id).where(
            ProviderEntityMapping.provider_name == provider,
            ProviderEntityMapping.entity_type == "team",
            ProviderEntityMapping.status == MappingStatus.ACTIVE.value,
        )
    )).all())

    fixtures = list((await session.execute(
        select(ProviderEntityMapping).where(
            ProviderEntityMapping.provider_name == provider,
            ProviderEntityMapping.entity_type == "match",
            ProviderEntityMapping.status == MappingStatus.UNRESOLVED.value,
        )
    )).scalars())

    linked = 0
    for fixture in fixtures:
        home, away = team_map.get(fixture.context["home_id"]), team_map.get(fixture.context["away_id"])
        if home is None or away is None:
            continue
        d = date.fromisoformat(fixture.context["date"])
        match_id = (await session.execute(
            select(Match.id).where(
                Match.home_team_id == home, Match.away_team_id == away,
                Match.match_date.between(d - timedelta(days=1), d + timedelta(days=1)),
            )
        )).scalar_one_or_none()
        if match_id is not None:
            fixture.canonical_id = match_id
            fixture.status = MappingStatus.ACTIVE.value
            fixture.method = ResolutionMethod.DETERMINISTIC_RULE.value
            fixture.confidence = 1.0
            linked += 1
    await session.flush()
    return linked
