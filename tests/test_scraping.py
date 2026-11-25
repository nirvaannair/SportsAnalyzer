from datetime import date

import pytest

from backend.core.leagues import LEAGUES_BY_CODE
from backend.scraping.espn_parse import (
    parse_minute,
    parse_scoreboard,
    parse_summary,
    scoreboard_url,
)
from backend.scraping.loaders import _on_off
from backend.scraping.pipeline import assert_no_betting_data
from backend.scraping.spiders.espn_matches import months_between

ENG2 = LEAGUES_BY_CODE["ENG2"]


@pytest.mark.parametrize(("text", "minute"), [("71'", 71), ("45'+2'", 47), ("90'+5'", 95), ("", None), (None, None)])
def test_parse_minute(text, minute) -> None:
    assert parse_minute(text) == minute


def test_months_between_and_url() -> None:
    assert list(months_between(date(2026, 11, 20), date(2027, 1, 3))) == ["202611", "202612", "202701"]
    assert scoreboard_url(ENG2, "202611").endswith("/soccer/eng.2/scoreboard?dates=202611&limit=1000")


def _team(team_id, name, score, side):
    return {"homeAway": side, "score": str(score), "team": {"id": team_id, "displayName": name}}


def test_parse_scoreboard() -> None:
    payload = {"events": [
        {"id": "1", "date": "2026-11-24T19:45Z", "status": {"type": {"completed": True, "name": "STATUS_FULL_TIME"}},
         "competitions": [{"competitors": [_team("333", "Bristol City", 1, "home"), _team("352", "Wrexham", 1, "away")]}]},
        {"id": "2", "competitions": [{"competitors": []}]},
    ]}
    (fixture,) = parse_scoreboard(payload, ENG2)
    assert fixture["date"] == "2026-11-24" and fixture["completed"]
    assert fixture["home"] == {"id": "333", "name": "Bristol City", "score": 1}


def test_parse_summary_keeps_football_and_drops_odds() -> None:
    payload = {
        "odds": [{"provider": "x", "homeTeamOdds": {"moneyLine": -110}}],
        "pickcenter": [{"spread": 1}],
        "rosters": [{"homeAway": "home", "team": {"id": "333", "displayName": "Bristol City"}, "roster": [
            {"athlete": {"id": "10", "displayName": "Starter Off"}, "starter": True, "subbedOut": True,
             "position": {"abbreviation": "M"}, "plays": [{"substitution": True, "clock": {"displayValue": "71'"}}],
             "stats": [{"name": "totalShots", "value": 2.0}]},
            {"athlete": {"id": "11", "displayName": "Sub On"}, "starter": False, "subbedIn": True,
             "plays": [{"substitution": True, "clock": {"displayValue": "71'"}}]},
            {"athlete": {"id": "12", "displayName": "Bench"}, "starter": False},
        ]}],
        "keyEvents": [
            {"type": {"text": "Goal"}, "clock": {"displayValue": "7'"}, "team": {"id": "333"},
             "participants": [{"athlete": {"id": "10"}}, {"athlete": {"id": "11"}}]},
            {"type": {"text": "Kickoff"}, "clock": {"displayValue": ""}},
            {"type": {"text": "Red Card"}, "clock": {"displayValue": "90'+3'"}, "team": {"id": "333"},
             "participants": [{"athlete": {"id": "11"}}]},
        ],
        "boxscore": {"teams": [{"team": {"id": "333"}, "statistics": [
            {"name": "possessionPct", "displayValue": "55.7"}, {"name": "weird", "displayValue": "n/a"}]}]},
    }
    detail = parse_summary(payload, "1", ENG2)
    assert_no_betting_data(detail)  # nothing from "odds"/"pickcenter" survives
    players = {p["name"]: p for p in detail["teams"][0]["players"]}
    assert players["Starter Off"]["minute_out"] == 71 and players["Sub On"]["minute_in"] == 71
    assert [e["kind"] for e in detail["events"]] == ["goal", "red"]
    assert detail["events"][0]["other_player_id"] == "11"
    assert detail["team_stats"][0]["stats"] == {"possessionPct": 55.7}


def test_betting_data_is_refused() -> None:
    with pytest.raises(ValueError):
        assert_no_betting_data({"teams": [{"players": []}], "pickcenter": {}})
    with pytest.raises(ValueError):
        assert_no_betting_data({"x": [{"homeTeamOdds": 1}]})
    assert_no_betting_data({"teams": [{"stats": {"goalsConceded": 1}}]})


def _p(**kw):
    base = {"starter": False, "subbed_in": False, "subbed_out": False, "minute_in": None, "minute_out": None,
            "red_card_minute": None}
    return {**base, **kw}


def test_on_pitch_minutes() -> None:
    assert _on_off(_p(starter=True), 94) == (0, 94)
    assert _on_off(_p(starter=True, subbed_out=True, minute_out=60), 94) == (0, 60)
    assert _on_off(_p(subbed_in=True, minute_in=60), 94) == (60, 94)
    assert _on_off(_p(subbed_in=True, minute_in=60, red_card_minute=80), 94) == (60, 80)
    assert _on_off(_p(), 94) == (None, None)  # unused substitute
