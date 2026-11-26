"""Point-in-time match features for the trained ML models. Football data only, never odds.

Every feature for a match is computed from matches played strictly *before* it
(per-team histories are shifted by one match), so a model trained on them could have
been run on the morning of the match. tests/test_ml.py checks this.

The input is the frame from backend.models.data.load_matches (already odds-free); the
output columns are listed in FEATURE_COLUMNS and checked again by assert_features_odds_free.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from backend.models.data import OddsLeakError, assert_odds_free
from backend.models.elo import pre_match_ratings
from backend.models.players import PLAYER_FEATURES, player_features

# Per-team stats tracked over recent matches (for = scored by the team, against = conceded).
_TEAM_STATS = ("gf", "ga", "sf", "sa", "stf", "sta", "cf", "ca", "pts")
_WINDOWS = (5, 10)
_EWM_HALFLIFE = 8  # matches
SIDE_FEATURES: tuple[str, ...] = (
    *(f"{stat}_l{w}" for w in _WINDOWS for stat in _TEAM_STATS),
    *(f"{stat}_ewm" for stat in ("gf", "ga", "stf", "sta", "pts")),
    "venue_gf_l5", "venue_ga_l5", "venue_pts_l5",  # home form for the home team, away form for the away team
    "rest_days", "played_season", "played_total", "elo",
    # opponent-adjusted ratings (see _strength_ratings) and finishing
    "att", "def", "sot_att", "sot_def", "finishing_l10",
    # from lineups (backend/models/players.py); NaN where no lineup data yet
    *PLAYER_FEATURES,
    # from news articles in the 7 days before kickoff; NaN where no news collected yet
    "news_n7", "news_sentiment7", "news_injury7",
)
NEWS_FEATURES: tuple[str, ...] = ("news_n7", "news_sentiment7", "news_injury7")
# Groups the Training page can switch on/off per run (switched off = blanked, as if never seen).
FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "players": tuple(f"{side}_{f}" for side in ("home", "away") for f in PLAYER_FEATURES),
    "news": tuple(f"{side}_{f}" for side in ("home", "away") for f in NEWS_FEATURES),
}


def apply_feature_groups(feats: pd.DataFrame, enabled: dict[str, bool]) -> pd.DataFrame:
    """Blank out the feature groups that are switched off."""
    feats = feats.copy()
    for group, columns in FEATURE_GROUPS.items():
        if not enabled.get(group, False):
            feats[list(columns)] = np.nan
    return feats


def _news_features(matches: pd.DataFrame, news: pd.DataFrame, days: int = 7) -> pd.DataFrame:
    """Per team, news published in the `days` before the match day (strictly before it)."""
    columns = ["match_id", *(f"{side}_{f}" for side in ("home", "away") for f in NEWS_FEATURES)]
    if news is None or news.empty:
        return pd.DataFrame(columns=columns)
    out = {"match_id": matches["match_id"].to_numpy()}
    news = news.sort_values("published_at")
    by_team = {}
    for team, g in news.groupby("team_id"):
        t = g["published_at"].to_numpy(dtype="datetime64[ns]")
        w = g["weight"].to_numpy(dtype=float)
        by_team[int(team)] = (t, np.concatenate([[0], np.cumsum(w)]),
                              np.concatenate([[0], np.cumsum(w * g["sentiment"].to_numpy(dtype=float))]),
                              np.concatenate([[0], np.cumsum(w * g["injury"].to_numpy(dtype=float))]))
    day = matches["date"].to_numpy(dtype="datetime64[ns]")
    start = day - np.timedelta64(days, "D")
    for side in ("home", "away"):
        n_col, s_col, i_col = (np.full(len(matches), np.nan) for _ in range(3))
        for i, team in enumerate(matches[f"{side}_id"].to_numpy()):
            data = by_team.get(int(team))
            if data is None:
                continue
            t, cw, cs, ci = data
            lo, hi = np.searchsorted(t, start[i]), np.searchsorted(t, day[i])  # [day-7, day)
            weight = cw[hi] - cw[lo]
            n_col[i] = weight
            s_col[i] = (cs[hi] - cs[lo]) / weight if weight > 0 else np.nan
            i_col[i] = ci[hi] - ci[lo]
        out[f"{side}_news_n7"], out[f"{side}_news_sentiment7"], out[f"{side}_news_injury7"] = n_col, s_col, i_col
    return pd.DataFrame(out)
MATCH_FEATURES: tuple[str, ...] = (
    "elo_diff", "tier", "season_progress", "month", "league_code",
    "rating_xg_home", "rating_xg_away", "rating_sot_home", "rating_sot_away",
    "h2h_n", "h2h_gd", "h2h_goals",
)
FEATURE_COLUMNS: tuple[str, ...] = (
    *(f"home_{f}" for f in SIDE_FEATURES),
    *(f"away_{f}" for f in SIDE_FEATURES),
    *MATCH_FEATURES,
)
TARGET_COLUMNS: tuple[str, ...] = ("y_1x2", "y_over25", "y_btts", "home_goals", "away_goals")
LEAGUE_CODES = ("ENG1", "ENG2", "ESP1", "ESP2", "ITA1", "ITA2", "GER1", "GER2", "FRA1", "FRA2")

_ODDS_PATTERN = re.compile(r"odd|price|implied|market|bookmaker|b365|pinnacle|closing|margin", re.I)


def assert_features_odds_free(columns) -> None:
    for column in columns:
        if _ODDS_PATTERN.search(str(column)):
            raise OddsLeakError(f"Feature {column!r} looks odds-derived; models must not use odds.")


def _team_long(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per (match, team): what the team did in that match."""
    def side(is_home: bool) -> pd.DataFrame:
        me, op = ("home", "away") if is_home else ("away", "home")
        goals_for, goals_against = matches[f"{me}_goals"], matches[f"{op}_goals"]
        points = np.where(goals_for > goals_against, 3.0, np.where(goals_for == goals_against, 1.0, 0.0))
        points = np.where(goals_for.isna() | goals_against.isna(), np.nan, points)
        return pd.DataFrame({
            "match_id": matches["match_id"], "date": matches["date"], "season": matches["season"],
            "team": matches[f"{me}_id"], "is_home": is_home,
            "gf": goals_for, "ga": goals_against,
            "sf": matches[f"{me}_shots"], "sa": matches[f"{op}_shots"],
            "stf": matches[f"{me}_shots_target"], "sta": matches[f"{op}_shots_target"],
            "cf": matches[f"{me}_corners"], "ca": matches[f"{op}_corners"],
            "pts": points,
        })

    long = pd.concat([side(True), side(False)], ignore_index=True)
    for column in _TEAM_STATS:
        long[column] = pd.to_numeric(long[column], errors="coerce").astype(float)
    return long.sort_values(["team", "date", "match_id"], kind="mergesort").reset_index(drop=True)


def _rolling_prior(grouped, column: str, window: int) -> pd.Series:
    """Mean over the team's previous `window` matches (the current match excluded)."""
    return grouped[column].transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())


def _strength_ratings(matches: pd.DataFrame, home_col: str, away_col: str, prefix: str,
                      k: float = 0.06, k_mu: float = 0.01) -> pd.DataFrame:
    """Online attack/defence ratings on a count (goals or shots on target), opponent-adjusted.

    log E[home count] = mu[league] + home_adv[league] + att[home] - def[away]
    log E[away count] = mu[league] + att[away] - def[home]
    Updated after each match in date order, so the values recorded for a match only reflect
    earlier matches. Teams carry their ratings across divisions (promotion/relegation), which
    keeps one strength scale across leagues.
    """
    att: dict[int, float] = {}
    dfn: dict[int, float] = {}
    mu: dict[str, float] = {}
    home_adv: dict[str, float] = {}
    tier_start = {1: 0.0, 2: -0.25}
    ordered = matches.sort_values(["date", "match_id"])
    n = len(ordered)
    out = {f"home_{prefix}att": np.empty(n), f"home_{prefix}def": np.empty(n),
           f"away_{prefix}att": np.empty(n), f"away_{prefix}def": np.empty(n),
           "exp_home": np.empty(n), "exp_away": np.empty(n)}
    hv, av = ordered[home_col].to_numpy(dtype=float), ordered[away_col].to_numpy(dtype=float)
    for i, row in enumerate(ordered.itertuples(index=False)):
        league = row.league
        start = tier_start.get(row.tier, -0.25)
        for team in (row.home_id, row.away_id):
            att.setdefault(team, start)
            dfn.setdefault(team, start)
        m = mu.setdefault(league, float(np.log(1.3 if prefix == "" else 4.2)))
        h = home_adv.setdefault(league, 0.2)
        a_h, d_h, a_a, d_a = att[row.home_id], dfn[row.home_id], att[row.away_id], dfn[row.away_id]
        exp_h, exp_a = np.exp(m + h + a_h - d_a), np.exp(m + a_a - d_h)
        out[f"home_{prefix}att"][i], out[f"home_{prefix}def"][i] = a_h, d_h
        out[f"away_{prefix}att"][i], out[f"away_{prefix}def"][i] = a_a, d_a
        out["exp_home"][i], out["exp_away"][i] = exp_h, exp_a
        if row.status == "finished" and np.isfinite(hv[i]) and np.isfinite(av[i]):
            # Error relative to expectation, scaled so big counts (shots) and small (goals) move alike.
            err_h, err_a = (hv[i] - exp_h) / max(exp_h, 0.5), (av[i] - exp_a) / max(exp_a, 0.5)
            att[row.home_id] = a_h + k * err_h
            dfn[row.away_id] = d_a - k * err_h
            att[row.away_id] = a_a + k * err_a
            dfn[row.home_id] = d_h - k * err_a
            mu[league] = m + k_mu * (err_h + err_a) / 2
            home_adv[league] = h + k_mu * (err_h - err_a) / 2
    frame = pd.DataFrame({"match_id": ordered["match_id"].to_numpy(), **out})
    label = "xg" if prefix == "" else "sot"
    return frame.rename(columns={"exp_home": f"rating_{label}_home", "exp_away": f"rating_{label}_away"})


def _head_to_head(matches: pd.DataFrame, last: int = 6) -> pd.DataFrame:
    """Previous meetings of the same two teams (either venue), from the home side's view."""
    history: dict[tuple[int, int], list[tuple[float, float]]] = {}
    rows = []
    for m in matches.sort_values(["date", "match_id"]).itertuples(index=False):
        key = (min(m.home_id, m.away_id), max(m.home_id, m.away_id))
        past = history.get(key, [])[-last:]
        sign = 1 if m.home_id == key[0] else -1
        if past:
            gds = [sign * (a - b) for a, b in past]  # stored as (key[0] goals, key[1] goals)
            rows.append((m.match_id, len(past), float(np.mean(gds)), float(np.mean([a + b for a, b in past]))))
        else:
            rows.append((m.match_id, 0, np.nan, np.nan))
        if m.status == "finished" and pd.notna(m.home_goals) and pd.notna(m.away_goals):
            hg, ag = float(m.home_goals), float(m.away_goals)
            history.setdefault(key, []).append((hg, ag) if sign == 1 else (ag, hg))
    return pd.DataFrame(rows, columns=["match_id", "h2h_n", "h2h_gd", "h2h_goals"]).astype({"h2h_n": float})


def build_features(matches: pd.DataFrame, lineups: pd.DataFrame | None = None,
                   goal_events: pd.DataFrame | None = None, news: pd.DataFrame | None = None) -> pd.DataFrame:
    """match_id + FEATURE_COLUMNS + targets (targets NaN for unplayed matches).

    `lineups`/`goal_events` come from backend.models.data.load_lineups; without them the player
    features are all missing.
    """
    assert_odds_free(matches.columns)
    long = _team_long(matches)
    by_team = long.groupby("team", sort=False)

    feats = long[["match_id", "team", "is_home"]].copy()
    for w in _WINDOWS:
        for stat in _TEAM_STATS:
            feats[f"{stat}_l{w}"] = _rolling_prior(by_team, stat, w)
    for stat in ("gf", "ga", "stf", "sta", "pts"):
        feats[f"{stat}_ewm"] = by_team[stat].transform(
            lambda s: s.shift(1).ewm(halflife=_EWM_HALFLIFE, ignore_na=True).mean())

    by_venue = long.groupby(["team", "is_home"], sort=False)
    for stat in ("gf", "ga", "pts"):
        feats[f"venue_{stat}_l5"] = _rolling_prior(by_venue, stat, 5)

    feats["rest_days"] = by_team["date"].diff().dt.days.clip(upper=30).astype(float)
    played = long["gf"].notna().astype(float)
    feats["played_total"] = played.groupby(long["team"]).transform(lambda s: s.shift(1).cumsum()).fillna(0)
    feats["played_season"] = played.groupby([long["team"], long["season"]]).transform(
        lambda s: s.shift(1).cumsum()).fillna(0)

    home = feats[feats["is_home"]].drop(columns=["team", "is_home"])
    away = feats[~feats["is_home"]].drop(columns=["team", "is_home"])
    home = home.rename(columns={c: f"home_{c}" for c in home.columns if c != "match_id"})
    away = away.rename(columns={c: f"away_{c}" for c in away.columns if c != "match_id"})

    elo = pre_match_ratings(matches).rename(columns={"elo_home": "home_elo", "elo_away": "away_elo"})
    out = matches[["match_id", "date", "season", "league", "tier", "status", "home_goals", "away_goals"]] \
        .merge(home, on="match_id").merge(away, on="match_id").merge(elo, on="match_id")
    goals = _strength_ratings(matches, "home_goals", "away_goals", prefix="")
    sot = _strength_ratings(matches, "home_shots_target", "away_shots_target", prefix="sot_")
    out = out.merge(goals, on="match_id").merge(sot, on="match_id").merge(_head_to_head(matches), on="match_id")
    if lineups is not None and not lineups.empty:
        players = player_features(matches, lineups, goal_events if goal_events is not None else pd.DataFrame(
            columns=["match_id", "team_id", "minute", "kind"]))
        out = out.merge(players, on="match_id", how="left")
    if news is not None and not news.empty:
        out = out.merge(_news_features(matches, news), on="match_id", how="left")
    for side in ("home", "away"):
        for f in (*PLAYER_FEATURES, *NEWS_FEATURES):
            if f"{side}_{f}" not in out:
                out[f"{side}_{f}"] = np.nan
        cols = [f"{side}_{f}" for f in (*PLAYER_FEATURES, *NEWS_FEATURES)]
        out[cols] = out[cols].astype(float)
    for side in ("home", "away"):
        out[f"{side}_finishing_l10"] = out[f"{side}_gf_l10"] / out[f"{side}_stf_l10"].where(out[f"{side}_stf_l10"] > 0)
    out["elo_diff"] = out["home_elo"] - out["away_elo"]
    out["tier"] = out["tier"].astype(float)
    out["month"] = out["date"].dt.month.astype(float)
    # Share of a typical season played so far (46 matches in second tiers like ENG2, ~38 elsewhere).
    out["season_progress"] = ((out["home_played_season"] + out["away_played_season"]) / 2 / 40).clip(upper=1.2)
    out["league_code"] = out["league"].map({c: i for i, c in enumerate(LEAGUE_CODES)}).fillna(-1).astype(float)

    hg, ag = out["home_goals"].astype(float), out["away_goals"].astype(float)
    done = hg.notna() & ag.notna()
    out["y_1x2"] = np.where(done, np.where(hg > ag, 0, np.where(hg == ag, 1, 2)), np.nan)
    out["y_over25"] = np.where(done, (hg + ag > 2.5).astype(float), np.nan)
    out["y_btts"] = np.where(done, ((hg > 0) & (ag > 0)).astype(float), np.nan)
    out["home_goals"], out["away_goals"] = hg, ag

    assert_features_odds_free(out.columns)
    return out.sort_values(["date", "match_id"]).reset_index(drop=True)
