"""Trained ML models: point-in-time features, no odds, and training on a synthetic league (CPU)."""

import numpy as np
import pandas as pd
import pytest

from backend.models import ml
from backend.models.data import OddsLeakError
from backend.models.features import FEATURE_COLUMNS, assert_features_odds_free, build_features
from tests.test_models import synthetic_league


def two_leagues(seasons: int = 4) -> pd.DataFrame:
    """Two synthetic leagues (codes ENG1 / ESP1) with different teams."""
    a = synthetic_league(seasons, seed=1).assign(league="ENG1", country="England")
    b = synthetic_league(seasons, seed=2).assign(league="ESP1", country="Spain")
    b["match_id"] += 100_000
    b["home_id"] += 100
    b["away_id"] += 100
    for column in ("home_shots_target", "away_shots_target"):
        a[column] = a["home_goals" if column.startswith("home") else "away_goals"] * 3 + 2
        b[column] = None
    return pd.concat([a, b], ignore_index=True).sort_values(["date", "match_id"]).reset_index(drop=True)


def test_feature_names_have_no_odds() -> None:
    assert_features_odds_free(FEATURE_COLUMNS)
    with pytest.raises(OddsLeakError):
        assert_features_odds_free(["home_elo", "implied_home"])


def test_features_only_use_earlier_matches() -> None:
    """Changing a match's result must not change that match's own features (or earlier ones)."""
    matches = two_leagues(2)
    base = build_features(matches).set_index("match_id")
    target = int(matches.iloc[300]["match_id"])
    changed = matches.copy()
    changed.loc[changed["match_id"] == target, ["home_goals", "away_goals"]] = [9, 0]
    after = build_features(changed).set_index("match_id")
    day = matches.loc[matches["match_id"] == target, "date"].iloc[0]
    upto = matches[matches["date"] <= day]["match_id"]
    cols = list(FEATURE_COLUMNS)
    pd.testing.assert_frame_equal(base.loc[upto, cols], after.loc[upto, cols])
    # ...but a later match of the same home team does see it.
    home = matches.loc[matches["match_id"] == target, "home_id"].iloc[0]
    later = matches[(matches["date"] > day) & ((matches["home_id"] == home) | (matches["away_id"] == home))]
    first_later = int(later.iloc[0]["match_id"])
    assert not base.loc[first_later, cols].equals(after.loc[first_later, cols])


def test_strength_features_rank_teams() -> None:
    feats = build_features(synthetic_league(3)).set_index("match_id")
    # Team 0 (strongest attack) should have a higher attack rating than team 9 by season 3.
    matches = synthetic_league(3)
    late = feats.join(matches.set_index("match_id")[["home_id"]])
    late = late[late["season"] == 2022]
    assert late[late["home_id"] == 0]["home_att"].mean() > late[late["home_id"] == 9]["home_att"].mean()


@pytest.fixture
def small_training(settings_override):
    settings_override({"training": {
        "min_league_rows": 100, "min_train_rows": 100, "warmup_days": 30,
        "xgb": {"rounds": 60, "tune_rounds": 20}, "nn": {"epochs": 4, "tune_epochs": 2},
    }})


@pytest.mark.parametrize("family", ["xgb", "nn"])
def test_walk_forward_trains_and_predicts(family, small_training, tmp_path) -> None:
    pytest.importorskip("xgboost" if family == "xgb" else "torch")
    feats = build_features(two_leagues(4))
    events = []
    preds, chooser = ml.walk_forward(feats, family, 2022, events.append, device="cpu")
    assert set(preds) == {"global", "league", "auto"}
    for frame in preds.values():
        assert len(frame) == len(feats[feats["season"] >= 2022])
        p = frame[["p_home", "p_draw", "p_away"]].to_numpy()
        assert np.allclose(p.sum(axis=1), 1, atol=1e-5)
        assert ((frame["p_over25"] > 0) & (frame["p_over25"] < 1)).all()
    assert events and {"fold", "season", "step", "train_loss", "val_loss"} <= set(events[-1])
    assert set(chooser.summary()) == {"ENG1", "ESP1"}

    # Save, load, and predict the same numbers.
    model = ml.MODEL_CLASSES[family](device="cpu").fit(ml.training_rows(feats))
    model.save(tmp_path / family)
    loaded = ml.MODEL_CLASSES[family].load(tmp_path / family)
    sample = feats.tail(30)
    for variant in ("global", "league"):
        a = model.predict(sample, variant).sort_values("match_id").reset_index(drop=True)
        b = loaded.predict(sample, variant).sort_values("match_id").reset_index(drop=True)
        np.testing.assert_allclose(a["p_home"], b["p_home"], rtol=1e-4, atol=1e-5)


def test_league_chooser_only_switches_with_evidence() -> None:
    chooser = ml.LeagueChooser()
    assert chooser.choice("ENG1") == "global"
    chooser.update("ENG1", "global", np.full(300, 1.0))
    chooser.update("ENG1", "league", np.full(300, 0.9))
    chooser.update("ESP1", "global", np.full(300, 0.9))
    chooser.update("ESP1", "league", np.full(300, 1.0))
    assert chooser.all_choices() == {"ENG1": "league", "ESP1": "global"}


def test_ensemble_averages_common_matches() -> None:
    a = pd.DataFrame({"match_id": [1, 2], **{c: [0.2, 0.4] for c in ml.OUTPUT_COLUMNS}})
    b = pd.DataFrame({"match_id": [2, 3], **{c: [0.6, 0.8] for c in ml.OUTPUT_COLUMNS}})
    out = ml.ensemble([a, b])
    assert out["match_id"].tolist() == [2]
    assert out["p_home"].iloc[0] == pytest.approx(0.5)


def test_xgb_league_models_keep_the_global_trees(small_training) -> None:
    pytest.importorskip("xgboost")
    feats = build_features(two_leagues(4))
    model = ml.XGBMatchModel(device="cpu").fit(ml.training_rows(feats))
    assert model.league_boosters
    for league, boosters in model.league_boosters.items():
        for task, booster in boosters.items():
            assert booster.num_boosted_rounds() > model.boosters[task].num_boosted_rounds(), (league, task)
