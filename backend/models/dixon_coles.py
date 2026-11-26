"""Time-weighted Dixon-Coles goals model.

Each team gets an attack and a defence strength; home advantage is shared. Expected goals:

    log λ_home = μ + home + attack[home] − defence[away]
    log λ_away = μ + attack[away] − defence[home]

Goals are Poisson with the Dixon-Coles correction (rho) for 0-0, 1-0, 0-1 and 1-1, which
plain Poisson gets wrong. Older matches count less (exponential decay, half-life ~1 year),
and a small L2 penalty keeps teams with little data near average.

Fitting is done per country over both divisions together, so promoted teams carry their
second-tier form into the first tier on one consistent scale.

The score matrix gives every market at once: 1X2, Over/Under 2.5 and both teams to score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor

from backend.core.settings import cfg
from backend.models.data import assert_odds_free


@dataclass
class DixonColesParams:
    half_life_days: float = field(default_factory=lambda: cfg("dixon_coles.half_life_days"))
    window_days: int = field(default_factory=lambda: cfg("dixon_coles.window_days"))
    l2: float = field(default_factory=lambda: cfg("dixon_coles.l2"))


def _tau(x: np.ndarray, y: np.ndarray, lam: np.ndarray, mu: np.ndarray, rho: float) -> np.ndarray:
    tau = np.ones_like(lam, dtype=float)
    tau = np.where((x == 0) & (y == 0), 1 - lam * mu * rho, tau)
    tau = np.where((x == 0) & (y == 1), 1 + lam * rho, tau)
    tau = np.where((x == 1) & (y == 0), 1 + mu * rho, tau)
    tau = np.where((x == 1) & (y == 1), 1 - rho, tau)
    return tau


class DixonColesModel:
    def __init__(self, params: DixonColesParams | None = None) -> None:
        self.params = params or DixonColesParams()
        self.teams: dict[int, int] = {}
        self.attack = np.zeros(0)
        self.defence = np.zeros(0)
        self.home = 0.0
        self.intercept = 0.0
        self.rho = 0.0
        self.team_tier: dict[int, int] = {}

    def fit(self, matches: pd.DataFrame, as_of: pd.Timestamp) -> DixonColesModel:
        """Fit on finished matches strictly before `as_of`, within the time window."""
        assert_odds_free(matches.columns)
        p = self.params
        train = matches[
            (matches["status"] == "finished")
            & (matches["date"] < as_of)
            & (matches["date"] >= as_of - pd.Timedelta(days=p.window_days))
        ].dropna(subset=["home_goals", "away_goals"])
        if len(train) < 50:
            raise ValueError(f"Not enough matches to fit ({len(train)})")

        team_ids = pd.unique(pd.concat([train["home_id"], train["away_id"]]))
        self.teams = {int(t): i for i, t in enumerate(team_ids)}
        n_teams, n = len(team_ids), len(train)
        hi = train["home_id"].map(self.teams).to_numpy()
        ai = train["away_id"].map(self.teams).to_numpy()

        # Two rows per match (home goals, away goals). Columns: attack[n_teams], -defence[n_teams], home.
        X = np.zeros((2 * n, 2 * n_teams + 1))
        rows = np.arange(n)
        X[rows, hi] = 1
        X[rows, n_teams + ai] = -1
        X[rows, -1] = 1
        X[n + rows, ai] = 1
        X[n + rows, n_teams + hi] = -1
        y = np.concatenate([train["home_goals"].to_numpy(float), train["away_goals"].to_numpy(float)])

        age_days = (as_of - train["date"]).dt.days.to_numpy(float)
        weight = np.exp(-np.log(2) * age_days / p.half_life_days)
        w = np.concatenate([weight, weight])

        glm = PoissonRegressor(alpha=p.l2, max_iter=300)
        glm.fit(X, y, sample_weight=w / w.mean())
        coef = glm.coef_
        self.attack = coef[:n_teams] - coef[:n_teams].mean()
        self.defence = coef[n_teams:2 * n_teams] - coef[n_teams:2 * n_teams].mean()
        self.home = float(coef[-1])
        # Re-centre: the mean shift is absorbed into the intercept.
        self.intercept = float(glm.intercept_ + coef[:n_teams].mean() - coef[n_teams:2 * n_teams].mean())

        # Low-score correction, given the Poisson means.
        lam = np.exp(self.intercept + self.home + self.attack[hi] - self.defence[ai])
        mu = np.exp(self.intercept + self.attack[ai] - self.defence[hi])
        hg, ag = train["home_goals"].to_numpy(int), train["away_goals"].to_numpy(int)

        def neg_ll(rho: float) -> float:
            tau = _tau(hg, ag, lam, mu, rho)
            if np.any(tau <= 0):
                return 1e12
            return -float(np.sum(weight * np.log(tau)))

        self.rho = float(minimize_scalar(neg_ll, bounds=(-0.2, 0.2), method="bounded").x)

        # Remember each team's most recent tier, to place unknown teams sensibly.
        latest = pd.concat([
            train[["date", "home_id", "tier"]].rename(columns={"home_id": "team"}),
            train[["date", "away_id", "tier"]].rename(columns={"away_id": "team"}),
        ]).sort_values("date").groupby("team")["tier"].last()
        self.team_tier = {int(k): int(v) for k, v in latest.items()}
        return self

    def _strength(self, team: int, tier: int) -> tuple[float, float]:
        idx = self.teams.get(int(team))
        if idx is not None:
            return float(self.attack[idx]), float(self.defence[idx])
        # Unknown team (e.g. promoted from outside our data): assume a weak team of that tier.
        same_tier = [self.teams[t] for t, tt in self.team_tier.items() if tt == tier and t in self.teams]
        pool = same_tier or list(self.teams.values())
        return float(np.percentile(self.attack[pool], 20)), float(np.percentile(self.defence[pool], 20))

    def expected_goals(self, home: int, away: int, tier: int) -> tuple[float, float]:
        ah, dh = self._strength(home, tier)
        aa, da = self._strength(away, tier)
        lam = float(np.exp(self.intercept + self.home + ah - da))
        mu = float(np.exp(self.intercept + aa - dh))
        return lam, mu

    def score_matrix(self, lam: float, mu: float) -> np.ndarray:
        goals = np.arange(cfg("dixon_coles.max_goals") + 1)
        matrix = np.outer(poisson.pmf(goals, lam), poisson.pmf(goals, mu))
        x, y = np.meshgrid(goals, goals, indexing="ij")
        matrix *= _tau(x, y, np.full_like(matrix, lam), np.full_like(matrix, mu), self.rho)
        return matrix / matrix.sum()

    def predict(self, home: int, away: int, tier: int) -> dict[str, float]:
        lam, mu = self.expected_goals(home, away, tier)
        m = self.score_matrix(lam, mu)
        goals = np.arange(cfg("dixon_coles.max_goals") + 1)
        total = goals[:, None] + goals[None, :]
        return {
            "p_home": float(np.tril(m, -1).sum()),
            "p_draw": float(np.trace(m)),
            "p_away": float(np.triu(m, 1).sum()),
            "p_over25": float(m[total >= 3].sum()),
            "p_btts": float(m[1:, 1:].sum()),
            "exp_home_goals": lam,
            "exp_away_goals": mu,
        }
