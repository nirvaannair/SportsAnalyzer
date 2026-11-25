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

BET_MUTATION_HINT = re.compile(r"bet", re.I)


def is_bet_mutation(operation_name: str, kind: str) -> bool:
    return kind == "mutation" and bool(BET_MUTATION_HINT.search(operation_name))


class TemplateError(ValueError):
    pass


def build_bet_variables(sample: dict[str, Any], outcome_id: str, amount: float, currency: str) -> dict[str, Any]:
    """Replace the bet-specific fields in a captured variables object; keep everything else."""
    variables = copy.deepcopy(sample)
    replaced: set[str] = set()

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if _OUTCOME_LIST.search(key) and isinstance(value, list):
                    node[key] = [outcome_id]
                    replaced.add("outcome")
                elif _OUTCOME_ONE.search(key):
                    node[key] = outcome_id
                    replaced.add("outcome")
                elif _AMOUNT.search(key) and isinstance(value, int | float):
                    node[key] = amount
                    replaced.add("amount")
                elif _CURRENCY.search(key) and isinstance(value, str):
                    node[key] = currency
                    replaced.add("currency")
                elif _IDENTIFIER.search(key) and isinstance(value, str):
                    node[key] = uuid.uuid4().hex[:21]
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


def build_bet_request(operation_name: str, query: str, sample: dict[str, Any], outcome_id: str,
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
