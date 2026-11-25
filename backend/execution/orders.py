"""Creating Stake orders: the one place real-money bets enter the system.

Used by the dashboard (manual ₹1 test bets) and by strategies in approve/auto mode.
Every order is checked against the .env limits here, and again when the helper picks it up.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import StakeOperation, StakeOrder, StakeOutcome
from backend.execution.guardrails import Limits, check_new_order
from backend.execution.stake_requests import TemplateError, build_bet_request, is_bet_mutation


async def bet_operation(session: AsyncSession) -> StakeOperation | None:
    ops = (await session.execute(select(StakeOperation).order_by(StakeOperation.last_seen_at.desc()))).scalars()
    return next((op for op in ops if is_bet_mutation(op.operation_name, op.kind)), None)


async def create_stake_order(session: AsyncSession, outcome: StakeOutcome, amount: float, *, source: str,
                             auto_approve: bool, match_id: int | None = None) -> StakeOrder:
    """Raises GuardrailError if the amount breaks a limit."""
    limits = Limits.from_env()
    check_new_order(amount, limits.currency, limits)
    op = await bet_operation(session)
    preview, detail = None, None
    if op is None:
        detail = "Waiting: the bet request hasn't been learned yet (place one manual bet with Learn mode on)."
    else:
        try:
            preview = build_bet_request(op.operation_name, op.query, op.sample_variables, outcome.outcome_id,
                                        amount, limits.currency)["variables"]
        except TemplateError as exc:
            detail = str(exc)
    order = StakeOrder(
        source=source, match_id=match_id, outcome_id=outcome.outcome_id,
        description=f"{outcome.fixture_name or '?'} · {outcome.market_name or '?'}"
                    f"{' ' + outcome.specifiers if outcome.specifiers else ''} · {outcome.name}",
        amount=amount, currency=limits.currency, min_price=None,
        status="approved" if auto_approve else "pending_approval",
        approved_at=datetime.now(UTC) if auto_approve else None,
        status_detail=detail or ("Auto mode: approved by strategy" if auto_approve else None),
        request_preview=preview,
    )
    session.add(order)
    await session.flush()
    return order
