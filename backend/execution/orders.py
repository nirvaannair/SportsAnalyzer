"""Creating Stake orders: the one place real-money actions enter the system.

Used by the dashboard (manual ₹1 test bets, cash-out clicks) and by strategies in
approve/auto mode. Every bet is checked against the .env limits here, and again when the
helper picks it up. Bets above STAKE_APPROVAL_ABOVE always wait for a click.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import StakeBet, StakeOperation, StakeOrder, StakeOutcome
from backend.execution.guardrails import Limits, check_new_order, needs_approval
from backend.execution.stake_requests import (
    MULTI_SUFFIX,
    TemplateError,
    build_bet_request,
    build_cashout_variables,
    is_bet_mutation,
    is_cashout_mutation,
)


async def _operations(session: AsyncSession) -> list[StakeOperation]:
    return list((await session.execute(select(StakeOperation).order_by(StakeOperation.last_seen_at.desc()))).scalars())


async def bet_operation(session: AsyncSession, multi: bool = False) -> StakeOperation | None:
    """The learned single-bet request, or (multi=True) the learned multi-bet request."""
    for op in await _operations(session):
        if not is_bet_mutation(op.operation_name.replace(MULTI_SUFFIX, ""), op.kind):
            continue
        if op.operation_name.endswith(MULTI_SUFFIX) == multi:
            return op
    return None


async def cashout_operation(session: AsyncSession) -> StakeOperation | None:
    return next((op for op in await _operations(session) if is_cashout_mutation(op.operation_name, op.kind)), None)


def _describe(outcome: StakeOutcome) -> str:
    return (f"{outcome.fixture_name or '?'} · {outcome.market_name or '?'}"
            f"{' ' + outcome.specifiers if outcome.specifiers else ''} · {outcome.name}")


async def create_stake_order(session: AsyncSession, outcomes: StakeOutcome | list[StakeOutcome], amount: float, *,
                             source: str, auto_approve: bool, match_id: int | None = None) -> StakeOrder:
    """A single bet (one outcome) or a multi (several outcomes, all must win). Raises GuardrailError."""
    legs = outcomes if isinstance(outcomes, list) else [outcomes]
    multi = len(legs) > 1
    limits = Limits.from_env()
    check_new_order(amount, limits.currency, limits)

    op = await bet_operation(session, multi=multi)
    ids = [o.outcome_id for o in legs]
    preview, detail = None, None
    if op is None:
        detail = ("Waiting: place one multi bet by hand with Learn mode on so the multi request is learned."
                  if multi else "Waiting: the bet request hasn't been learned yet (place one manual bet with Learn mode on).")
    else:
        try:
            preview = build_bet_request(op.operation_name.replace(MULTI_SUFFIX, ""), op.query, op.sample_variables,
                                        ids if multi else ids[0], amount, limits.currency)["variables"]
        except TemplateError as exc:
            detail = str(exc)

    approve_now = auto_approve and not needs_approval(amount, limits)
    if auto_approve and not approve_now:
        detail = f"Above ₹{limits.approval_above:g}: waiting for your approval even in Auto mode."
    price = 1.0
    for o in legs:
        price *= o.price or 1.0

    order = StakeOrder(
        source=source, kind="multi" if multi else "bet", match_id=match_id,
        outcome_id=ids[0], outcome_ids=ids if multi else None,
        description=(" + ".join(_describe(o) for o in legs))[:300],
        amount=amount, currency=limits.currency, min_price=None, price_at_creation=round(price, 3),
        status="approved" if approve_now else "pending_approval",
        approved_at=datetime.now(UTC) if approve_now else None,
        status_detail=detail or ("Auto mode: approved by strategy" if approve_now else None),
        request_preview=preview,
    )
    session.add(order)
    await session.flush()
    return order


async def create_cashout_order(session: AsyncSession, bet: StakeBet) -> StakeOrder:
    """Cash out one Stake bet at its current value. Created only by the owner's click."""
    op = await cashout_operation(session)
    if op is None:
        raise TemplateError("Cash-out hasn't been learned yet: cash out one bet by hand on Stake with Learn mode on.")
    variables = build_cashout_variables(op.sample_variables, bet.id, bet.cashout_multiplier)
    value = round((bet.amount or 0) * (bet.cashout_multiplier or 0), 2)
    order = StakeOrder(
        source="cashout", kind="cashout", target_bet_id=bet.id, outcome_id="-",
        description=f"Cash out: {bet.description or bet.id} (about ₹{value:g})"[:300],
        amount=0.0, currency=bet.currency or "inr", status="approved", approved_at=datetime.now(UTC),
        status_detail="Cash-out requested by you", request_preview=variables,
    )
    session.add(order)
    await session.flush()
    return order
