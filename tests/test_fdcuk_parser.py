from datetime import UTC, date, datetime
from decimal import Decimal

from backend.cli import current_season_start
from backend.core.leagues import LEAGUES_BY_CODE, season_label
from backend.ingestion.fdcuk import csv_url, decode_csv, parse_csv, season_code

EPL = LEAGUES_BY_CODE["ENG1"]

MODERN = (
    "﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HS,AS,"
    "PSH,PSD,PSA,PSCH,PSCD,PSCA,AvgH,AvgD,AvgA,P>2.5,P<2.5\n"
    "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,0,0,14,10,1.63,4.38,5.3,1.65,4.23,5.28,1.62,4.36,5.15,1.56,2.56\n"
    "E0,14/12/2024,15:00,Arsenal,Everton,0,0,D,0,0,20,3,1.2,7.5,15,,,,1.21,7.1,14,abc,1.0\n"
)

OLD = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,BbAvH,BbAvD,BbAvA\n"
    "E0,08/08/15,Bournemouth,Aston Villa,0,1,1.9,3.5,4.4\n"
    ",,,,,,,,\n"
)


def test_season_codes() -> None:
    assert season_code(2024) == "2425"
    assert season_code(1999) == "9900"
    assert season_label(2026) == "2026/27"
    assert csv_url(EPL, 2024).endswith("/mmz4281/2425/E0.csv")


def test_current_season_start() -> None:
    assert current_season_start(date(2026, 11, 25)) == 2026
    assert current_season_start(date(2027, 3, 1)) == 2026
    assert current_season_start(date(2027, 7, 1)) == 2027


def test_decode_handles_bom_and_windows_1252() -> None:
    assert decode_csv("﻿Div".encode()) == "Div"
    assert decode_csv("Div,M\xfcnchen".encode("cp1252")) == "Div,München"


def test_parses_results_stats_and_kickoff_time() -> None:
    first, second = parse_csv(decode_csv(MODERN.encode()), EPL)
    assert (first.home_team, first.away_team, first.home_goals, first.away_goals) == ("Man United", "Fulham", 1, 0)
    assert first.match_date == date(2024, 8, 16)
    # 20:00 UK summer time is 19:00 UTC; 15:00 UK winter time is 15:00 UTC
    assert first.kickoff_at == datetime(2024, 8, 16, 19, 0, tzinfo=UTC)
    assert second.kickoff_at == datetime(2024, 12, 14, 15, 0, tzinfo=UTC)
    assert first.stats["HS"] == 14


def test_odds_opening_closing_and_invalid_prices() -> None:
    first, second = parse_csv(MODERN, EPL)
    by_key = {(o.bookmaker, o.market, o.selection, o.is_closing): o.price for o in first.odds}
    assert by_key[("pinnacle", "1x2", "home", False)] == Decimal("1.63")
    assert by_key[("pinnacle", "1x2", "home", True)] == Decimal("1.65")
    assert by_key[("pinnacle", "ou25", "over", False)] == Decimal("1.56")
    # second row: no closing prices, "abc" and 1.0 are not valid decimal odds
    assert not any(o.is_closing for o in second.odds)
    assert not any(o.market == "ou25" for o in second.odds)


def test_old_format_uses_fallback_columns_and_skips_blank_rows() -> None:
    (match,) = parse_csv(OLD, EPL)
    assert match.match_date == date(2015, 8, 8)
    assert match.kickoff_at is None
    assert {(o.bookmaker, o.selection) for o in match.odds} == {("avg", "home"), ("avg", "draw"), ("avg", "away")}
