"""Money safety rules for real Stake bets. Enforced by the local app, not by the browser helper.

Every check runs again at the moment a bet is handed to the helper, so a stale approval
or a changed setting can never push a bet past the limits.

Limits come from .env (defaults are deliberately tiny for the testing phase):
    STAKE_MAX_BET=1              per bet, in STAKE_CURRENCY
    STAKE_TEST_BUDGET=20         total that may ever be sent to Stake
    STAKE_MAX_BETS_PER_DAY=10
    STAKE_APPROVAL_ABOVE=1000    bets above this always wait for your click, even in Auto mode
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_bet: float
    budget: float
    max_bets_per_day: int
    currency: str
    approval_above: float = 1000.0

    @classmethod
    def from_env(cls) -> Limits:
        def number(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, "") or default)
            except ValueError:
                return default

        return cls(
            max_bet=number("STAKE_MAX_BET", 1.0),
            budget=number("STAKE_TEST_BUDGET", 20.0),
            max_bets_per_day=int(number("STAKE_MAX_BETS_PER_DAY", 10)),
            currency=(os.getenv("STAKE_CURRENCY", "inr").strip().lower() or "inr"),
            approval_above=number("STAKE_APPROVAL_ABOVE", 1000.0),
        )


@dataclass(frozen=True)
class Exposure:
    spent_total: float  # amount already sent or placed (all time)
    bets_today: int


class GuardrailError(ValueError):
    """A bet that must not be placed. The message is shown on the dashboard."""


def check_new_order(amount: float, currency: str, limits: Limits) -> None:
    if amount <= 0:
        raise GuardrailError("Stake must be more than zero.")
    if currency.lower() != limits.currency:
        raise GuardrailError(f"Only {limits.currency.upper()} bets are allowed.")
    if amount > limits.max_bet:
        raise GuardrailError(f"₹{amount:g} is above the per-bet limit of ₹{limits.max_bet:g}.")


def check_dispatch(amount: float, currency: str, limits: Limits, exposure: Exposure, enabled: bool) -> None:
    """Final gate before a bet goes to the helper."""
    if not enabled:
        raise GuardrailError("Execution is switched off on the Stake page.")
    check_new_order(amount, currency, limits)
    if exposure.spent_total + amount > limits.budget + 1e-9:
        raise GuardrailError(
            f"Budget reached: ₹{exposure.spent_total:g} of ₹{limits.budget:g} already used.")
    if exposure.bets_today >= limits.max_bets_per_day:
        raise GuardrailError(f"Daily limit reached ({limits.max_bets_per_day} bets).")


def needs_approval(amount: float, limits: Limits) -> bool:
    """Large bets always wait for a human click, whatever the strategy's mode."""
    return amount > limits.approval_above
