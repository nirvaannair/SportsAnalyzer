from datetime import date, timedelta

import pytest
from sqlalchemy import select

from backend.database.models import Competition, Match, ProviderEntityMapping, Season, Team
from backend.identity.team_resolver import (
    _fixture_votes,
    link_fixtures_to_matches,
    name_similarity,
    resolve_unresolved_teams,
)
from backend.ingestion.api_football_sync import parse_fixtures, team_evidence


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Manchester United", "Man United"),
        ("Atletico Madrid", "Ath Madrid"),
        ("1. FC Köln", "FC Koln"),
        ("AS Roma", "Roma"),
    ],
)
def test_name_similarity_handles_abbreviations(a: str, b: str) -> None:
    assert name_similarity(a, b) >= 0.6
    assert name_similarity(a, b) > name_similarity(a, "Fulham")


def test_exact_names_after_normalisation() -> None:
    assert name_similarity("Bayern München", "Bayern Munchen") == 1.0


def test_fixture_votes_tolerate_one_day_shift() -> None:
    index = {(date(2024, 8, 17), 2, 1): [(10, 20)], (date(2024, 8, 24), 0, 0): [(30, 10)]}
    evidence = [
        {"date": "2024-08-16", "is_home": True, "home_goals": 2, "away_goals": 1},  # a day early (UTC)
        {"date": "2024-08-24", "is_home": False, "home_goals": 0, "away_goals": 0},
        {"date": "2024-08-31", "is_home": True, "home_goals": None, "away_goals": None},  # not played
    ]
    votes, usable = _fixture_votes(evidence, index)
    assert usable == 2
    assert votes[10] == 2


def test_parse_fixtures_and_evidence() -> None:
    payload = {"response": [{
        "fixture": {"id": 1, "date": "2023-08-11T19:00:00+00:00", "status": {"short": "FT"}},
        "teams": {"home": {"id": 44, "name": "Burnley"}, "away": {"id": 50, "name": "Manchester City"}},
        "goals": {"home": 0, "away": 3},
    }, {"fixture": {"id": 2}}]}
    fixtures = parse_fixtures(payload)
    assert len(fixtures) == 1
    (ev,) = team_evidence(fixtures, "50")
    assert ev == {"fixture_id": "1", "date": "2023-08-11", "is_home": False, "home_goals": 0, "away_goals": 3}


@pytest.mark.db
async def test_resolves_by_results_and_links_fixtures(db_session) -> None:
    comp = Competition(code="TST1", name="Test League", country="Testland", tier=1)
    db_session.add(comp)
    await db_session.flush()
    season = Season(competition_id=comp.id, start_year=2023, label="2023/24")
    teams = [Team(name=n, country="Testland") for n in ("Man United", "Man City", "Fulham", "Leeds")]
    db_session.add_all([season, *teams])
    await db_session.flush()
    utd, city, fulham, leeds = teams

    # Man United's season: 6 results against varied opponents on distinct dates
    start = date(2023, 8, 12)
    schedule = [(utd, fulham, 1, 0), (city, utd, 2, 2), (utd, leeds, 3, 1),
                (fulham, utd, 0, 1), (utd, city, 0, 2), (leeds, utd, 1, 1)]
    for i, (home, away, hg, ag) in enumerate(schedule):
        db_session.add(Match(competition_id=comp.id, season_id=season.id, match_date=start + timedelta(days=7 * i),
                             home_team_id=home.id, away_team_id=away.id, status="finished",
                             home_goals=hg, away_goals=ag))
    await db_session.flush()

    # API-Football calls it "Manchester United", id 33
    fixtures = [{
        "fixture_id": str(100 + i), "date": (start + timedelta(days=7 * i)).isoformat(),
        "home_id": "33" if home is utd else f"9{i}", "away_id": "33" if away is utd else f"9{i}",
        "home_goals": hg, "away_goals": ag,
    } for i, (home, away, hg, ag) in enumerate(schedule)]
    db_session.add(ProviderEntityMapping(
        provider_name="api_football", entity_type="team", provider_entity_id="33",
        provider_label="Manchester United", status="unresolved",
        context={"country": "Testland", "fixtures": {"TST1:2023": team_evidence(fixtures, "33")}},
    ))
    # A team with no evidence and no exact name stays in review
    db_session.add(ProviderEntityMapping(
        provider_name="api_football", entity_type="team", provider_entity_id="999",
        provider_label="Unknown Rovers", status="unresolved", context={"country": "Testland", "fixtures": {}},
    ))
    await db_session.flush()

    summary = await resolve_unresolved_teams(db_session)
    assert summary == {"resolved": 1, "review": 1}

    mapping = (await db_session.execute(select(ProviderEntityMapping).where(
        ProviderEntityMapping.provider_entity_id == "33"))).scalar_one()
    assert (mapping.status, mapping.canonical_id, mapping.method) == ("active", utd.id, "composite_score")
    assert mapping.confidence == 1.0
    assert mapping.candidates[0]["name"] == "Man United"

    # fixtures only link when *both* teams are resolved; resolve Fulham by hand, then link
    db_session.add(ProviderEntityMapping(provider_name="api_football", entity_type="team",
                                         provider_entity_id="90", provider_label="Fulham",
                                         status="active", canonical_id=fulham.id))
    db_session.add(ProviderEntityMapping(provider_name="api_football", entity_type="match",
                                         provider_entity_id="100", provider_label="x",
                                         status="unresolved", context=fixtures[0]))
    await db_session.flush()
    assert await link_fixtures_to_matches(db_session) == 1
