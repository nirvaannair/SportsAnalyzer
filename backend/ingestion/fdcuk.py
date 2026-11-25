"""football-data.co.uk importer: historical results, match stats and bookmaker odds.

Free, no API key. One CSV per league per season, e.g.
https://www.football-data.co.uk/mmz4281/2425/E0.csv  (2024/25 Premier League)

This is SportsAnalyzer's *seed* source: it defines the canonical teams and
matches, and its closing odds are what models are judged against.
"""

from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.leagues import LEAGUES, League
from backend.database.models import Match, OddsQuote
from backend.ingestion.catalog import TeamDirectory, ensure_competitions, ensure_season
from backend.integrations.base import ProviderRequestContext
from backend.integrations.postgres_raw_repository import PostgresRawPayloadRepository
from backend.integrations.raw import RawPayload

PROVIDER = "fdcuk"
BASE_URL = "https://www.football-data.co.uk/mmz4281"
USER_AGENT = "SportsAnalyzer/0.1 (personal research tool)"
REQUEST_GAP_SECONDS = 1.5  # be polite: one small file every 1.5 s

STAT_COLUMNS = ("Referee", "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR")

# (bookmaker, market, selection, opening columns, closing columns).
# Older seasons used different column names, so each entry lists fallbacks in order.
ODDS_COLUMNS: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("pinnacle", "1x2", "home", ("PSH",), ("PSCH",)),
    ("pinnacle", "1x2", "draw", ("PSD",), ("PSCD",)),
    ("pinnacle", "1x2", "away", ("PSA",), ("PSCA",)),
    ("bet365", "1x2", "home", ("B365H",), ("B365CH",)),
    ("bet365", "1x2", "draw", ("B365D",), ("B365CD",)),
    ("bet365", "1x2", "away", ("B365A",), ("B365CA",)),
    ("avg", "1x2", "home", ("AvgH", "BbAvH"), ("AvgCH",)),
    ("avg", "1x2", "draw", ("AvgD", "BbAvD"), ("AvgCD",)),
    ("avg", "1x2", "away", ("AvgA", "BbAvA"), ("AvgCA",)),
    ("max", "1x2", "home", ("MaxH", "BbMxH"), ("MaxCH",)),
    ("max", "1x2", "draw", ("MaxD", "BbMxD"), ("MaxCD",)),
    ("max", "1x2", "away", ("MaxA", "BbMxA"), ("MaxCA",)),
    ("pinnacle", "ou25", "over", ("P>2.5",), ("PC>2.5",)),
    ("pinnacle", "ou25", "under", ("P<2.5",), ("PC<2.5",)),
    ("bet365", "ou25", "over", ("B365>2.5",), ("B365C>2.5",)),
    ("bet365", "ou25", "under", ("B365<2.5",), ("B365C<2.5",)),
    ("avg", "ou25", "over", ("Avg>2.5", "BbAv>2.5"), ("AvgC>2.5",)),
    ("avg", "ou25", "under", ("Avg<2.5", "BbAv<2.5"), ("AvgC<2.5",)),
)


@dataclass(frozen=True, slots=True)
class ParsedOdds:
    bookmaker: str
    market: str
    selection: str
    price: Decimal
    is_closing: bool


@dataclass(frozen=True, slots=True)
class ParsedMatch:
    match_date: date
    kickoff_at: datetime | None
    home_team: str
    away_team: str
    home_goals: int | None
    away_goals: int | None
    ht_home_goals: int | None
    ht_away_goals: int | None
    stats: dict[str, str | int]
    odds: tuple[ParsedOdds, ...] = field(default=())


def season_code(start_year: int) -> str:
    """2024 -> '2425'."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def csv_url(league: League, start_year: int) -> str:
    return f"{BASE_URL}/{season_code(start_year)}/{league.fdcuk_division}.csv"


def decode_csv(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252")  # older files are Windows-1252


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def _price(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        price = Decimal(value.strip())
    except InvalidOperation:
        return None
    return price if price > 1 else None  # decimal odds are always > 1


def _first(row: dict[str, str], columns: Iterable[str]) -> str | None:
    for column in columns:
        value = row.get(column)
        if value not in (None, ""):
            return value
    return None


def _parse_date(value: str) -> date:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {value!r}")


def parse_csv(text: str, league: League) -> list[ParsedMatch]:
    """Parse one football-data.co.uk CSV. Rows without teams or a date are skipped."""
    tz = ZoneInfo(league.timezone)
    matches: list[ParsedMatch] = []

    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        home, away, raw_date = row.get("HomeTeam"), row.get("AwayTeam"), row.get("Date")
        if not home or not away or not raw_date:
            continue

        match_date = _parse_date(raw_date)
        kickoff_at = None
        if row.get("Time"):
            try:
                local = datetime.strptime(f"{match_date} {row['Time']}", "%Y-%m-%d %H:%M")
                kickoff_at = local.replace(tzinfo=tz).astimezone(UTC)
            except ValueError:
                pass

        odds: list[ParsedOdds] = []
        for bookmaker, market, selection, opening, closing in ODDS_COLUMNS:
            for is_closing, columns in ((False, opening), (True, closing)):
                price = _price(_first(row, columns))
                if price is not None:
                    odds.append(ParsedOdds(bookmaker, market, selection, price, is_closing))

        stats: dict[str, str | int] = {}
        for column in STAT_COLUMNS:
            value = row.get(column)
            if value:
                stats[column] = value if column == "Referee" else (_int(value) or 0)

        matches.append(
            ParsedMatch(
                match_date=match_date,
                kickoff_at=kickoff_at,
                home_team=home,
                away_team=away,
                home_goals=_int(row.get("FTHG")),
                away_goals=_int(row.get("FTAG")),
                ht_home_goals=_int(row.get("HTHG")),
                ht_away_goals=_int(row.get("HTAG")),
                stats=stats,
                odds=tuple(odds),
            )
        )
    return matches


def team_provider_id(league: League, name: str) -> str:
    """football-data.co.uk has no team IDs; a name is unique within a country."""
    return f"{league.country}:{name}"


@dataclass
class ImportResult:
    league: str
    season: int
    status: str  # imported | unchanged | missing | failed
    matches: int = 0
    odds: int = 0
    detail: str = ""


async def _upsert(session: AsyncSession, competition_id: int, season_id: int, league: League,
                  parsed: list[ParsedMatch], teams: TeamDirectory) -> tuple[int, int]:
    match_rows = []
    for m in parsed:
        home_id = await teams.seed_team(session, team_provider_id(league, m.home_team), m.home_team, league)
        away_id = await teams.seed_team(session, team_provider_id(league, m.away_team), m.away_team, league)
        finished = m.home_goals is not None and m.away_goals is not None
        match_rows.append({
            "competition_id": competition_id,
            "season_id": season_id,
            "match_date": m.match_date,
            "kickoff_at": m.kickoff_at,
            "home_team_id": home_id,
            "away_team_id": away_id,
            "status": "finished" if finished else "scheduled",
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
            "ht_home_goals": m.ht_home_goals,
            "ht_away_goals": m.ht_away_goals,
            "stats": m.stats,
        })
    if not match_rows:
        return 0, 0

    statement = insert(Match).values(match_rows)
    statement = statement.on_conflict_do_update(
        constraint="uq_matches_teams_date",
        set_={c: statement.excluded[c] for c in (
            "kickoff_at", "status", "home_goals", "away_goals", "ht_home_goals", "ht_away_goals", "stats",
        )},
    ).returning(Match.id, Match.home_team_id, Match.away_team_id, Match.match_date)
    ids = {(h, a, d): mid for mid, h, a, d in (await session.execute(statement))}

    odds_rows = []
    for m, row in zip(parsed, match_rows, strict=True):
        match_id = ids[(row["home_team_id"], row["away_team_id"], m.match_date)]
        odds_rows.extend(
            {
                "match_id": match_id, "source": PROVIDER, "bookmaker": o.bookmaker, "market": o.market,
                "selection": o.selection, "price": o.price, "is_closing": o.is_closing,
            }
            for o in m.odds
        )

    for start in range(0, len(odds_rows), 3000):  # stay under Postgres' parameter limit
        chunk = insert(OddsQuote).values(odds_rows[start:start + 3000])
        await session.execute(
            chunk.on_conflict_do_update(constraint="uq_odds_quotes_identity", set_={"price": chunk.excluded.price})
        )
    return len(match_rows), len(odds_rows)


async def import_season(session: AsyncSession, client: httpx.AsyncClient, league: League,
                        start_year: int, competition_ids: dict[str, int], teams: TeamDirectory,
                        force: bool = False) -> ImportResult:
    url = csv_url(league, start_year)
    requested_at = datetime.now(UTC)
    response = await client.get(url)
    if response.status_code == 404:
        return ImportResult(league.code, start_year, "missing", detail="not published")
    response.raise_for_status()

    text = decode_csv(response.content)
    raw = RawPayload.from_request_context(
        ProviderRequestContext(
            provider_name=PROVIDER,
            endpoint=f"mmz4281/{season_code(start_year)}/{league.fdcuk_division}.csv",
            requested_at=requested_at,
            request_id=str(uuid4()),
            parameters={"league": league.code, "season": start_year},
        ),
        text,
        response_headers={k: v for k, v in response.headers.items() if k.lower() in ("last-modified", "etag")},
    )
    _, is_new = await PostgresRawPayloadRepository(session).store_if_new(raw)
    if not is_new and not force:
        return ImportResult(league.code, start_year, "unchanged")

    parsed = parse_csv(text, league)
    competition_id = competition_ids[league.code]
    season_id = await ensure_season(session, competition_id, start_year)
    n_matches, n_odds = await _upsert(session, competition_id, season_id, league, parsed, teams)
    return ImportResult(league.code, start_year, "imported", n_matches, n_odds)


async def import_all(session_factory: Callable[[], AsyncSession], leagues: Iterable[League] = LEAGUES,
                     seasons: Iterable[int] = (), force: bool = False,
                     on_result: Callable[[ImportResult], None] = lambda _: None) -> list[ImportResult]:
    """Import every (league, season) pair, committing after each file."""
    results: list[ImportResult] = []
    async with session_factory() as session:
        competition_ids = await ensure_competitions(session)
        teams = TeamDirectory(PROVIDER)
        await teams.load(session)
        await session.commit()

        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                                     timeout=30) as client:
            for league in leagues:
                for start_year in seasons:
                    try:
                        result = await import_season(session, client, league, start_year,
                                                     competition_ids, teams, force)
                        await session.commit()
                    except Exception as exc:  # one bad file must not stop the run
                        await session.rollback()
                        await teams.load(session)  # drop cached ids from the rolled-back transaction
                        result = ImportResult(league.code, start_year, "failed", detail=f"{type(exc).__name__}: {exc}")
                    results.append(result)
                    on_result(result)
                    await asyncio.sleep(REQUEST_GAP_SECONDS)
    return results
