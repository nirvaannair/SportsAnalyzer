"""Walk-forward backtest and live predictions for the Elo, Dixon-Coles and blended models.

Walk-forward: for every week, fit using only matches played before that week, then
predict that week's matches. This is exactly what the model could have known at the time.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from backend.core.settings import cfg
from backend.models.data import assert_odds_free
from backend.models.dixon_coles import DixonColesModel, DixonColesParams
from backend.models.elo import EloOutcomeModel, pre_match_ratings

MODELS = ("elo", "dixon_coles", "blend")


def _elo_predictions(matches: pd.DataFrame, cutoffs: list[pd.Timestamp]) -> pd.DataFrame:
    """Elo 1X2 for matches in each [cutoff, next cutoff); outcome mapping refit at each cutoff."""
    ratings = matches[["match_id", "date", "status", "home_goals", "away_goals"]].merge(
        pre_match_ratings(matches), on="match_id"
    )
    first_day = matches["date"].min() + pd.Timedelta(days=cfg("elo.warmup_days"))
    parts = []
    for start, end in zip(cutoffs, cutoffs[1:] + [pd.Timestamp.max], strict=True):
        target = ratings[(ratings["date"] >= start) & (ratings["date"] < end)]
        if target.empty:
            continue
        before = ratings[(ratings["status"] == "finished") & (ratings["date"] < start)].dropna(
            subset=["home_goals", "away_goals"])
        train = before[before["date"] >= first_day]
        if len(train) < 200:  # short history: use everything rather than nothing
            train = before
        model = EloOutcomeModel().fit(train["elo_home"], train["elo_away"],
                                      train["home_goals"], train["away_goals"])
        proba = model.predict(target["elo_home"], target["elo_away"])
        parts.append(pd.DataFrame({
            "match_id": target["match_id"].to_numpy(),
            "p_home": proba[:, 0], "p_draw": proba[:, 1], "p_away": proba[:, 2],
        }))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _dixon_coles_predictions(matches: pd.DataFrame, cutoffs: list[pd.Timestamp],
                             params: DixonColesParams,
                             progress: Callable[[str], None]) -> pd.DataFrame:
    """Refit per country at each cutoff; predict that country's matches until the next cutoff."""
    rows = []
    for country, country_matches in matches.groupby("country"):
        fits = 0
        for start, end in zip(cutoffs, cutoffs[1:] + [pd.Timestamp.max], strict=True):
            target = country_matches[(country_matches["date"] >= start) & (country_matches["date"] < end)]
            if target.empty:
                continue
            model = DixonColesModel(params).fit(country_matches, as_of=start)
            fits += 1
            for m in target.itertuples(index=False):
                rows.append({"match_id": m.match_id, **model.predict(m.home_id, m.away_id, m.tier)})
        progress(f"  Dixon-Coles {country}: {fits} weekly fits")
    return pd.DataFrame(rows)


def weekly_cutoffs(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    """Mondays from `start` to `end` inclusive."""
    first = start - pd.Timedelta(days=start.weekday())
    return list(pd.date_range(first, end, freq="7D"))


def run_backtest(matches: pd.DataFrame, start: pd.Timestamp,
                 params: DixonColesParams | None = None,
                 progress: Callable[[str], None] = lambda _: None) -> dict[str, pd.DataFrame]:
    """Predictions for every finished match from `start`, for each model."""
    assert_odds_free(matches.columns)
    finished_end = matches.loc[matches["status"] == "finished", "date"].max()
    cutoffs = weekly_cutoffs(start, finished_end)
    if not cutoffs:
        raise ValueError(f"No finished matches after {start.date()} to backtest on.")
    progress(f"Walk-forward from {start.date()} to {finished_end.date()}: {len(cutoffs)} weeks")

    in_scope = matches[(matches["date"] >= cutoffs[0]) & (matches["status"] == "finished")]
    elo = _elo_predictions(matches, cutoffs)
    elo = elo[elo["match_id"].isin(in_scope["match_id"])]
    progress(f"  Elo: {len(elo)} predictions")
    dc = _dixon_coles_predictions(matches[matches["date"] <= finished_end], cutoffs,
                                  params or DixonColesParams(), progress)
    dc = dc[dc["match_id"].isin(in_scope["match_id"])]
    return {"elo": elo, "dixon_coles": dc, "blend": blend(elo, dc)}


def blend(elo: pd.DataFrame, dc: pd.DataFrame) -> pd.DataFrame:
    """Average Elo and Dixon-Coles 1X2; Over/Under and BTTS come from Dixon-Coles."""
    merged = dc.merge(elo, on="match_id", suffixes=("", "_elo"))
    for column in ("p_home", "p_draw", "p_away"):
        merged[column] = (merged[column] + merged[f"{column}_elo"]) / 2
    return merged.drop(columns=["p_home_elo", "p_draw_elo", "p_away_elo"])


def live_predictions(matches: pd.DataFrame, as_of: pd.Timestamp,
                     params: DixonColesParams | None = None) -> dict[str, pd.DataFrame]:
    """Predictions for every not-yet-finished match, using all results known before `as_of`.

    Includes matches from the past week whose result has not been published yet.
    """
    assert_odds_free(matches.columns)
    window_start = as_of - pd.Timedelta(days=7)
    upcoming = matches[(matches["status"] == "scheduled") & (matches["date"] >= window_start)]
    if upcoming.empty:
        return {name: pd.DataFrame() for name in MODELS}

    elo = _elo_predictions(matches, [window_start])
    elo = elo[elo["match_id"].isin(upcoming["match_id"])]

    rows = []
    for country, target in upcoming.groupby("country"):
        model = DixonColesModel(params).fit(matches[matches["country"] == country], as_of=as_of)
        for m in target.itertuples(index=False):
            rows.append({"match_id": m.match_id, **model.predict(m.home_id, m.away_id, m.tier)})
    dc = pd.DataFrame(rows)
    return {"elo": elo, "dixon_coles": dc, "blend": blend(elo, dc)}


def outcome_index(home_goals: np.ndarray, away_goals: np.ndarray) -> np.ndarray:
    """0 = home win, 1 = draw, 2 = away win."""
    return np.where(home_goals > away_goals, 0, np.where(home_goals == away_goals, 1, 2))
