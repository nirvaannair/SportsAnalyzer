"""Elo ratings with home advantage and goal-difference scaling, mapped to 1X2 probabilities.

Ratings are updated match by match in date order, so every rating used for a prediction
only reflects matches played before it (point-in-time by construction).
Teams keep one rating across divisions, so promotion and relegation are handled naturally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from backend.models.data import assert_odds_free


@dataclass
class EloParams:
    k: float = 20.0
    home_advantage: float = 65.0
    start_rating_by_tier: dict[int, float] = field(default_factory=lambda: {1: 1500.0, 2: 1350.0})
    season_regression: float = 0.2  # pull ratings 20% back to their league mean between seasons


def _goal_multiplier(goal_diff: int) -> float:
    return 1.0 if goal_diff <= 1 else float(np.log(goal_diff + 1) * 1.45)


def pre_match_ratings(matches: pd.DataFrame, params: EloParams | None = None) -> pd.DataFrame:
    """Return match_id plus home/away Elo *before* each match, processing in date order.

    Scheduled matches get the latest ratings without updating them.
    """
    assert_odds_free(matches.columns)
    p = params or EloParams()
    ratings: dict[int, float] = {}
    season_of: dict[int, int] = {}
    out_home = np.empty(len(matches))
    out_away = np.empty(len(matches))

    ordered = matches.sort_values(["date", "match_id"])
    for i, row in enumerate(ordered.itertuples(index=False)):
        for team in (row.home_id, row.away_id):
            if team not in ratings:
                ratings[team] = p.start_rating_by_tier.get(row.tier, 1350.0)
            elif season_of.get(team) != row.season:
                # new season: regress towards the starting level of the team's current tier
                base = p.start_rating_by_tier.get(row.tier, 1350.0)
                ratings[team] = ratings[team] + p.season_regression * (base - ratings[team])
            season_of[team] = row.season

        rh, ra = ratings[row.home_id], ratings[row.away_id]
        out_home[i], out_away[i] = rh, ra

        if row.status == "finished" and pd.notna(row.home_goals) and pd.notna(row.away_goals):
            expected_home = 1.0 / (1.0 + 10 ** ((ra - rh - p.home_advantage) / 400.0))
            hg, ag = int(row.home_goals), int(row.away_goals)
            actual = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
            change = p.k * _goal_multiplier(abs(hg - ag)) * (actual - expected_home)
            ratings[row.home_id] = rh + change
            ratings[row.away_id] = ra - change

    return pd.DataFrame({
        "match_id": ordered["match_id"].to_numpy(),
        "elo_home": out_home,
        "elo_away": out_away,
    })


class EloOutcomeModel:
    """Maps the Elo difference (plus home advantage) to home/draw/away probabilities.

    A multinomial logistic regression on one feature: the rating gap. Fitted only on
    matches before the prediction cutoff.
    """

    def __init__(self, home_advantage: float = EloParams().home_advantage) -> None:
        self.home_advantage = home_advantage
        self._model = LogisticRegression(max_iter=1000)

    def _x(self, elo_home, elo_away) -> np.ndarray:
        return ((np.asarray(elo_home) + self.home_advantage - np.asarray(elo_away)) / 100.0).reshape(-1, 1)

    def fit(self, elo_home, elo_away, home_goals, away_goals) -> EloOutcomeModel:
        hg, ag = np.asarray(home_goals), np.asarray(away_goals)
        y = np.where(hg > ag, 0, np.where(hg == ag, 1, 2))  # 0 home, 1 draw, 2 away
        self._model.fit(self._x(elo_home, elo_away), y)
        return self

    def predict(self, elo_home, elo_away) -> np.ndarray:
        """Array of shape (n, 3): P(home), P(draw), P(away)."""
        proba = self._model.predict_proba(self._x(elo_home, elo_away))
        order = np.argsort(self._model.classes_)
        return proba[:, order]
