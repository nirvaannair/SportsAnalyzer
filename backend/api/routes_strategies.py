"""Strategies: settings (including reinvest % and mode), bankrolls, the bet ledger, automation status."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from backend.core.leagues import LEAGUES_BY_CODE
from backend.database.engine import AsyncSessionFactory
from backend.database.models import AppSetting, Match, StakeOrder, Strategy, StrategyBet, Team
from backend.strategies.core import MARKETS
from backend.strategies.engine import run_cycle, strategy_bankroll

router = APIRouter(prefix="/api/strategies")

DEFAULTS = [
    {"name": "Steady (flat 2%)", "kind": "flat", "stake_pct": 2, "reinvest_pct": 0, "min_edge": 0.05},
    {"name": "Compounder (flat 2%, reinvest 100%)", "kind": "flat", "stake_pct": 2, "reinvest_pct": 100,
     "min_edge": 0.05},
    {"name": "Kelly quarter", "kind": "kelly", "kelly_fraction": 0.25, "reinvest_pct": 50, "min_edge": 0.07},
    {"name": "Value outsiders (20-50%)", "kind": "flat", "stake_pct": 1, "reinvest_pct": 50, "min_edge": 0.08,
     "min_prob": 0.2, "max_prob": 0.5},
    {"name": "Treble (3-leg multi)", "kind": "multi", "multi_legs": 3, "stake_pct": 1, "reinvest_pct": 100,
     "min_edge": 0.1, "min_prob": 0.4, "max_prob": 0.85},
]


def _json(s: Strategy) -> dict[str, Any]:
    return {c: getattr(s, c) for c in (
        "id", "name", "kind", "mode", "enabled", "paused_reason", "model", "bankroll_start", "reinvest_pct",
        "stake_pct", "kelly_fraction", "max_stake", "min_edge", "min_price", "max_price", "min_prob", "max_prob",
        "multi_legs", "markets", "leagues",
        "max_bets_per_day", "drawdown_stop_pct", "created_at")}


async def _ensure_defaults(session) -> None:
    """Add any starter strategy that doesn't exist yet (all off, paper mode)."""
    existing = set((await session.execute(select(Strategy.name))).scalars())
    missing = [d for d in DEFAULTS if d["name"] not in existing]
    if not missing:
        return
    for d in missing:
        session.add(Strategy(mode="paper", enabled=False, bankroll_start=500.0, max_stake=10.0,
                             markets=["1x2", "ou25", "btts"], leagues=[], **d))
    await session.commit()


@router.get("")
async def list_strategies() -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        await _ensure_defaults(session)
        strategies = (await session.execute(select(Strategy).order_by(Strategy.id))).scalars().all()
        out = []
        for s in strategies:
            bank = await strategy_bankroll(session, s)
            counts = dict((await session.execute(select(StrategyBet.status, func.count()).where(
                StrategyBet.strategy_id == s.id).group_by(StrategyBet.status))).all())
            staked = (await session.execute(select(func.coalesce(func.sum(StrategyBet.stake), 0.0)).where(
                StrategyBet.strategy_id == s.id, StrategyBet.status.in_(["won", "lost"])))).scalar_one()
            out.append({**_json(s), "bankroll": {
                "pot": bank.pot, "available": bank.available, "banked": bank.banked, "open_stakes": bank.open_stakes,
                "profit": bank.profit, "drawdown_pct": round(bank.drawdown_pct, 1),
                "roi": round(bank.profit / staked, 4) if staked else None,
            }, "bets": counts})
        return out


class StrategyFields(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    kind: Literal["flat", "kelly", "multi"] | None = None
    mode: Literal["paper", "approve", "auto"] | None = None
    enabled: bool | None = None
    bankroll_start: float | None = Field(None, gt=0)
    reinvest_pct: float | None = Field(None, ge=0, le=100)
    stake_pct: float | None = Field(None, gt=0, le=20)
    kelly_fraction: float | None = Field(None, gt=0, le=1)
    max_stake: float | None = Field(None, ge=1)
    min_edge: float | None = Field(None, ge=0, le=1)
    min_price: float | None = Field(None, gt=1)
    max_price: float | None = Field(None, gt=1)
    min_prob: float | None = Field(None, ge=0, le=1)
    max_prob: float | None = Field(None, ge=0, le=1)
    multi_legs: int | None = Field(None, ge=2, le=6)
    markets: list[str] | None = None
    leagues: list[str] | None = None
    max_bets_per_day: int | None = Field(None, ge=1, le=100)
    drawdown_stop_pct: float | None = Field(None, gt=0, le=100)
    resume: bool | None = None  # clear an automatic drawdown pause
    confirm_real_money: bool = False  # required when switching to approve/auto


def _validate(fields: StrategyFields, current_mode: str | None) -> dict[str, Any]:
    values = fields.model_dump(exclude_none=True, exclude={"resume", "confirm_real_money"})
    if fields.markets is not None and (not fields.markets or set(fields.markets) - set(MARKETS)):
        raise HTTPException(400, f"Markets must be among {', '.join(MARKETS)}")
    if fields.leagues is not None and set(fields.leagues) - set(LEAGUES_BY_CODE):
        raise HTTPException(400, "Unknown league code")
    if fields.mode in ("approve", "auto") and fields.mode != current_mode and not fields.confirm_real_money:
        raise HTTPException(400, "Switching to approve or auto mode uses real money: confirm_real_money is required")
    return values


@router.post("")
async def create_strategy(fields: StrategyFields) -> dict[str, Any]:
    values = _validate(fields, None)
    if not values.get("name") or not values.get("kind") or not values.get("bankroll_start"):
        raise HTTPException(400, "name, kind and bankroll_start are required")
    async with AsyncSessionFactory() as session:
        if (await session.execute(select(Strategy.id).where(Strategy.name == values["name"]))).first():
            raise HTTPException(409, "A strategy with that name exists")
        strategy = Strategy(**{"mode": "paper", "enabled": False, **values})
        session.add(strategy)
        await session.commit()
        return _json(strategy)


@router.patch("/{strategy_id}")
async def update_strategy(strategy_id: int, fields: StrategyFields) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        strategy = await session.get(Strategy, strategy_id)
        if strategy is None:
            raise HTTPException(404, "Strategy not found")
        for key, value in _validate(fields, strategy.mode).items():
            setattr(strategy, key, value)
        if fields.resume:
            strategy.paused_reason = None
        await session.commit()
        return _json(strategy)


@router.post("/run")
async def run_now() -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        await _ensure_defaults(session)
        report = await run_cycle(session)
        await session.commit()
    return report


@router.get("/bets")
async def bets(strategy_id: int | None = None, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    home, away = aliased(Team), aliased(Team)
    async with AsyncSessionFactory() as session:
        query = (select(StrategyBet, Strategy.name, Match, home.name, away.name, StakeOrder.status)
                 .join(Strategy, Strategy.id == StrategyBet.strategy_id)
                 .join(Match, Match.id == StrategyBet.match_id)
                 .join(home, home.id == Match.home_team_id).join(away, away.id == Match.away_team_id)
                 .join(StakeOrder, StakeOrder.id == StrategyBet.stake_order_id, isouter=True)
                 .order_by(StrategyBet.id.desc()).limit(limit))
        if strategy_id:
            query = query.where(StrategyBet.strategy_id == strategy_id)
        if status:
            query = query.where(StrategyBet.status == status)
        rows = (await session.execute(query)).all()
    return [{
        "id": b.id, "strategy": name, "match": f"{h} v {a}", "date": m.match_date, "kickoff_at": m.kickoff_at,
        "score": None if m.home_goals is None else f"{m.home_goals}–{m.away_goals}",
        "market": b.market, "selection": b.selection, "mode": b.mode, "p_model": b.p_model, "price": b.price,
        "price_source": b.price_source, "edge": b.edge, "stake": b.stake, "status": b.status, "profit": b.profit,
        "order_status": order_status, "created_at": b.created_at, "settled_at": b.settled_at, "legs": b.legs,
    } for b, name, m, h, a, order_status in rows]


@router.get("/automation")
async def automation() -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        row = await session.get(AppSetting, "automation")
    return row.value if row else {}
