"""Model behaviour on synthetic seasons where the truth is known."""

import numpy as np
import pandas as pd
import pytest

from backend.evaluation.metrics import calibration, evaluate, score_1x2, simulate_bets
from backend.models.backtest import blend, weekly_cutoffs
from backend.models.dixon_coles import DixonColesModel
from backend.models.elo import EloOutcomeModel, pre_match_ratings


def synthetic_league(seasons: int = 3, seed: int = 1) -> pd.DataFrame:
    """10 teams with known strengths; team 0 strongest, team 9 weakest. Double round robin."""
    rng = np.random.default_rng(seed)
    attack = np.linspace(0.5, -0.5, 10)
    defence = np.linspace(0.4, -0.4, 10)
    rows, match_id, day = [], 1, pd.Timestamp("2020-08-01")
    for season in range(seasons):
        for h in range(10):
            for a in range(10):
                if h == a:
                    continue
                lam = np.exp(0.15 + 0.25 + attack[h] - defence[a])
                mu = np.exp(0.15 + attack[a] - defence[h])
                rows.append({
                    "match_id": match_id, "date": day, "league": "TST1", "country": "Testland", "tier": 1,
                    "season": 2020 + season, "home_id": h, "away_id": a, "status": "finished",
                    "home_goals": int(rng.poisson(lam)), "away_goals": int(rng.poisson(mu)),
                })
                match_id += 1
                day += pd.Timedelta(days=1)
    frame = pd.DataFrame(rows)
    for column in ("home_shots", "away_shots", "home_shots_target", "away_shots_target",
                   "home_corners", "away_corners", "home_red", "away_red"):
        frame[column] = None
    return frame


def test_dixon_coles_recovers_team_order_and_home_advantage() -> None:
    league = synthetic_league()
    model = DixonColesModel().fit(league, as_of=league["date"].max() + pd.Timedelta(days=1))
    attack = [model.attack[model.teams[t]] for t in range(10)]
    assert np.corrcoef(attack, np.linspace(0.5, -0.5, 10))[0, 1] > 0.9
    assert 0.1 < model.home < 0.4

    strong_home = model.predict(0, 9, tier=1)
    assert strong_home["p_home"] > 0.6
    assert abs(strong_home["p_home"] + strong_home["p_draw"] + strong_home["p_away"] - 1) < 1e-9
    assert 0 < strong_home["p_over25"] < 1 and 0 < strong_home["p_btts"] < 1


def test_dixon_coles_ignores_future_matches() -> None:
    league = synthetic_league()
    cutoff = pd.Timestamp("2021-06-01")
    a = DixonColesModel().fit(league, as_of=cutoff).predict(0, 9, 1)
    tampered = league.copy()
    tampered.loc[tampered["date"] >= cutoff, ["home_goals", "away_goals"]] = [0, 9]
    b = DixonColesModel().fit(tampered, as_of=cutoff).predict(0, 9, 1)
    assert a == pytest.approx(b)


def test_unknown_team_is_treated_as_weak() -> None:
    league = synthetic_league(seasons=1)
    model = DixonColesModel().fit(league, as_of=league["date"].max() + pd.Timedelta(days=1))
    assert model.predict(0, 999, tier=1)["p_home"] > model.predict(0, 5, tier=1)["p_home"]


def test_elo_ratings_are_pre_match_and_rank_teams() -> None:
    league = synthetic_league()
    ratings = pre_match_ratings(league)
    first = ratings.iloc[0]
    assert first["elo_home"] == first["elo_away"] == 1500.0  # nothing played yet
    last = league.merge(ratings, on="match_id").tail(90)
    by_team = pd.concat([last[["home_id", "elo_home"]].set_axis(["team", "elo"], axis=1),
                         last[["away_id", "elo_away"]].set_axis(["team", "elo"], axis=1)]).groupby("team")["elo"].mean()
    assert by_team[0] > by_team[9] + 100

    merged = league.merge(ratings, on="match_id")
    model = EloOutcomeModel().fit(merged["elo_home"], merged["elo_away"], merged["home_goals"], merged["away_goals"])
    p = model.predict([1700], [1300])[0]
    assert p[0] > p[2] and abs(p.sum() - 1) < 1e-9


def test_weekly_cutoffs_are_mondays() -> None:
    cutoffs = weekly_cutoffs(pd.Timestamp("2024-08-15"), pd.Timestamp("2024-09-10"))
    assert all(c.weekday() == 0 for c in cutoffs)
    assert cutoffs[0] == pd.Timestamp("2024-08-12")


def test_scores_and_calibration() -> None:
    perfect = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    assert score_1x2(perfect, np.array([0, 1]))["brier"] == pytest.approx(0)
    uniform = np.full((300, 3), 1 / 3)
    outcome = np.repeat([0, 1, 2], 100)
    assert score_1x2(uniform, outcome)["logloss"] == pytest.approx(np.log(3))
    assert all(abs(b["predicted"] - b["observed"]) < 1e-9 for b in calibration(uniform, outcome))


def test_blend_averages_1x2_and_keeps_goal_markets() -> None:
    elo = pd.DataFrame({"match_id": [1], "p_home": [0.6], "p_draw": [0.2], "p_away": [0.2]})
    dc = pd.DataFrame({"match_id": [1], "p_home": [0.4], "p_draw": [0.3], "p_away": [0.3], "p_over25": [0.55],
                       "p_btts": [0.5], "exp_home_goals": [1.5], "exp_away_goals": [1.1]})
    row = blend(elo, dc).iloc[0]
    assert row["p_home"] == pytest.approx(0.5) and row["p_over25"] == 0.55


def test_simulated_bets_use_price_only_as_payout() -> None:
    preds = pd.DataFrame({"match_id": [1, 2], "p_home": [0.6, 0.3], "p_draw": [0.2, 0.3], "p_away": [0.2, 0.4]})
    results = pd.DataFrame({"match_id": [1, 2], "home_goals": [2, 0], "away_goals": [0, 1]})
    prices = pd.DataFrame({"match_id": [1, 2], "1x2_home": [2.0, 3.0], "1x2_draw": [3.0, 3.0], "1x2_away": [4.0, 2.0]})
    # match 1: home edge 0.6*2-1=0.2 (won, +1); match 2: none above 3%... away 0.4*2-1=-0.2
    (row,) = [r for r in simulate_bets(preds, results, prices) if r["edge_threshold"] == 0.05]
    assert row == {"market": "1x2", "edge_threshold": 0.05, "bets": 1, "profit_units": 1.0, "roi": 1.0}


def test_evaluate_end_to_end_on_backtest_output() -> None:
    from backend.models.backtest import run_backtest

    league = synthetic_league(seasons=3)
    preds = run_backtest(league, pd.Timestamp("2021-01-04"))
    results = league[["match_id", "home_goals", "away_goals", "season", "league"]]
    prices = pd.DataFrame({"match_id": league["match_id"], "1x2_home": 2.0, "1x2_draw": 3.4, "1x2_away": 3.8,
                           "ou25_over": 1.9, "ou25_under": 1.9})
    for model in ("elo", "dixon_coles", "blend"):
        metrics = evaluate(preds[model], results, prices)
        assert metrics["n"] == len(preds[model]) > 50
        assert metrics["1x2"]["logloss"] < np.log(3)
    dc = evaluate(preds["dixon_coles"], results, prices)
    assert dc["1x2"]["logloss"] < dc["baseline_1x2"]["logloss"]  # beats "always the average"
    assert "ou25_logloss" in dc and dc["simulated_bets"]
