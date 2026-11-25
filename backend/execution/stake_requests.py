"""Build Stake GraphQL requests from operations the helper learned in the user's own browser.

Stake has no public betting API, so the exact request shapes are learned ("captured") when
the user places one bet by hand with Learn mode on. Only the request body is captured,
never headers or tokens. To place a new bet we reuse that body and swap in the new outcome,
amount, currency and a fresh idempotency identifier.
"""

from __future__ import annotations

import copy
import re
import uuid
from typing import Any

_AMOUNT = re.compile(r"^amount$|stake|betAmount", re.I)
_CURRENCY = re.compile(r"^currency$", re.I)
_OUTCOME_LIST = re.compile(r"^outcomeIds$", re.I)
_OUTCOME_ONE = re.compile(r"^outcomeId$", re.I)
_IDENTIFIER = re.compile(r"^identifier$|idempotency", re.I)
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

BET_MUTATION_HINT = re.compile(r"bet", re.I)
_OPERATION = re.compile(r"^\s*(query|mutation|subscription)(?![A-Za-z0-9_])\s*([A-Za-z_][A-Za-z0-9_]*)?")
_FIRST_FIELD = re.compile(r"\{\s*([A-Za-z_][A-Za-z0-9_]*)")


def describe_operation(operation_name: str | None, query: str) -> tuple[str, str] | None:
    """(name, kind) for a GraphQL request, even when the client sent no operationName.

    Falls back to the name inside the query text ("mutation SportBet(...)"), then to the
    first field it selects ("mutation { sportBet(...) }" -> "sportBet").
    """
    match = _OPERATION.match(query or "")
    if match:
        kind = match.group(1)
        name = operation_name or match.group(2)
    elif (query or "").lstrip().startswith("{"):
        kind, name = "query", operation_name  # shorthand query
    else:
        return None
    if not name:
        field = _FIRST_FIELD.search(query or "")
        name = field.group(1) if field else None
    return (name, kind) if name else None


def is_bet_mutation(operation_name: str, kind: str) -> bool:
    return kind == "mutation" and bool(BET_MUTATION_HINT.search(operation_name))


class TemplateError(ValueError):
    pass


def build_bet_variables(sample: dict[str, Any], outcome_id: str | list[str], amount: float,
                        currency: str) -> dict[str, Any]:
    """Replace the bet-specific fields in a captured variables object; keep everything else.

    `outcome_id` may be a list (a multi bet: every leg must win).
    """
    outcome_ids = list(outcome_id) if isinstance(outcome_id, list | tuple) else [outcome_id]
    variables = copy.deepcopy(sample)
    replaced: set[str] = set()

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if _OUTCOME_LIST.search(key) and isinstance(value, list):
                    node[key] = outcome_ids
                    replaced.add("outcome")
                elif _OUTCOME_ONE.search(key):
                    if len(outcome_ids) > 1:
                        raise TemplateError("This bet request takes one outcome; learn a multi bet first.")
                    node[key] = outcome_ids[0]
                    replaced.add("outcome")
                elif _AMOUNT.search(key) and isinstance(value, int | float):
                    node[key] = amount
                    replaced.add("amount")
                elif _CURRENCY.search(key) and isinstance(value, str):
                    node[key] = currency
                    replaced.add("currency")
                elif _IDENTIFIER.search(key) and isinstance(value, str) and value:
                    # A fresh one-time key in the same format Stake used (UUID or short code).
                    node[key] = str(uuid.uuid4()) if _UUID.match(value) else uuid.uuid4().hex[:max(len(value), 8)]
                else:
                    node[key] = walk(value)
        elif isinstance(node, list):
            return [walk(v) for v in node]
        return node

    walk(variables)
    missing = {"outcome", "amount", "currency"} - replaced
    if missing:
        raise TemplateError(
            f"The learned bet request has no recognisable {', '.join(sorted(missing))} field; "
            "place one manual bet with Learn mode on so it can be captured again.")
    return variables


def build_bet_request(operation_name: str, query: str, sample: dict[str, Any], outcome_id: str | list[str],
                      amount: float, currency: str) -> dict[str, Any]:
    return {"operationName": operation_name, "query": query,
            "variables": build_bet_variables(sample, outcome_id, amount, currency)}


def extract_outcomes(payload: Any) -> list[dict[str, Any]]:
    """Find selectable outcomes (id + name + odds) anywhere in a Stake GraphQL response.

    Stake's schema is not published, so this looks for the general shape: an object with an
    id, a name and a numeric `odds`, inside a market (named, with a list of outcomes),
    inside a fixture/event (named).
    """
    found: list[dict[str, Any]] = []

    def walk(node: Any, fixture: str | None, market: str | None) -> None:
        if isinstance(node, dict):
            name = node.get("name") if isinstance(node.get("name"), str) else None
            has_outcomes = isinstance(node.get("outcomes"), list)
            if name and isinstance(node.get("markets") or node.get("groups"), list):
                fixture = name
            if name and has_outcomes:
                market = name
            odds = node.get("odds")
            if node.get("id") and name and isinstance(odds, int | float) and not has_outcomes:
                found.append({"outcome_id": str(node["id"]), "name": name, "price": float(odds),
                              "active": node.get("active"), "market_name": market, "fixture_name": fixture})
            for value in node.values():
                walk(value, fixture, market)
        elif isinstance(node, list):
            for value in node:
                walk(value, fixture, market)

    walk(payload, None, None)
    return found


def bet_result(response: dict[str, Any]) -> tuple[bool, str | None, str]:
    """(placed?, stake bet id, message) from a Stake bet mutation response."""
    if not isinstance(response, dict):
        return False, None, "No response from Stake"
    errors = response.get("errors")
    if errors:
        return False, None, "; ".join(str(e.get("message")) for e in errors if isinstance(e, dict))
    data = response.get("data") or {}
    for value in data.values():
        if isinstance(value, dict) and value.get("id"):
            return True, str(value["id"]), "Placed"
    return False, None, "Stake did not return a bet id"


# ----------------------------------------------------------------------------- multis and cash-out

MULTI_SUFFIX = "#multi"


def template_name(operation_name: str, kind: str, variables: dict[str, Any]) -> str:
    """Store multi-bet captures separately from single-bet captures of the same mutation."""
    ids = variables.get("outcomeIds") if isinstance(variables, dict) else None
    if is_bet_mutation(operation_name, kind) and isinstance(ids, list) and len(ids) > 1:
        return operation_name + MULTI_SUFFIX
    return operation_name


def is_cashout_mutation(operation_name: str, kind: str) -> bool:
    return kind == "mutation" and "cashout" in operation_name.lower()


_BET_ID = re.compile(r"^betId$|^id$|^iid$", re.I)
_MULTIPLIER = re.compile(r"multiplier", re.I)


def build_cashout_variables(sample: dict[str, Any], bet_id: str, multiplier: float | None) -> dict[str, Any]:
    variables = copy.deepcopy(sample)
    found = False
    for key, value in list(variables.items()):
        if _BET_ID.search(key) and isinstance(value, str):
            variables[key] = bet_id
            found = True
        elif _MULTIPLIER.search(key) and isinstance(value, int | float) and multiplier is not None:
            variables[key] = multiplier
    if not found:
        raise TemplateError("The learned cash-out request has no bet id field; cash out one bet by hand "
                            "with Learn mode on.")
    return variables


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_sport_bets(payload: Any) -> list[dict[str, Any]]:
    """The OWNER's sports bets (singles and multis) from a Stake "My Bets" response.

    Only bets inside a `user { ... }` object count. Stake pages also show other people's bets
    (e.g. the public high-roller board); those never sit under `user` and are ignored.
    """
    bets: dict[str, dict[str, Any]] = {}

    def describe(node: dict[str, Any]) -> str:
        parts = []
        for leg in node.get("outcomes") or []:
            if not isinstance(leg, dict):
                continue
            outcome = leg.get("outcome") if isinstance(leg.get("outcome"), dict) else leg
            fixture = leg.get("fixture") if isinstance(leg.get("fixture"), dict) else {}
            name = outcome.get("name") if isinstance(outcome, dict) else None
            parts.append(" · ".join(p for p in (fixture.get("name"), name) if p))
        return " + ".join(p for p in parts if p)[:500]

    def walk(node: Any, own: bool = False) -> None:
        if isinstance(node, list):
            for value in node:
                walk(value, own)
            return
        if not isinstance(node, dict):
            return
        kind = str(node.get("__typename") or "")
        if own and kind in ("SportBet", "SwishBet") and node.get("id"):
            bets[str(node["id"])] = {
                "id": str(node["id"]), "status": node.get("status"), "active": node.get("active"),
                "amount": _num(node.get("amount")), "currency": node.get("currency"),
                "potential_multiplier": _num(node.get("potentialMultiplier") or node.get("payoutMultiplier")),
                "payout": _num(node.get("payout")),
                "cashout_multiplier": _num(node.get("cashoutMultiplier")),
                "cashout_disabled": node.get("cashoutDisabled"),
                "description": describe(node) or None,
                "placed_at": node.get("createdAt"),
                "raw": node,
            }
            return
        for key, value in node.items():
            walk(value, own or (key == "user" and isinstance(value, dict)))

    walk(payload)
    return list(bets.values())


# Stake computes the live cash-out value in the browser from streamed odds and its cash-out
# settings; no server request returns it. This per-leg factor reproduces the values Stake's
# page showed for the owner's two multis on 2026-11-25 (0.83 and 0.91): value ~= potential
# multiplier / product(current odds of unsettled legs) x 0.9617^legs. It is an ESTIMATE only
# and is never used to execute a cash-out.
CASHOUT_LEG_FACTOR = 0.9617


def cashout_view(raw: dict[str, Any]) -> dict[str, Any]:
    """Availability (exactly Stake's rule) and an estimated cash-out multiplier for one own bet."""
    legs = []
    for leg in raw.get("outcomes") or []:
        market = leg.get("market") or {}
        outcome = leg.get("outcome") or {}
        fixture = leg.get("fixture") or {}
        legs.append({
            "fixture": fixture.get("name"),
            "selection": outcome.get("name"),
            "market": market.get("name"),
            "odds_at_bet": _num(leg.get("odds")),
            "current_odds": _num(outcome.get("odds")),
            "status": leg.get("status"),
            "open": (market.get("status") == "active" and bool(outcome.get("active"))
                     and fixture.get("cashoutEnabled", True) is not False),
        })
    pending = [leg for leg in legs if (leg["status"] or "pending") == "pending"]
    reason = None
    if raw.get("cashoutDisabled"):
        reason = "Stake has disabled cash-out on this bet"
    elif not pending:
        reason = "All legs settled"
    elif any(not leg["open"] for leg in pending):
        reason = "A market is suspended (often during live play)"
    estimate = None
    potential = _num(raw.get("potentialMultiplier"))
    if reason is None and potential and all(leg["current_odds"] for leg in pending):
        product = 1.0
        for leg in pending:
            product *= leg["current_odds"]
        estimate = round(potential / product * CASHOUT_LEG_FACTOR ** len(pending), 4)
    return {"available": reason is None, "reason": reason, "estimate_multiplier": estimate, "legs": legs}
