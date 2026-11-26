"""Player impact ratings and lineup features: point-in-time, and they find the player who matters."""

import numpy as np
import pandas as pd

from backend.models.features import FEATURE_COLUMNS, build_features
from backend.models.players import PLAYER_FEATURES, PlayerRatings, player_features


def league_with_a_star(n_rounds: int = 40, seed: int = 3):
    """Team 1 plays team 2 repeatedly. Team 1 scores only while its star (player 100) is on the pitch;
    he plays the first 60 minutes in half the matches and is absent from the rest."""
    rng = np.random.default_rng(seed)
    matches, lineups, goals = [], [], []
    day = pd.Timestamp("2023-08-01")
    for i in range(n_rounds):
        mid = i + 1
        star_plays = i % 2 == 0
        home_goals = int(star_plays) + int(rng.random() < 0.2)
        away_goals = int(rng.random() < 0.3)
        matches.append({"match_id": mid, "date": day, "home_id": 1, "away_id": 2, "status": "finished",
                        "home_goals": home_goals, "away_goals": away_goals})
        for pid in range(101, 111):
            lineups.append((mid, day, 1, pid, True, None, None))
        lineups.append((mid, day, 1, 100 if star_plays else 111, True, None, 60 if star_plays else None))
        lineups.append((mid, day, 1, 111 if star_plays else 112, False, 60 if star_plays else None, None))
        for pid in range(200, 211):
            lineups.append((mid, day, 2, pid, True, None, None))
        if star_plays:
            goals.append((mid, 1, 30.0, "goal"))
        if home_goals > int(star_plays):
            goals.append((mid, 1, 75.0 if star_plays else 30.0, "goal"))
        if away_goals:
            goals.append((mid, 2, 80.0, "goal"))
        day += pd.Timedelta(days=7)
    lineups = pd.DataFrame(lineups, columns=["match_id", "date", "team_id", "player_id", "started", "minute_on", "minute_off"])
    goals = pd.DataFrame(goals, columns=["match_id", "team_id", "minute", "kind"])
    return pd.DataFrame(matches), lineups, goals


def test_star_player_gets_the_highest_impact() -> None:
    matches, lineups, goals = league_with_a_star()
    ratings = PlayerRatings()
    player_features(matches, lineups, goals, ratings)
    impacts = {p: s.impact for p, s in ratings.players.items() if ratings.team_of.get(p) == 1}
    assert max(impacts, key=impacts.get) == 100
    assert impacts[100] > 0.3


def test_lineup_features_only_use_earlier_matches() -> None:
    matches, lineups, goals = league_with_a_star()
    base = player_features(matches, lineups, goals).set_index("match_id")
    changed_goals = goals[goals["match_id"] != 21]  # remove match 21's goals
    changed = matches.copy()
    changed.loc[changed["match_id"] == 21, ["home_goals", "away_goals"]] = [0, 0]
    after = player_features(changed, lineups, changed_goals).set_index("match_id")
    pd.testing.assert_frame_equal(base.loc[:21], after.loc[:21])
    assert not base.loc[22:].equals(after.loc[22:])


def test_missing_star_shows_up_as_regulars_out() -> None:
    matches, lineups, goals = league_with_a_star()
    feats = player_features(matches, lineups, goals).set_index("match_id")
    late = feats.loc[30:]
    with_star = late[late.index % 2 == 1]  # match ids are i+1, star plays when i is even
    without = late[late.index % 2 == 0]
    assert without["home_xi_impact"].mean() < with_star["home_xi_impact"].mean()


def test_build_features_has_player_columns_even_without_lineups() -> None:
    from tests.test_models import synthetic_league

    feats = build_features(synthetic_league(2))
    for side in ("home", "away"):
        for f in PLAYER_FEATURES:
            assert f"{side}_{f}" in FEATURE_COLUMNS
            assert feats[f"{side}_{f}"].isna().all()
