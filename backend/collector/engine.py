"""Background collector: works through a queue of free-plan API requests, within each plan's limits.

Runs inside the API server (started from backend.api.main). Off by default; the owner
switches it, and each provider, on from the Data Sources page.

For every request:
  1. the provider must be switched on, have a key if it needs one, and have daily budget left;
  2. requests to one provider are spaced by its min_interval_s;
  3. the response is stored untouched in raw_provider_observations (raw first, always);
  4. usage is counted per UTC day in provider_usage.
Quota errors pause that provider until the next UTC day; "not in your plan" marks the task
unavailable so it is never retried.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.collector.providers import PROVIDERS, Provider, check_endpoint
from backend.core.config import ENV_FILE
from backend.database.engine import AsyncSessionFactory
from backend.database.models import AppSetting, CollectorTask, ProviderUsage, RawProviderObservation

log = logging.getLogger("collector")
SETTING_KEY = "collector"
MAX_ATTEMPTS = 3
FOLLOWUP_PRIORITY = 50  # per-fixture requests run after the league-level ones

# In-process runtime state (the loop and the API share one process).
RUNTIME: dict[str, dict[str, Any]] = {name: {} for name in PROVIDERS}


def default_state() -> dict[str, Any]:
    return {"enabled": False,
            "providers": {name: {"enabled": False, "daily_budget": p.default_daily_budget}
                          for name, p in PROVIDERS.items()}}


async def get_state(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(AppSetting, SETTING_KEY)
    state = default_state()
    if row and isinstance(row.value, dict):
        state["enabled"] = bool(row.value.get("enabled", False))
        for name, saved in (row.value.get("providers") or {}).items():
            if name in state["providers"] and isinstance(saved, dict):
                state["providers"][name].update({k: saved[k] for k in ("enabled", "daily_budget") if k in saved})
    return state


async def save_state(session: AsyncSession, state: dict[str, Any]) -> None:
    statement = insert(AppSetting).values(key=SETTING_KEY, value=state)
    await session.execute(statement.on_conflict_do_update(index_elements=["key"],
                                                          set_={"value": statement.excluded.value}))


def utc_today() -> date:
    return datetime.now(UTC).date()


async def used_today(session: AsyncSession, provider: str) -> int:
    row = await session.get(ProviderUsage, (provider, utc_today()))
    return row.requests if row else 0


async def _count_usage(session: AsyncSession, provider: str, error: bool, remaining: int | None) -> None:
    values = {"provider": provider, "day": utc_today(), "requests": 1, "errors": 1 if error else 0,
              "remaining_reported": remaining}
    statement = insert(ProviderUsage).values(**values)
    set_ = {"requests": ProviderUsage.requests + 1, "errors": ProviderUsage.errors + (1 if error else 0)}
    if remaining is not None:
        set_["remaining_reported"] = remaining
    await session.execute(statement.on_conflict_do_update(index_elements=["provider", "day"], set_=set_))


# ---------------------------------------------------------------------------
# Planning the queue
# ---------------------------------------------------------------------------

async def plan(session: AsyncSession) -> dict[str, int]:
    """Add every task the providers want (existing ones are kept), then follow-ups, and
    mark tasks done whose exact request is already in the raw store (e.g. from the CLI)."""
    added: dict[str, int] = {}
    for name, provider in PROVIDERS.items():
        rows = []
        for spec in provider.planner():
            check_endpoint(spec.endpoint)
            rows.append({"provider": name, "kind": spec.kind, "endpoint": spec.endpoint, "params": spec.params,
                         "label": spec.label, "priority": spec.priority, "status": "pending"})
        if rows:
            result = await session.execute(insert(CollectorTask).values(rows).on_conflict_do_nothing()
                                           .returning(CollectorTask.id))
            added[name] = len(result.all())
    added["api_football_followups"] = await expand_followups(session)
    await session.execute(text("""
        UPDATE collector_tasks t SET status = 'done', done_at = now(), error = 'already collected earlier'
        WHERE t.status = 'pending' AND EXISTS (
            SELECT 1 FROM raw_provider_observations r
            WHERE r.provider_name = t.provider AND r.endpoint = t.endpoint
              AND r.request_parameters = t.params AND r.status IN ('stored', 'success'))
    """))
    return added


def finished_fixture_ids(payload: Any) -> list[tuple[str, int]]:
    """(fixture id, season) for finished matches in an API-Football /fixtures payload."""
    out = []
    if not isinstance(payload, dict):
        return out
    season = (payload.get("parameters") or {}).get("season")
    for item in payload.get("response") or []:
        fixture = item.get("fixture") or {}
        if fixture.get("id") and (fixture.get("status") or {}).get("short") in ("FT", "AET", "PEN"):
            out.append((str(fixture["id"]), int(season or 0)))
    return out


async def expand_followups(session: AsyncSession) -> int:
    """For every API-Football fixture list we hold, queue per-fixture player stats (newest season first)."""
    payloads = (await session.execute(
        select(RawProviderObservation.payload).where(
            RawProviderObservation.provider_name == "api_football",
            RawProviderObservation.endpoint == "fixtures",
            RawProviderObservation.status.in_(("stored", "success")))
    )).scalars().all()
    rows, seen = [], set()
    for payload in payloads:
        for fixture_id, season in finished_fixture_ids(payload):
            if fixture_id in seen:
                continue
            seen.add(fixture_id)
            rows.append({"provider": "api_football", "kind": "fixture_players", "endpoint": "fixtures/players",
                         "params": {"fixture": int(fixture_id)},
                         "label": f"Player stats, fixture {fixture_id} ({season}/{(season + 1) % 100:02d})",
                         "priority": FOLLOWUP_PRIORITY + max(0, 2024 - season), "status": "pending"})
    added = 0
    for start in range(0, len(rows), 2000):
        result = await session.execute(insert(CollectorTask).values(rows[start:start + 2000])
                                       .on_conflict_do_nothing().returning(CollectorTask.id))
        added += len(result.all())
    return added


# ---------------------------------------------------------------------------
# Running one request
# ---------------------------------------------------------------------------

def _items(payload: Any) -> int | None:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("response", "matches", "teams", "teams_list"):
            if isinstance(payload.get(key), list):
                return len(payload[key])
        if "teams" in payload and payload["teams"] is None:
            return 0
    return None


def _remaining(provider: str, headers: httpx.Headers) -> int | None:
    name = {"api_football": "x-ratelimit-requests-remaining"}.get(provider)
    value = headers.get(name) if name else None
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def classify(provider: str, status_code: int, payload: Any) -> tuple[str, str | None]:
    """-> (outcome, message). outcome: ok | unavailable | quota | auth | retry | failed."""
    if provider == "api_football" and status_code == 200 and isinstance(payload, dict):
        errors = payload.get("errors")
        if errors:
            message = json.dumps(errors)[:300]
            low = message.lower()
            if "request" in low and ("limit" in low or "day" in low):
                return "quota", message
            if "token" in low or "key" in low or "subscription" in low:
                return "auth", message
            if "plan" in low or "season" in low or "free" in low:
                return "unavailable", message
            return "failed", message
    if status_code == 200:
        return "ok", None
    if status_code in (401,):
        return "auth", f"HTTP {status_code}: the key was refused"
    if status_code in (403, 404):
        return "unavailable", f"HTTP {status_code}: not available on the free plan"
    if status_code == 429:
        return "retry", "HTTP 429: too many requests, backing off"
    if status_code >= 500:
        return "retry", f"HTTP {status_code}: provider error"
    return "failed", f"HTTP {status_code}"


async def _store_raw(session: AsyncSession, provider: Provider, task: CollectorTask, response: httpx.Response,
                     payload: Any, requested_at: datetime) -> None:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    safe_headers = {k: v for k, v in response.headers.items() if k.lower().startswith(("x-ratelimit", "x-requests", "date", "content-type"))}
    session.add(RawProviderObservation(
        provider_name=provider.name, endpoint=task.endpoint, request_id=str(uuid4()), entity_type=task.kind,
        provider_entity_id=None, requested_at=requested_at, received_at=datetime.now(UTC),
        request_parameters=task.params, response_headers=safe_headers, payload_format="json",
        payload_hash=hashlib.sha256(body.encode()).hexdigest(), payload=payload, status="stored",
        http_status=response.status_code,
    ))


async def _after_store(session: AsyncSession, provider: Provider, task: CollectorTask, payload: Any) -> None:
    """Parse what we can right away. API-Football fixture lists register teams/fixtures and
    queue per-fixture player stats; everything else waits in the raw store for its parser."""
    if provider.name == "api_football" and task.kind == "fixtures":
        from backend.core.leagues import LEAGUES_BY_API_FOOTBALL
        from backend.identity.team_resolver import (
            link_fixtures_to_matches,
            resolve_unresolved_teams,
        )
        from backend.ingestion.api_football_sync import parse_fixtures, register_fixtures

        league = LEAGUES_BY_API_FOOTBALL.get(int(task.params.get("league", 0)))
        if league is not None:
            await register_fixtures(session, league, int(task.params["season"]), parse_fixtures(payload))
            await resolve_unresolved_teams(session)
            await link_fixtures_to_matches(session)
        await session.flush()
        await expand_followups(session)


async def run_task(session: AsyncSession, provider: Provider, task: CollectorTask,
                   client: httpx.AsyncClient) -> str:
    check_endpoint(task.endpoint)
    url = f"{provider.base_url.rstrip('/')}/{task.endpoint.lstrip('/')}"
    requested_at = datetime.now(UTC)
    task.attempts += 1
    try:
        response = await client.get(url, params=task.params, headers=provider.headers())
    except httpx.HTTPError as exc:
        await _count_usage(session, provider.name, True, None)
        task.error = f"Network error: {type(exc).__name__}"
        task.status = "failed" if task.attempts >= MAX_ATTEMPTS else "pending"
        return "retry"
    try:
        payload = response.json()
    except ValueError:
        payload = None
    outcome, message = classify(provider.name, response.status_code, payload)
    await _count_usage(session, provider.name, outcome != "ok", _remaining(provider.name, response.headers))

    if outcome == "ok":
        await _store_raw(session, provider, task, response, payload, requested_at)
        task.status, task.items, task.error, task.done_at = "done", _items(payload), None, datetime.now(UTC)
        await _after_store(session, provider, task, payload)
    elif outcome == "unavailable":
        task.status, task.error, task.done_at = "unavailable", message, datetime.now(UTC)
    elif outcome in ("quota", "auth"):
        task.attempts -= 1  # not the task's fault
        task.error = message
    else:
        task.error = message
        task.status = "failed" if task.attempts >= MAX_ATTEMPTS else "pending"
    return outcome


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

def _next_utc_midnight() -> datetime:
    now = datetime.now(UTC)
    return datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)


async def tick(client: httpx.AsyncClient) -> int:
    """Run at most one request per provider whose turn it is. Returns how many ran."""
    ran = 0
    now = datetime.now(UTC)
    async with AsyncSessionFactory() as session:
        state = await get_state(session)
        if not state["enabled"]:
            return 0
        for name, provider in PROVIDERS.items():
            settings, runtime = state["providers"][name], RUNTIME[name]
            if not settings["enabled"] or not provider.configured():
                continue
            if runtime.get("paused_until") and now < runtime["paused_until"]:
                continue
            if runtime.get("next_at") and now < runtime["next_at"]:
                continue
            budget = int(settings["daily_budget"])
            if provider.plan_daily_limit is not None:
                budget = min(budget, provider.plan_daily_limit)
            if await used_today(session, name) >= budget:
                runtime["paused_until"], runtime["reason"] = _next_utc_midnight(), "Daily budget used up"
                continue
            task = (await session.execute(
                select(CollectorTask).where(CollectorTask.provider == name, CollectorTask.status == "pending")
                .order_by(CollectorTask.priority, CollectorTask.id).limit(1).with_for_update(skip_locked=True)
            )).scalar_one_or_none()
            if task is None:
                runtime["reason"] = "Queue empty"
                continue
            outcome = await run_task(session, provider, task, client)
            await session.commit()
            ran += 1
            runtime.update({"last_at": datetime.now(UTC), "last_task": task.label, "last_outcome": outcome,
                            "reason": None, "next_at": datetime.now(UTC) + timedelta(seconds=provider.min_interval_s)})
            if outcome == "quota":
                runtime["paused_until"], runtime["reason"] = _next_utc_midnight(), "Provider says today's quota is used up"
            elif outcome == "auth":
                runtime["paused_until"] = datetime.now(UTC) + timedelta(hours=1)
                runtime["reason"] = "Key refused; check it in .env"
            elif outcome == "retry":
                runtime["next_at"] = datetime.now(UTC) + timedelta(seconds=60)
    return ran


async def loop() -> None:
    load_dotenv(ENV_FILE)
    await asyncio.sleep(25)  # let the server finish starting
    planned_on: date | None = None
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "SportsAnalyzer/0.1 (personal research)"}) as client:
        while True:
            try:
                if planned_on != utc_today():  # re-plan daily: new season tasks, new fixtures
                    async with AsyncSessionFactory() as session:
                        if (await get_state(session))["enabled"]:
                            await plan(session)
                            await session.commit()
                            planned_on = utc_today()
                await tick(client)
            except Exception:
                log.exception("collector tick failed")
                await asyncio.sleep(30)
            await asyncio.sleep(1)


async def overview(session: AsyncSession) -> dict[str, Any]:
    """Everything the Data Sources page shows about the collector."""
    state = await get_state(session)
    counts = (await session.execute(
        select(CollectorTask.provider, CollectorTask.status, func.count()).group_by(CollectorTask.provider, CollectorTask.status)
    )).all()
    by_provider: dict[str, dict[str, int]] = {}
    for provider, status, n in counts:
        by_provider.setdefault(provider, {})[status] = n
    usage = {row.provider: row for row in (await session.execute(
        select(ProviderUsage).where(ProviderUsage.day == utc_today()))).scalars().all()}
    providers = []
    for name, p in PROVIDERS.items():
        runtime = RUNTIME[name]
        u = usage.get(name)
        recent = (await session.execute(
            select(CollectorTask).where(CollectorTask.provider == name, CollectorTask.done_at.is_not(None))
            .order_by(CollectorTask.done_at.desc()).limit(5))).scalars().all()
        providers.append({
            "name": name, "label": p.label, "plan": p.plan, "collects": p.collects, "signup_url": p.signup_url,
            "needs_key": p.key_env is not None, "key_env": p.key_env, "configured": p.configured(),
            "plan_daily_limit": p.plan_daily_limit, **state["providers"][name],
            "used_today": u.requests if u else 0, "errors_today": u.errors if u else 0,
            "remaining_reported": u.remaining_reported if u else None,
            "queue": by_provider.get(name, {}),
            "paused_until": runtime.get("paused_until"), "reason": runtime.get("reason"),
            "last_at": runtime.get("last_at"), "last_task": runtime.get("last_task"),
            "recent": [{"label": t.label, "status": t.status, "items": t.items, "error": t.error, "done_at": t.done_at}
                       for t in recent],
        })
    return {"enabled": state["enabled"], "providers": providers}


async def reset_failed(session: AsyncSession, provider: str) -> int:
    result = await session.execute(update(CollectorTask).where(
        CollectorTask.provider == provider, CollectorTask.status == "failed").values(status="pending", attempts=0))
    return result.rowcount or 0
