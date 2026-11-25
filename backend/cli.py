"""SportsAnalyzer command line.

    .venv/Scripts/python -m backend.cli import-fdcuk                 # all leagues, 2015/16 to now
    .venv/Scripts/python -m backend.cli import-fdcuk --from 2023 --leagues ENG1,ESP1
    .venv/Scripts/python -m backend.cli sync-api-football --season 2023
    .venv/Scripts/python -m backend.cli resolve-teams
    .venv/Scripts/python -m backend.cli summary
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from dotenv import load_dotenv
from sqlalchemy import func, select

from backend.core.config import ENV_FILE
from backend.core.leagues import LEAGUES, LEAGUES_BY_CODE
from backend.database.engine import AsyncSessionFactory, dispose_database_engine
from backend.database.models import Match, OddsQuote, ProviderEntityMapping, Team

# Provider adapters read API keys from os.environ, so expose .env to them.
load_dotenv(ENV_FILE)


def current_season_start(today: date | None = None) -> int:
    """European seasons start in July/August: Nov 2026 -> 2026, Mar 2027 -> 2026."""
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def _leagues(arg: str | None):
    if not arg:
        return LEAGUES
    try:
        return tuple(LEAGUES_BY_CODE[c.strip().upper()] for c in arg.split(","))
    except KeyError as exc:
        sys.exit(f"Unknown league {exc}. Choose from: {', '.join(LEAGUES_BY_CODE)}")


async def cmd_import_fdcuk(args: argparse.Namespace) -> None:
    from backend.ingestion.fdcuk import ImportResult, import_all

    seasons = range(args.from_season, (args.to_season or current_season_start()) + 1)
    leagues = _leagues(args.leagues)
    print(f"football-data.co.uk: {len(leagues)} leagues x {len(seasons)} seasons "
          f"({seasons[0]}/{(seasons[0] + 1) % 100:02d} to {seasons[-1]}/{(seasons[-1] + 1) % 100:02d})",
          flush=True)

    def report(r: ImportResult) -> None:
        extra = f"{r.matches:>4} matches {r.odds:>6} odds" if r.status == "imported" else r.detail
        print(f"  {r.league} {r.season}/{(r.season + 1) % 100:02d}  {r.status:<9} {extra}", flush=True)

    results = await import_all(AsyncSessionFactory, leagues, seasons, args.force, report)
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    print("Done:", ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())), flush=True)


async def cmd_sync_api_football(args: argparse.Namespace) -> None:
    from backend.ingestion.api_football_sync import sync_fixtures

    await sync_fixtures(AsyncSessionFactory, args.season, _leagues(args.leagues), print_fn=print)


async def cmd_resolve_teams(_: argparse.Namespace) -> None:
    from backend.identity.team_resolver import resolve_unresolved_teams

    async with AsyncSessionFactory() as session:
        summary = await resolve_unresolved_teams(session)
        await session.commit()
    print(f"Teams: {summary['resolved']} resolved automatically, {summary['review']} need review.")


async def cmd_summary(_: argparse.Namespace) -> None:
    async with AsyncSessionFactory() as session:
        teams = (await session.execute(select(func.count()).select_from(Team))).scalar_one()
        matches = (await session.execute(select(func.count()).select_from(Match))).scalar_one()
        odds = (await session.execute(select(func.count()).select_from(OddsQuote))).scalar_one()
        span = (await session.execute(select(func.min(Match.match_date), func.max(Match.match_date)))).one()
        mappings = (await session.execute(
            select(ProviderEntityMapping.provider_name, ProviderEntityMapping.status, func.count())
            .group_by(ProviderEntityMapping.provider_name, ProviderEntityMapping.status)
            .order_by(ProviderEntityMapping.provider_name)
        )).all()
    print(f"Teams {teams:,} | Matches {matches:,} ({span[0]} to {span[1]}) | Odds quotes {odds:,}")
    for provider, status, count in mappings:
        print(f"  {provider:<14} {status:<11} {count:,}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("import-fdcuk", help="Import results and odds from football-data.co.uk")
    p.add_argument("--from", dest="from_season", type=int, default=2015, help="first season start year")
    p.add_argument("--to", dest="to_season", type=int, help="last season start year (default: current)")
    p.add_argument("--leagues", help="comma-separated codes, e.g. ENG1,ESP1 (default: all)")
    p.add_argument("--force", action="store_true", help="re-parse files even if unchanged")
    p.set_defaults(func=cmd_import_fdcuk)

    p = sub.add_parser("sync-api-football", help="Fetch API-Football fixtures and match their team IDs")
    p.add_argument("--season", type=int, required=True, help="season start year, e.g. 2023")
    p.add_argument("--leagues", help="comma-separated codes (default: all)")
    p.set_defaults(func=cmd_sync_api_football)

    sub.add_parser("resolve-teams", help="Re-run team matching for unresolved provider teams") \
        .set_defaults(func=cmd_resolve_teams)
    sub.add_parser("summary", help="Show what is in the database").set_defaults(func=cmd_summary)

    args = parser.parse_args()

    async def run() -> None:
        try:
            await args.func(args)
        finally:
            await dispose_database_engine()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run())


if __name__ == "__main__":
    main()
