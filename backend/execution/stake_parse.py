"""Parse Stake sportsbook data (captured from the user's own Stake tab) into fixtures and outcomes.

Stake's football data comes from Betradar, so markets carry Betradar's standard market codes:
    1  = 1x2                 selections: home / draw / away
    18 = Total (Asian)       specifiers "total=2.5": over / under
    29 = Both Teams to Score selections: yes / no
Other markets are kept (for manual test bets) but get no normalised selection.

Prices are bet payouts only; prediction models never read them (README §5.0).
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

# (country, tournament name, lowercase) -> our league code
LEAGUE_BY_STAKE_NAME: dict[tuple[str, str], str] = {
    ("england", "premier league"): "ENG1",
    ("england", "championship"): "ENG2",
    ("spain", "laliga"): "ESP1",
    ("spain", "la liga"): "ESP1",
    ("spain", "laliga 2"): "ESP2",
    ("spain", "laliga hypermotion"): "ESP2",
    ("spain", "segunda division"): "ESP2",
    ("italy", "serie a"): "ITA1",
    ("italy", "serie b"): "ITA2",
    ("germany", "bundesliga"): "GER1",
    ("germany", "2. bundesliga"): "GER2",
    ("germany", "2nd bundesliga"): "GER2",
    ("france", "ligue 1"): "FRA1",
    ("france", "ligue 2"): "FRA2",
}

MARKET_1X2, MARKET_TOTAL, MARKET_BTTS = "1", "18", "29"


def league_code(country: str | None, tournament: str | None) -> str | None:
    if not country or not tournament:
        return None
    return LEAGUE_BY_STAKE_NAME.get((country.strip().lower(), tournament.strip().lower()))


def parse_start(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(UTC)  # "Sun, 29 Nov 2026 12:00:00 GMT"
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None


def _selection(code: str, name: str, index: int, home: str | None, away: str | None) -> str | None:
    lowered = (name or "").strip().lower()
    if code == MARKET_1X2:
        if lowered == "draw":
            return "draw"
        if home and lowered == home.lower():
            return "home"
        if away and lowered == away.lower():
            return "away"
        return ("home", "draw", "away")[index] if index < 3 else None
    if code == MARKET_TOTAL:
        return "over" if lowered.startswith("over") else "under" if lowered.startswith("under") else None
    if code == MARKET_BTTS:
        return "yes" if lowered == "yes" else "no" if lowered == "no" else None
    return None


def _markets(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for key in ("groups", "group"):
        for group in fixture.get(key) or []:
            for template in group.get("templates") or []:
                for market in template.get("markets") or []:
                    if market.get("id") and market.get("outcomes"):
                        seen[market["id"]] = market
    return list(seen.values())


def parse_payload(data: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """All football fixtures and their outcomes found anywhere in one GraphQL response."""
    fixtures: dict[str, dict[str, Any]] = {}
    outcomes: dict[str, dict[str, Any]] = {}

    def walk(node: Any, ctx: dict[str, str | None]) -> None:
        if isinstance(node, list):
            for value in node:
                walk(value, ctx)
            return
        if not isinstance(node, dict):
            return
        kind = node.get("__typename")
        if kind == "Sport":
            ctx = {**ctx, "sport": node.get("slug") or node.get("name")}
        elif kind == "SportCategory":
            ctx = {**ctx, "country": node.get("name")}
            walk(node.get("sport"), ctx)
        elif kind == "SportTournament":
            ctx = {**ctx, "tournament": node.get("name")}
            category = node.get("category") or {}
            ctx = {**ctx, "country": category.get("name") or ctx.get("country"),
                   "sport": ((category.get("sport") or {}).get("slug")) or ctx.get("sport")}

        if kind == "SportFixture" and node.get("id") and node.get("name"):
            tournament = node.get("tournament") or {}
            category = tournament.get("category") or {}
            sport = (category.get("sport") or {}).get("slug") or ctx.get("sport")
            country = category.get("name") or ctx.get("country")
            tournament_name = tournament.get("name") or ctx.get("tournament")
            data_block = node.get("data") or {}
            teams = {t.get("qualifier"): t.get("name") for t in data_block.get("teams") or []}
            home, away = teams.get("home"), teams.get("away")
            if not home or not away:
                competitors = data_block.get("competitors") or []
                if len(competitors) == 2:
                    home, away = competitors[0].get("name"), competitors[1].get("name")
            fixtures[node["id"]] = {
                "id": node["id"], "slug": node.get("slug"), "ext_id": node.get("extId"), "name": node["name"],
                "start_time": parse_start(data_block.get("startTime")), "home_name": home, "away_name": away,
                "tournament": tournament_name, "country": country, "sport": sport,
                "league_code": league_code(country, tournament_name) if sport in (None, "soccer") else None,
            }
            for market in _markets(node):
                code = str(market.get("extId") or "")
                for index, outcome in enumerate(market.get("outcomes") or []):
                    if not outcome.get("id") or not isinstance(outcome.get("odds"), int | float):
                        continue
                    outcomes[outcome["id"]] = {
                        "outcome_id": str(outcome["id"]), "stake_fixture_id": node["id"],
                        "market_code": code or None, "specifiers": market.get("specifiers") or None,
                        "selection": _selection(code, outcome.get("name") or "", index, home, away),
                        "fixture_name": node["name"], "market_name": market.get("name"),
                        "name": outcome.get("name") or "?", "price": float(outcome["odds"]),
                        "active": bool(outcome.get("active")) and market.get("status") == "active",
                    }
        for key, value in node.items():
            if key not in ("tournament",):
                walk(value, ctx)
        if kind != "SportFixture":
            walk(node.get("tournament"), ctx)

    walk(data, {"sport": None, "country": None, "tournament": None})
    return list(fixtures.values()), list(outcomes.values())
