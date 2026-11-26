"""News: scoring headlines, parsing ESPN's feed, point-in-time news features, feature switches."""

import numpy as np
import pandas as pd

from backend.models.features import (
    FEATURE_GROUPS,
    _news_features,
    apply_feature_groups,
    build_features,
)
from backend.scraping.news_analysis import analyse
from backend.scraping.spiders.espn_news import parse_articles
from tests.test_models import synthetic_league


def test_good_bad_and_injury_news() -> None:
    good = analyse("Haaland hat-trick as Man City thrash Spurs to go top", "City extend lead with dominant win")
    bad = analyse("Arteta under pressure as Arsenal slump to third straight defeat", None)
    hurt = analyse("Saka ruled out for six weeks with hamstring injury", "Blow for Arsenal")
    neutral = analyse("Transfer rumors: Barcelona eyeing defender", None)
    assert good["sentiment"] > 0.5 and not good["injury"]
    assert bad["sentiment"] < -0.5
    assert hurt["sentiment"] < 0 and hurt["injury"]
    assert neutral["sentiment"] == 0 and neutral["signals"]["transfer"]


def test_betting_words_do_not_score() -> None:
    assert analyse("Best betting tips and odds for the weekend", None)["sentiment"] == 0


def test_parse_espn_articles_keeps_tags_and_no_betting_fields() -> None:
    payload = {"articles": [{
        "id": 1, "headline": "H", "description": "D", "published": "2026-11-26T08:57:49Z",
        "links": {"web": {"href": "https://espn.com/x"}},
        "categories": [{"type": "team", "teamId": 360, "description": "Manchester United"},
                       {"type": "athlete", "athleteId": 7, "description": "A Player"},
                       {"type": "topic", "description": "soccer transfers"}],
    }, {"id": 2, "headline": None}]}
    [article] = parse_articles(payload, "ENG1")
    assert article["teams"] == [{"id": "360", "name": "Manchester United"}]
    assert article["players"] == [{"id": "7", "name": "A Player"}]
    assert article["url"] == "https://espn.com/x" and article["league"] == "ENG1"


def test_news_features_only_use_articles_before_the_match_day() -> None:
    matches = synthetic_league(1).head(20)
    day = matches.iloc[10]["date"]
    home = int(matches.iloc[10]["home_id"])
    news = pd.DataFrame({
        "team_id": [home, home, home],
        "published_at": [day - pd.Timedelta(days=3), day + pd.Timedelta(hours=2), day - pd.Timedelta(days=9)],
        "sentiment": [-0.8, 0.9, 0.9], "injury": [True, False, False], "weight": [1.0, 1.0, 1.0],
    })
    feats = _news_features(matches, news).set_index("match_id")
    row = feats.loc[matches.iloc[10]["match_id"]]
    assert row["home_news_n7"] == 1  # only the article 3 days before; not same-day, not 9 days before
    assert row["home_news_sentiment7"] == -0.8
    assert row["home_news_injury7"] == 1


def test_switched_off_groups_are_blanked() -> None:
    feats = build_features(synthetic_league(2))
    feats[list(FEATURE_GROUPS["news"])] = 1.0
    off = apply_feature_groups(feats, {"players": True, "news": False})
    assert off[list(FEATURE_GROUPS["news"])].isna().all().all()
    on = apply_feature_groups(feats, {"news": True})
    assert np.allclose(on[list(FEATURE_GROUPS["news"])].to_numpy(), 1.0)
