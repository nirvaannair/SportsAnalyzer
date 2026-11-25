"""Stake execution: dashboard controls + endpoints for the SportsAnalyzer browser helper.

Flow for one bet:
  dashboard creates order (pending_approval) -> user clicks Approve (approved)
  -> helper asks /helper/next; guardrails re-checked; order handed over (sent)
  -> helper posts Stake's answer to /helper/orders/{id}/result (placed | failed)

Nothing here can place a bet by itself: the helper only runs in the user's own browser,
only while execution is switched on, and only for orders the user approved.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import AsyncSessionFactory
from backend.database.models import (
    AppSetting,
    StakeBet,
    StakeFixture,
    StakeOperation,
    StakeOrder,
    StakeOutcome,
    StrategyBet,
)
from backend.execution.guardrails import (
    Exposure,
    GuardrailError,
    Limits,
    check_dispatch,
)
from backend.execution.orders import (
    bet_operation,
    cashout_operation,
    create_cashout_order,
    create_stake_order,
)
from backend.execution.stake_link import link_stake_fixtures, store_parsed
from backend.execution.stake_parse import parse_payload, parse_start
from backend.execution.stake_requests import (
    MULTI_SUFFIX,
    TemplateError,
    bet_result,
    build_bet_request,
    cashout_view,
    describe_operation,
    is_bet_mutation,
    parse_sport_bets,
    template_name,
)
from backend.integrations.base import ProviderRequestContext
from backend.integrations.postgres_raw_repository import PostgresRawPayloadRepository
from backend.integrations.raw import RawPayload

router = APIRouter(prefix="/api/stake")

HELPER_STALE_SECONDS = 30
SENT_TIMEOUT = timedelta(minutes=2)
_SECRET_KEYS = ("token", "authorization", "cookie", "password", "session")


# ----------------------------------------------------------------------------- helpers

async def _get(session: AsyncSession, key: str, default: Any = None) -> Any:
    row = await session.get(AppSetting, key)
    return default if row is None else row.value


async def _put(session: AsyncSession, key: str, value: Any) -> None:
    statement = insert(AppSetting).values(key=key, value=value)
    await session.execute(statement.on_conflict_do_update(
        index_elements=["key"], set_={"value": statement.excluded.value, "updated_at": func.now()}))


def _scrub(node: Any) -> Any:
    """Drop anything secret-looking from data the helper sends (defence in depth)."""
    if isinstance(node, dict):
        return {k: _scrub(v) for k, v in node.items() if not any(s in k.lower() for s in _SECRET_KEYS)}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    return node


async def _exposure(session: AsyncSession) -> Exposure:
    """Every order ever handed to Stake counts, whatever its result: if unsure, assume it was spent."""
    spent = (await session.execute(select(func.coalesce(func.sum(StakeOrder.amount), 0.0))
                                   .where(StakeOrder.sent_at.is_not(None)))).scalar_one()
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    bets_today = (await session.execute(select(func.count()).select_from(StakeOrder).where(
        StakeOrder.sent_at >= today))).scalar_one()
    return Exposure(spent_total=float(spent), bets_today=int(bets_today))


def _order_json(o: StakeOrder) -> dict[str, Any]:
    return {c: getattr(o, c) for c in (
        "id", "created_at", "source", "kind", "outcome_id", "outcome_ids", "description", "amount", "currency",
        "min_price", "price_at_creation", "target_bet_id", "status",
        "status_detail", "request_preview", "stake_bet_id", "placed_price", "approved_at", "sent_at", "finished_at")}


# ----------------------------------------------------------------------------- dashboard

@router.get("/status")
async def status() -> dict[str, Any]:
    limits = Limits.from_env()
    async with AsyncSessionFactory() as session:
        helper = await _get(session, "stake_helper", {})
        enabled = bool(await _get(session, "stake_execution_enabled", False))
        learn = bool(await _get(session, "stake_learn_mode", False))
        exposure = await _exposure(session)
        bet_op = await bet_operation(session)
        multi_op = await bet_operation(session, multi=True)
        cash_op = await cashout_operation(session)
        bet_list_op = await _get(session, "stake_bet_list_op")
        counts = dict((await session.execute(
            select(StakeOrder.status, func.count()).group_by(StakeOrder.status))).all())
    last_seen = helper.get("last_seen")
    connected = bool(last_seen) and (
        datetime.now(UTC) - datetime.fromisoformat(last_seen)).total_seconds() < HELPER_STALE_SECONDS
    return {
        "helper": {**helper, "connected": connected},
        "execution_enabled": enabled, "learn_mode": learn,
        "limits": vars(limits), "spent_total": exposure.spent_total, "bets_today": exposure.bets_today,
        "budget_left": max(0.0, limits.budget - exposure.spent_total),
        "bet_request_learned": bet_op is not None,
        "bet_operation": bet_op.operation_name if bet_op else None,
        "multi_request_learned": multi_op is not None,
        "cashout_request_learned": cash_op is not None,
        "bet_list_learned": bool(bet_list_op),
        "orders_by_status": counts,
    }


class SettingsBody(BaseModel):
    execution_enabled: bool | None = None
    learn_mode: bool | None = None


@router.post("/settings")
async def settings(body: SettingsBody) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        if body.execution_enabled is not None:
            await _put(session, "stake_execution_enabled", body.execution_enabled)
        if body.learn_mode is not None:
            await _put(session, "stake_learn_mode", body.learn_mode)
        await session.commit()
    return {"ok": True}


@router.get("/outcomes")
async def outcomes(q: str = "", main_markets: bool = True, limit: int = 120) -> list[dict[str, Any]]:
    """Outcomes seen on Stake, for matches in our leagues first (1X2 / totals / BTTS by default)."""
    async with AsyncSessionFactory() as session:
        query = (select(StakeOutcome, StakeFixture)
                 .join(StakeFixture, StakeFixture.id == StakeOutcome.stake_fixture_id, isouter=True)
                 .order_by(StakeFixture.league_code.is_(None), StakeFixture.start_time, StakeOutcome.market_code,
                           StakeOutcome.specifiers, StakeOutcome.id)
                 .limit(limit))
        if main_markets:
            query = query.where(StakeOutcome.selection.is_not(None), StakeFixture.league_code.is_not(None),
                                (StakeOutcome.market_code != "18") | (StakeOutcome.specifiers == "total=2.5"))
        if q:
            like = f"%{q}%"
            query = query.where(StakeOutcome.fixture_name.ilike(like) | StakeOutcome.name.ilike(like)
                                | StakeOutcome.market_name.ilike(like))
        rows = (await session.execute(query)).all()
    return [{"outcome_id": o.outcome_id, "fixture": o.fixture_name, "market": o.market_name, "name": o.name,
             "selection": o.selection, "price": o.price, "active": o.active, "seen_at": o.seen_at,
             "league": f.league_code if f else None, "start_time": f.start_time if f else None,
             "match_id": f.match_id if f else None} for o, f in rows]


@router.get("/operations")
async def operations() -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(select(StakeOperation).order_by(StakeOperation.last_seen_at.desc()))).scalars()
        return [{"name": r.operation_name, "kind": r.kind, "seen": r.seen_count, "last_seen_at": r.last_seen_at,
                 "is_bet": is_bet_mutation(r.operation_name, r.kind)} for r in rows]


@router.get("/orders")
async def orders(limit: int = 50) -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(select(StakeOrder).order_by(StakeOrder.id.desc()).limit(limit))).scalars()
        return [_order_json(o) for o in rows]


class NewOrder(BaseModel):
    outcome_id: str
    amount: float = 1.0
    min_price: float | None = None


@router.post("/orders")
async def create_order(body: NewOrder) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        outcome = (await session.execute(select(StakeOutcome).where(
            StakeOutcome.outcome_id == body.outcome_id))).scalar_one_or_none()
        if outcome is None:
            raise HTTPException(404, "Unknown Stake outcome. Open the match on Stake with Learn mode on first.")
        try:
            order = await create_stake_order(session, outcome, body.amount, source="manual_test", auto_approve=False)
        except GuardrailError as exc:
            raise HTTPException(400, str(exc)) from exc
        await session.commit()
        return _order_json(order)


async def _transition(order_id: int, allowed: tuple[str, ...], new_status: str, **values: Any) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        order = await session.get(StakeOrder, order_id)
        if order is None:
            raise HTTPException(404, "Order not found")
        if order.status not in allowed:
            raise HTTPException(409, f"Order is {order.status}")
        order.status = new_status
        for key, value in values.items():
            setattr(order, key, value)
        await session.commit()
        return _order_json(order)


@router.post("/orders/{order_id}/approve")
async def approve(order_id: int) -> dict[str, Any]:
    return await _transition(order_id, ("pending_approval",), "approved", approved_at=datetime.now(UTC))


@router.post("/orders/{order_id}/reject")
async def reject(order_id: int) -> dict[str, Any]:
    return await _transition(order_id, ("pending_approval", "approved"), "rejected",
                             finished_at=datetime.now(UTC), status_detail="Rejected by you")


# ----------------------------------------------------------------------------- helper

class Heartbeat(BaseModel):
    version: str
    host: str
    balances: dict[str, dict[str, float]] | None = None
    token_source: str | None = None
    error: str | None = None
    hook: dict[str, int] | None = None  # in-page listener counters (diagnostics only)


@router.post("/helper/heartbeat")
async def heartbeat(body: Heartbeat) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        await _put(session, "stake_helper", {
            "last_seen": datetime.now(UTC).isoformat(), "version": body.version, "host": body.host,
            "balances": body.balances, "token_source": body.token_source, "error": body.error,
            "hook": body.hook,
        })
        learn = bool(await _get(session, "stake_learn_mode", False))
        enabled = bool(await _get(session, "stake_execution_enabled", False))
        bet_list_request = None
        list_name = await _get(session, "stake_bet_list_op")
        if list_name:
            op = (await session.execute(select(StakeOperation).where(
                StakeOperation.operation_name == list_name))).scalar_one_or_none()
            if op:
                variables = dict(op.sample_variables or {})
                if "limit" in variables:
                    variables["limit"] = 50  # all open bets, not just the first few
                bet_list_request = {"operationName": op.operation_name, "query": op.query, "variables": variables}
        await session.commit()
    return {"learn_mode": learn, "execution_enabled": enabled, "poll_seconds": 5,
            "bet_list_request": bet_list_request, "bet_list_every_seconds": 60}


@router.get("/helper/token")
async def helper_token() -> dict[str, Any]:
    """Fallback for when the Stake tab's own session cookie can't be read. Local helper only."""
    token = os.getenv("STAKE_ACCESS_TOKEN", "").strip()
    return {"token": token or None}


class Captured(BaseModel):
    operations: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []


@router.post("/helper/captured")
async def captured(body: Captured) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        if not await _get(session, "stake_learn_mode", False):
            return {"stored": 0, "outcomes": 0, "note": "Learn mode is off"}
        stored = 0
        for op in body.operations:
            query = str(op.get("query") or "")
            described = describe_operation(op.get("operationName"), query)
            if described is None:
                continue
            name, kind = described
            name = template_name(name, kind, op.get("variables") or {})
            statement = insert(StakeOperation).values(
                operation_name=name[:128], kind=kind, query=query, sample_variables=_scrub(op.get("variables") or {}))
            await session.execute(statement.on_conflict_do_update(
                index_elements=["operation_name"],
                set_={"query": statement.excluded.query, "sample_variables": statement.excluded.sample_variables,
                      "seen_count": StakeOperation.seen_count + 1, "last_seen_at": func.now()}))
            stored += 1
        outcomes_seen = 0
        raw_repo = PostgresRawPayloadRepository(session)
        for response in body.responses:
            data = _scrub(response.get("data"))
            if data:
                # Raw first, like every other source: kept untouched so Stake's fixture/market
                # structure can be parsed properly (and re-parsed later) without re-capturing.
                described = describe_operation(response.get("operationName"), "")
                name = (response.get("operationName") or (described[0] if described else None)
                        or next(iter(data), "unknown"))
                await raw_repo.store_if_new(RawPayload.from_request_context(
                    ProviderRequestContext(provider_name="stake", endpoint=f"graphql/{name}"[:200],
                                           requested_at=datetime.now(UTC), request_id=str(uuid4())),
                    data))
            fixtures, outcomes = parse_payload(data)
            await store_parsed(session, fixtures, outcomes)
            outcomes_seen += len(outcomes)
            bets = parse_sport_bets(data)
            if bets:
                await _store_stake_bets(session, bets)
                if response.get("operationName"):  # remember it: the helper re-runs it every minute
                    await _put(session, "stake_bet_list_op", response["operationName"])
        await link_stake_fixtures(session)
        await session.commit()
    return {"stored": stored, "outcomes": outcomes_seen}


@router.post("/helper/next")
async def next_order() -> dict[str, Any]:
    """Hand the oldest approved order to the helper, if every guardrail still allows it."""
    limits = Limits.from_env()
    async with AsyncSessionFactory() as session:
        # An order "sent" but never answered is marked failed (not retried: it may have gone through).
        stale = (await session.execute(select(StakeOrder).where(
            StakeOrder.status == "sent", StakeOrder.sent_at < datetime.now(UTC) - SENT_TIMEOUT))).scalars().all()
        for o in stale:
            o.status, o.finished_at = "failed", datetime.now(UTC)
            o.status_detail = "No answer from the helper within 2 minutes. Check My Bets on Stake before retrying."

        order = (await session.execute(select(StakeOrder).where(StakeOrder.status == "approved")
                                       .order_by(StakeOrder.approved_at).limit(1).with_for_update())).scalar_one_or_none()
        if order is None:
            await session.commit()
            return {"order": None}
        enabled = bool(await _get(session, "stake_execution_enabled", False))
        if order.kind == "cashout":
            # Your own click; it only takes money off the table, so it doesn't wait for Execution.
            # The helper presses Stake's own Cashout button: Stake's exact value, Stake's own flow.
            order.status, order.sent_at = "sent", datetime.now(UTC)
            await session.commit()
            preview = order.request_preview or {}
            return {"order": {"id": order.id, "kind": "cashout", "description": order.description,
                              "iid": preview.get("iid"), "bet_id": preview.get("bet_id"),
                              "estimate": preview.get("estimate")}}

        op = await bet_operation(session, multi=order.kind == "multi")
        if op is None or not enabled:
            await session.commit()  # leave it approved; it goes out once both are true
            return {"order": None, "reason": "Execution is off" if not enabled else "Bet request not learned yet"}
        try:
            check_dispatch(order.amount, order.currency, limits, await _exposure(session), enabled)
            outcome = order.outcome_ids if order.kind == "multi" else order.outcome_id
            request = build_bet_request(op.operation_name.replace(MULTI_SUFFIX, ""), op.query, op.sample_variables,
                                        outcome, order.amount, order.currency)
        except (GuardrailError, TemplateError) as exc:
            order.status, order.status_detail, order.finished_at = "blocked", str(exc), datetime.now(UTC)
            await session.commit()
            return {"order": None, "reason": str(exc)}

        order.status, order.sent_at, order.request_preview = "sent", datetime.now(UTC), request["variables"]
        await session.commit()
        return {"order": {"id": order.id, "description": order.description, "amount": order.amount,
                          "currency": order.currency, "min_price": order.min_price, "request": request}}


class OrderResult(BaseModel):
    response: dict[str, Any] | None = None
    error: str | None = None


@router.post("/helper/orders/{order_id}/result")
async def order_result(order_id: int, body: OrderResult) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        order = await session.get(StakeOrder, order_id)
        if order is None or order.status != "sent":
            raise HTTPException(409, "Order is not waiting for a result")
        response = _scrub(body.response or {})
        placed, bet_id, message = bet_result(response) if body.response else (False, None, body.error or "Error")
        if order.kind == "cashout":
            data = (body.response or {}).get("data") or {}
            result = data.get("cashoutSportBet") if isinstance(data, dict) else None
            ok = bool(result) and not (body.response or {}).get("errors")
            if ok:
                payout = result.get("payout")
                order.status = "placed"
                order.status_detail = f"Cashed out for ₹{payout:g}" if isinstance(payout, int | float) else "Cashed out"
                order.placed_price = payout if isinstance(payout, int | float) else None
            else:
                order.status, order.status_detail = "failed", body.error or message
        else:
            order.status = "placed" if placed else "failed"
            order.stake_bet_id, order.status_detail = bet_id, message
        order.response, order.finished_at = response, datetime.now(UTC)
        await session.commit()
        return _order_json(order)


# ----------------------------------------------------------------------------- your Stake bets, payouts, cash-out

async def _store_stake_bets(session: AsyncSession, bets: list[dict[str, Any]]) -> None:
    for b in bets:
        values = {**b}
        values["placed_at"] = parse_start(values.pop("placed_at", None))  # Stake uses "Wed, 25 Nov 2026 12:11:39 GMT"
        statement = insert(StakeBet).values(**values)
        await session.execute(statement.on_conflict_do_update(
            index_elements=["id"], set_={k: statement.excluded[k] for k in values if k != "id"}))


class BetList(BaseModel):
    data: dict[str, Any] | None = None


@router.post("/helper/bets")
async def helper_bets(body: BetList) -> dict[str, Any]:
    """The helper re-runs your Stake "My Bets" request every minute; this stores the result."""
    bets = parse_sport_bets(_scrub(body.data or {}))
    async with AsyncSessionFactory() as session:
        await _store_stake_bets(session, bets)
        await session.commit()
    return {"bets": len(bets)}


def _is_open(b: StakeBet) -> bool:
    if b.active is not None:
        return bool(b.active)
    return (b.status or "").lower() in ("active", "pending", "open", "confirmed")


@router.get("/bets")
async def stake_bets(open_only: bool = True) -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(select(StakeBet).order_by(StakeBet.placed_at.desc().nulls_last()))).scalars().all()
    out = []
    for b in rows:
        if open_only and not _is_open(b):
            continue
        amount = b.amount or 0.0
        view = cashout_view(b.raw or {})
        legs = view["legs"]
        title = (f"{len(legs)}-leg multi" if len(legs) > 1
                 else f"{(legs[0]['selection'] if legs else None) or b.description or b.id}")
        out.append({
            "id": b.id, "status": b.status, "open": _is_open(b), "amount": amount, "currency": b.currency,
            "title": title, "legs": legs, "placed_at": b.placed_at, "updated_at": b.updated_at,
            "potential_payout": round(amount * b.potential_multiplier, 2) if b.potential_multiplier else None,
            "cashout_available": view["available"], "cashout_reason": view["reason"],
            "cashout_estimate": (round(amount * view["estimate_multiplier"], 2)
                                 if view["estimate_multiplier"] is not None else None),
        })
    return out


@router.post("/bets/{bet_id}/cashout")
async def cashout(bet_id: str) -> dict[str, Any]:
    """Your click: the helper opens the bet on Stake and presses Stake's own Cashout button."""
    async with AsyncSessionFactory() as session:
        bet = await session.get(StakeBet, bet_id)
        if bet is None or not _is_open(bet):
            raise HTTPException(404, "No open Stake bet with that id")
        view = cashout_view(bet.raw or {})
        if not view["available"]:
            raise HTTPException(409, f"Stake isn't offering a cash-out right now: {view['reason']}")
        busy = (await session.execute(select(func.count()).select_from(StakeOrder).where(
            StakeOrder.kind == "cashout", StakeOrder.target_bet_id == bet_id,
            StakeOrder.status.in_(["approved", "sent"])))).scalar_one()
        if busy:
            raise HTTPException(409, "A cash-out for this bet is already in progress")
        legs = view["legs"]
        title = f"{len(legs)}-leg multi" if len(legs) > 1 else (legs[0]["selection"] if legs else bet.id)
        estimate = round((bet.amount or 0) * view["estimate_multiplier"], 2) if view["estimate_multiplier"] else None
        try:
            order = await create_cashout_order(session, bet, title, estimate)
        except TemplateError as exc:
            raise HTTPException(409, str(exc)) from exc
        await session.commit()
        return _order_json(order)


@router.get("/exposure")
async def exposure() -> dict[str, Any]:
    """What is in play right now: stakes and estimated total payout, real (Stake) and paper."""
    async with AsyncSessionFactory() as session:
        real = [b for b in (await session.execute(select(StakeBet))).scalars().all() if _is_open(b)]
        paper = (await session.execute(select(StrategyBet).where(
            StrategyBet.status == "open", StrategyBet.mode == "paper"))).scalars().all()
        pending = (await session.execute(select(StakeOrder).where(
            StakeOrder.status.in_(["pending_approval", "approved", "sent"]), StakeOrder.kind != "cashout"))).scalars().all()
    real_stake = sum(b.amount or 0 for b in real)
    real_payout = sum((b.amount or 0) * (b.potential_multiplier or 0) for b in real)
    real_cashout = 0.0
    for b in real:
        view = cashout_view(b.raw or {})
        if view["estimate_multiplier"] is not None:
            real_cashout += (b.amount or 0) * view["estimate_multiplier"]
    return {
        "real": {"bets": len(real), "stake": round(real_stake, 2), "potential_payout": round(real_payout, 2),
                 "cashout_value": round(real_cashout, 2)},
        "pending_orders": {"count": len(pending), "stake": round(sum(o.amount for o in pending), 2),
                           "potential_payout": round(sum(o.amount * (o.price_at_creation or 0) for o in pending), 2)},
        "paper": {"bets": len(paper), "stake": round(sum(b.stake for b in paper), 2),
                  "potential_payout": round(sum(b.stake * b.price for b in paper), 2)},
    }
